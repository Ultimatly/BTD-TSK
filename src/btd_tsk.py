from dataclasses import dataclass

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

try:
    from .btd_teacher import BiLSTMSequenceClassifier
    from .tsk_classifier import BaseTSK
except ImportError:
    from btd_teacher import BiLSTMSequenceClassifier
    from tsk_classifier import BaseTSK


@dataclass
class BTDTSKTrainingSummary:
    best_val_loss: float
    best_val_acc: float
    epochs_ran: int


class ZeroOrderTSKGDClassifier:
    def __init__(
        self,
        n_rules=10,
        reg=1e-4,
        batch_size=256,
        lr=5e-2,
        max_epochs=200,
        patience=20,
        selection_metric='loss',
        seed=42,
        device=None,
        antecedent_strategy='global',
        kd_mode='full',
        lambda_anchor=0.0,
    ):
        self.n_rules = n_rules
        self.reg = reg
        self.batch_size = batch_size
        self.lr = lr
        self.max_epochs = max_epochs
        self.patience = patience
        self.selection_metric = selection_metric
        self.seed = seed
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.antecedent_strategy = antecedent_strategy
        self.kd_mode = kd_mode
        self.lambda_anchor = lambda_anchor

        self.base_model = BaseTSK(n_rules=n_rules, reg=reg)
        self.num_classes = None
        self.beta = None
        self.summary = None

    def _softmax(self, scores, temperature=1.0):
        temperature = max(float(temperature), 1e-12)
        shifted = scores / temperature
        shifted = shifted - np.max(shifted, axis=1, keepdims=True)
        exp_scores = np.exp(shifted)
        return exp_scores / (np.sum(exp_scores, axis=1, keepdims=True) + 1e-12)

    def fit_antecedents(self, X, num_classes, y=None, sample_weight=None):
        self.num_classes = int(num_classes)
        np.random.seed(self.seed)
        self.base_model.fit_antecedents(
            X,
            y=y,
            num_classes=self.num_classes,
            strategy=self.antecedent_strategy,
            sample_weight=sample_weight,
        )
        return self

    def _top2_kd_loss(self, logits, teacher_logits, temperature):
        teacher_soft = torch.softmax(teacher_logits / temperature, dim=1)
        student_soft = torch.softmax(logits / temperature, dim=1)
        topk = min(2, teacher_soft.shape[1])
        top_idx = torch.topk(teacher_soft, k=topk, dim=1).indices
        teacher_top = torch.gather(teacher_soft, 1, top_idx)
        student_top = torch.gather(student_soft, 1, top_idx)
        teacher_top = teacher_top / (teacher_top.sum(dim=1, keepdim=True) + 1e-12)
        student_top = student_top / (student_top.sum(dim=1, keepdim=True) + 1e-12)
        return torch.sum(
            teacher_top * (torch.log(teacher_top + 1e-12) - torch.log(student_top + 1e-12)),
            dim=1,
        ).mean() * (temperature ** 2)

    def _anchor_loss(self, beta):
        rule_class_ids = getattr(self.base_model, 'rule_class_ids', None)
        if rule_class_ids is None or self.lambda_anchor <= 0.0:
            return beta.new_tensor(0.0)
        target = torch.tensor(rule_class_ids, dtype=torch.long, device=beta.device)
        log_probs = torch.log_softmax(beta, dim=1)
        return -log_probs[torch.arange(len(target), device=beta.device), target].mean()

    def _make_loader(self, H, y, teacher_logits=None, shuffle=False):
        H_tensor = torch.tensor(H, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.long)
        tensors = [H_tensor, y_tensor]
        if teacher_logits is not None:
            tensors.append(torch.tensor(teacher_logits, dtype=torch.float32))
        dataset = TensorDataset(*tensors)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=shuffle)

    def _train_beta(self, H, y, teacher_logits=None, lambda_ce=1.0, lambda_kd=0.0, temperature=2.0):
        idx = np.arange(len(y))
        train_idx, val_idx = train_test_split(
            idx,
            test_size=0.15,
            random_state=self.seed,
            stratify=y,
        )

        H_train, y_train = H[train_idx], y[train_idx]
        H_val, y_val = H[val_idx], y[val_idx]
        teacher_train = None if teacher_logits is None else teacher_logits[train_idx]
        teacher_val = None if teacher_logits is None else teacher_logits[val_idx]

        criterion = nn.CrossEntropyLoss()
        kl_div = nn.KLDivLoss(reduction='batchmean')

        train_loader = self._make_loader(H_train, y_train, teacher_logits=teacher_train, shuffle=True)
        val_loader = self._make_loader(H_val, y_val, teacher_logits=teacher_val, shuffle=False)

        torch.manual_seed(self.seed)
        beta = nn.Parameter(torch.zeros(self.n_rules, self.num_classes, dtype=torch.float32, device=self.device))
        optimizer = torch.optim.Adam([beta], lr=self.lr, weight_decay=self.reg)

        best_state = None
        best_val_loss = float('inf')
        best_val_acc = 0.0
        best_score = float('inf') if self.selection_metric == 'loss' else -float('inf')
        wait = 0
        epochs_ran = 0

        for epoch in range(self.max_epochs):
            epochs_ran = epoch + 1
            self.base_model.beta = None
            for batch in train_loader:
                batch_H = batch[0].to(self.device)
                batch_y = batch[1].to(self.device)
                batch_teacher = batch[2].to(self.device) if teacher_train is not None else None

                optimizer.zero_grad()
                logits = batch_H @ beta
                loss = lambda_ce * criterion(logits, batch_y)
                if batch_teacher is not None and lambda_kd > 0.0:
                    if self.kd_mode == 'top2':
                        kd_loss = self._top2_kd_loss(logits, batch_teacher, temperature)
                    else:
                        teacher_soft = torch.softmax(batch_teacher / temperature, dim=1)
                        student_log_soft = torch.log_softmax(logits / temperature, dim=1)
                        kd_loss = kl_div(student_log_soft, teacher_soft) * (temperature ** 2)
                    loss = loss + lambda_kd * kd_loss
                if self.lambda_anchor > 0.0:
                    loss = loss + self.lambda_anchor * self._anchor_loss(beta)
                loss.backward()
                optimizer.step()

            with torch.no_grad():
                total_loss = 0.0
                total_correct = 0
                total_count = 0
                for batch in val_loader:
                    batch_H = batch[0].to(self.device)
                    batch_y = batch[1].to(self.device)
                    batch_teacher = batch[2].to(self.device) if teacher_val is not None else None
                    logits = batch_H @ beta
                    loss = lambda_ce * criterion(logits, batch_y)
                    if batch_teacher is not None and lambda_kd > 0.0:
                        if self.kd_mode == 'top2':
                            kd_loss = self._top2_kd_loss(logits, batch_teacher, temperature)
                        else:
                            teacher_soft = torch.softmax(batch_teacher / temperature, dim=1)
                            student_log_soft = torch.log_softmax(logits / temperature, dim=1)
                            kd_loss = kl_div(student_log_soft, teacher_soft) * (temperature ** 2)
                        loss = loss + lambda_kd * kd_loss
                    if self.lambda_anchor > 0.0:
                        loss = loss + self.lambda_anchor * self._anchor_loss(beta)
                    total_loss += float(loss.item()) * len(batch_y)
                    pred = torch.argmax(logits, dim=1)
                    total_correct += int((pred == batch_y).sum().item())
                    total_count += int(len(batch_y))

                val_loss = total_loss / max(total_count, 1)
                val_acc = total_correct / max(total_count, 1)
                current_score = val_loss if self.selection_metric == 'loss' else val_acc
                improved = (
                    current_score < best_score - 1e-6
                    if self.selection_metric == 'loss'
                    else current_score > best_score + 1e-6
                )
                if improved:
                    best_score = current_score
                    best_val_loss = val_loss
                    best_val_acc = val_acc
                    best_state = beta.detach().cpu().clone()
                    wait = 0
                else:
                    wait += 1
                    if wait >= self.patience:
                        break

        if best_state is None:
            best_state = beta.detach().cpu().clone()

        self.beta = best_state.numpy()
        self.base_model.beta = self.beta
        self.summary = BTDTSKTrainingSummary(
            best_val_loss=float(best_val_loss),
            best_val_acc=float(best_val_acc),
            epochs_ran=epochs_ran,
        )
        return self

    def fit(self, X, y):
        y = np.asarray(y, dtype=int)
        self.fit_antecedents(X, int(np.max(y)) + 1, y=y)
        H = self.base_model.compute_rule_activations(X)
        self._train_beta(H, y, teacher_logits=None, lambda_ce=1.0, lambda_kd=0.0, temperature=1.0)
        return self

    def fit_distilled(
        self,
        X,
        y,
        teacher_logits,
        lambda_ce=1.0,
        lambda_kd=0.5,
        temperature=2.0,
        antecedent_sample_weight=None,
        fit_antecedent=True,
    ):
        y = np.asarray(y, dtype=int)
        if fit_antecedent or self.base_model.a is None or self.base_model.sigma is None:
            self.fit_antecedents(X, int(np.max(y)) + 1, y=y, sample_weight=antecedent_sample_weight)
        else:
            self.num_classes = int(np.max(y)) + 1
        H = self.base_model.compute_rule_activations(X)
        self._train_beta(H, y, teacher_logits=teacher_logits, lambda_ce=lambda_ce, lambda_kd=lambda_kd, temperature=temperature)
        return self

    def set_antecedents(self, a, sigma, rule_class_ids=None, num_classes=None):
        self.base_model.a = np.asarray(a, dtype=float)
        self.base_model.sigma = np.asarray(sigma, dtype=float)
        self.base_model.rule_class_ids = None if rule_class_ids is None else np.asarray(rule_class_ids, dtype=int)
        if num_classes is not None:
            self.num_classes = int(num_classes)
        return self

    def predict_scores(self, X):
        return self.base_model.predict_scores(X)

    def predict_proba(self, X, temperature=1.0):
        return self._softmax(self.predict_scores(X), temperature=temperature)

    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)

    def compute_rule_activations(self, X):
        return self.base_model.compute_rule_activations(X)

    def get_rule_class_probabilities(self):
        if self.base_model.beta is None:
            raise ValueError('Model consequents are not initialized.')
        return self._softmax(self.base_model.beta, temperature=1.0)

    @property
    def a(self):
        return self.base_model.a

    @property
    def sigma(self):
        return self.base_model.sigma



class BTDTSKDistiller:
    def __init__(
        self,
        student_n_rules=10,
        sequence_radius=2,
        teacher_temperature=2.0,
        lambda_ce=1.0,
        lambda_kd=0.5,
        seed=42,
        antecedent_strategy='global',
        kd_mode='full',
        lambda_anchor=0.0,
        antecedent_guidance='none',
        guidance_alpha=0.7,
    ):
        self.student_n_rules = student_n_rules
        self.sequence_radius = sequence_radius
        self.teacher_temperature = teacher_temperature
        self.lambda_ce = lambda_ce
        self.lambda_kd = lambda_kd
        self.seed = seed
        self.antecedent_strategy = antecedent_strategy
        self.kd_mode = kd_mode
        self.lambda_anchor = lambda_anchor
        self.antecedent_guidance = antecedent_guidance
        self.guidance_alpha = guidance_alpha
        self.teacher_model = None
        self.student_model = ZeroOrderTSKGDClassifier(
            n_rules=student_n_rules,
            seed=seed,
            antecedent_strategy=antecedent_strategy,
            kd_mode=kd_mode,
            lambda_anchor=lambda_anchor,
        )
        self.training_details = {}

    def _allocate_rule_quotas(self, y, num_classes):
        y = np.asarray(y, dtype=int)
        class_counts = np.bincount(y, minlength=num_classes).astype(float)
        quotas = np.ones(num_classes, dtype=int)
        remaining = max(int(self.student_n_rules) - int(num_classes), 0)
        if remaining <= 0:
            return quotas

        proportions = class_counts / max(class_counts.sum(), 1e-12)
        raw_extra = remaining * proportions
        extra = np.floor(raw_extra).astype(int)
        quotas += extra
        leftover = remaining - int(extra.sum())
        if leftover > 0:
            order = np.argsort(-(raw_extra - extra))
            for idx in order[:leftover]:
                quotas[idx] += 1
        return quotas

    def _weighted_mean(self, X, sample_weight):
        weight = np.asarray(sample_weight, dtype=float).reshape(-1, 1)
        denom = np.sum(weight) + 1e-12
        return np.sum(X * weight, axis=0) / denom

    def _weighted_variance(self, X, center, sample_weight):
        weight = np.asarray(sample_weight, dtype=float).reshape(-1, 1)
        denom = np.sum(weight) + 1e-12
        return np.sum(((X - center) ** 2) * weight, axis=0) / denom

    def _build_teacher_embedding_antecedents(self, X_student, y, teacher_embeddings, teacher_probs):
        y = np.asarray(y, dtype=int)
        num_classes = int(np.max(y)) + 1
        quotas = self._allocate_rule_quotas(y, num_classes)

        entropy = -np.sum(teacher_probs * np.log(teacher_probs + 1e-12), axis=1)
        entropy_norm = entropy / np.log(max(num_classes, 2))

        centers = []
        sigmas = []
        rule_class_ids = []

        for class_idx in range(num_classes):
            class_mask = y == class_idx
            class_x = X_student[class_mask]
            class_h = teacher_embeddings[class_mask]
            if len(class_x) == 0:
                continue

            true_prob = teacher_probs[class_mask, class_idx]
            class_entropy = entropy_norm[class_mask]
            class_weight = (
                self.guidance_alpha * true_prob
                + (1.0 - self.guidance_alpha) * (1.0 - class_entropy)
            )
            class_weight = np.clip(class_weight, 1e-3, None)
            class_weight = class_weight / (np.mean(class_weight) + 1e-12)

            n_clusters = min(max(int(quotas[class_idx]), 1), len(class_x))
            if n_clusters == 1:
                labels = np.zeros(len(class_x), dtype=int)
            else:
                from sklearn.cluster import KMeans

                kmeans = KMeans(n_clusters=n_clusters, random_state=self.seed, n_init=10)
                kmeans.fit(class_h, sample_weight=class_weight)
                labels = kmeans.labels_

            for local_idx in range(n_clusters):
                cluster_mask = labels == local_idx
                cluster_x = class_x[cluster_mask]
                cluster_weight = class_weight[cluster_mask]
                if len(cluster_x) == 0:
                    cluster_x = class_x
                    cluster_weight = class_weight
                center = self._weighted_mean(cluster_x, cluster_weight)
                variance = self._weighted_variance(cluster_x, center, cluster_weight)
                sigma = np.sqrt(self.student_model.base_model.h * variance + 1e-6)
                centers.append(center)
                sigmas.append(sigma)
                rule_class_ids.append(class_idx)

        centers = np.asarray(centers, dtype=float)
        sigmas = np.asarray(sigmas, dtype=float)
        rule_class_ids = np.asarray(rule_class_ids, dtype=int)

        if len(centers) < self.student_n_rules:
            deficit = self.student_n_rules - len(centers)
            repeats = np.arange(len(centers))[:deficit]
            centers = np.vstack([centers, centers[repeats]])
            sigmas = np.vstack([sigmas, sigmas[repeats]])
            rule_class_ids = np.concatenate([rule_class_ids, rule_class_ids[repeats]])
        elif len(centers) > self.student_n_rules:
            centers = centers[:self.student_n_rules]
            sigmas = sigmas[:self.student_n_rules]
            rule_class_ids = rule_class_ids[:self.student_n_rules]

        return centers, sigmas, rule_class_ids

    def _build_antecedent_weight(self, y, teacher_probs):
        if self.antecedent_guidance != 'teacher':
            return None
        num_classes = teacher_probs.shape[1]
        true_prob = teacher_probs[np.arange(len(y)), y]
        entropy = -np.sum(teacher_probs * np.log(teacher_probs + 1e-12), axis=1)
        entropy_norm = entropy / np.log(max(num_classes, 2))
        confidence_term = self.guidance_alpha * true_prob
        certainty_term = (1.0 - self.guidance_alpha) * (1.0 - entropy_norm)
        weight = confidence_term + certainty_term
        weight = np.clip(weight, 1e-3, None)
        return weight / (np.mean(weight) + 1e-12)

    def fit(self, X_student, X_sequence, y):
        y = np.asarray(y, dtype=int)
        num_classes = int(np.max(y)) + 1

        self.teacher_model = BiLSTMSequenceClassifier(
            input_dim=X_sequence.shape[2],
            num_classes=num_classes,
            seed=self.seed,
        )
        self.teacher_model.fit(X_sequence, y)
        teacher_logits = self.teacher_model.predict_logits(X_sequence)
        teacher_probs = self.teacher_model.predict_proba(X_sequence, temperature=1.0)

        fit_antecedent = True
        antecedent_sample_weight = None
        if self.antecedent_guidance == 'teacher_embedding':
            teacher_embeddings = self.teacher_model.predict_embeddings(X_sequence)
            antecedent_a, antecedent_sigma, rule_class_ids = self._build_teacher_embedding_antecedents(
                X_student,
                y,
                teacher_embeddings,
                teacher_probs,
            )
            self.student_model.set_antecedents(
                antecedent_a,
                antecedent_sigma,
                rule_class_ids=rule_class_ids,
                num_classes=num_classes,
            )
            fit_antecedent = False
        else:
            antecedent_sample_weight = self._build_antecedent_weight(y, teacher_probs)

        self.student_model.fit_distilled(
            X_student,
            y,
            teacher_logits=teacher_logits,
            lambda_ce=self.lambda_ce,
            lambda_kd=self.lambda_kd,
            temperature=self.teacher_temperature,
            antecedent_sample_weight=antecedent_sample_weight,
            fit_antecedent=fit_antecedent,
        )

        self.training_details = {
            'teacher_summary': self.teacher_model.summary,
            'student_summary': self.student_model.summary,
            'teacher_confidence': float(np.mean(np.max(teacher_probs, axis=1))),
            'antecedent_guidance': self.antecedent_guidance,
            'guidance_weight_mean': None if antecedent_sample_weight is None else float(np.mean(antecedent_sample_weight)),
            'rule_class_distribution': None
            if self.student_model.base_model.rule_class_ids is None
            else {
                int(class_idx): int(np.sum(self.student_model.base_model.rule_class_ids == class_idx))
                for class_idx in range(num_classes)
            },
        }
        return self

    def predict_student(self, X_student):
        return self.student_model.predict(X_student)
