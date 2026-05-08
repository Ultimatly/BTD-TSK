import numpy as np
import skfuzzy as fuzz
from sklearn.cluster import KMeans


class BaseTSK:
    def __init__(self, n_rules=10, h=1.0, reg=1e-3, normalize_firing=True, epsilon=1e-12):
        self.n_rules = n_rules
        self.h = h
        self.reg = reg
        self.normalize_firing = normalize_firing
        self.epsilon = epsilon
        self.a = None
        self.sigma = None
        self.beta = None
        self.rule_class_ids = None

    def _compute_firing_strength(self, X, a, sigma, normalize=None):
        n_samples, _ = X.shape
        n_rules = a.shape[0]
        H = np.zeros((n_samples, n_rules))
        for rule_idx in range(n_rules):
            dist = -((X - a[rule_idx, :]) ** 2) / (2 * sigma[rule_idx, :] ** 2)
            H[:, rule_idx] = np.exp(np.sum(dist, axis=1))

        if normalize is None:
            normalize = self.normalize_firing
        if normalize:
            H_sum = np.sum(H, axis=1, keepdims=True) + self.epsilon
            H = H / H_sum
        return H

    def _solve_beta(self, H, Y, sample_weight=None):
        if sample_weight is None:
            H_weighted = H
            Y_weighted = Y
        else:
            sqrt_weight = np.sqrt(sample_weight).reshape(-1, 1)
            H_weighted = H * sqrt_weight
            Y_weighted = Y * sqrt_weight

        identity = np.eye(H.shape[1])
        H_inv = np.linalg.pinv(H_weighted.T @ H_weighted + self.reg * identity) @ H_weighted.T
        return H_inv @ Y_weighted

    def _build_global_antecedents(self, X):
        _, feature_dim = X.shape
        centers, memberships, _, _, _, _, _ = fuzz.cluster.cmeans(
            X.T,
            c=self.n_rules,
            m=2.0,
            error=0.005,
            maxiter=1000,
            init=None,
        )

        sigma = np.zeros_like(centers)
        for rule_idx in range(self.n_rules):
            membership_sum = np.sum(memberships[rule_idx, :]) + self.epsilon
            for feature_idx in range(feature_dim):
                numerator = np.sum(
                    memberships[rule_idx, :] * (X[:, feature_idx] - centers[rule_idx, feature_idx]) ** 2
                )
                sigma[rule_idx, feature_idx] = self.h * (numerator / membership_sum) + 1e-6
        sigma = np.sqrt(sigma)
        return centers, sigma, None

    def _weighted_mean(self, X, sample_weight=None):
        if sample_weight is None:
            return np.mean(X, axis=0)
        weight = np.asarray(sample_weight, dtype=float).reshape(-1, 1)
        denom = np.sum(weight) + self.epsilon
        return np.sum(X * weight, axis=0) / denom

    def _weighted_variance(self, X, center, sample_weight=None):
        if sample_weight is None:
            return np.mean((X - center) ** 2, axis=0)
        weight = np.asarray(sample_weight, dtype=float).reshape(-1, 1)
        denom = np.sum(weight) + self.epsilon
        return np.sum(((X - center) ** 2) * weight, axis=0) / denom

    def _build_classwise_antecedents(self, X, y, num_classes, sample_weight=None):
        y = np.asarray(y, dtype=int)
        _, feature_dim = X.shape
        class_counts = np.bincount(y, minlength=num_classes).astype(float)
        quotas = np.ones(num_classes, dtype=int)
        remaining = max(int(self.n_rules) - int(num_classes), 0)
        if remaining > 0:
            proportions = class_counts / max(class_counts.sum(), self.epsilon)
            raw_extra = remaining * proportions
            extra = np.floor(raw_extra).astype(int)
            quotas += extra
            leftover = remaining - int(extra.sum())
            if leftover > 0:
                order = np.argsort(-(raw_extra - extra))
                for idx in order[:leftover]:
                    quotas[idx] += 1

        centers_list = []
        sigma_list = []
        rule_class_ids = []
        for class_idx in range(num_classes):
            class_mask = y == class_idx
            class_samples = X[class_mask]
            if len(class_samples) == 0:
                continue
            class_weight = None if sample_weight is None else np.asarray(sample_weight, dtype=float)[class_mask]
            n_clusters = min(max(quotas[class_idx], 1), len(class_samples))
            if n_clusters == 1:
                class_centers = self._weighted_mean(class_samples, class_weight)[None, :]
                labels = np.zeros(len(class_samples), dtype=int)
            else:
                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                if class_weight is None:
                    labels = kmeans.fit_predict(class_samples)
                else:
                    kmeans.fit(class_samples, sample_weight=class_weight)
                    labels = kmeans.labels_
                class_centers = kmeans.cluster_centers_

            for local_idx in range(n_clusters):
                cluster_mask = labels == local_idx
                cluster_samples = class_samples[cluster_mask]
                cluster_weight = None if class_weight is None else class_weight[cluster_mask]
                if len(cluster_samples) == 0:
                    cluster_samples = class_samples
                    cluster_weight = class_weight
                center = self._weighted_mean(cluster_samples, cluster_weight)
                variance = self._weighted_variance(cluster_samples, center, cluster_weight)
                sigma = np.sqrt(self.h * variance + 1e-6)
                centers_list.append(center)
                sigma_list.append(sigma)
                rule_class_ids.append(class_idx)

        centers = np.asarray(centers_list, dtype=float)
        sigma = np.asarray(sigma_list, dtype=float)

        if len(centers) < self.n_rules:
            deficit = self.n_rules - len(centers)
            repeats = np.arange(len(centers))[:deficit]
            centers = np.vstack([centers, centers[repeats]])
            sigma = np.vstack([sigma, sigma[repeats]])
            rule_class_ids.extend([rule_class_ids[idx] for idx in repeats])
        elif len(centers) > self.n_rules:
            centers = centers[:self.n_rules]
            sigma = sigma[:self.n_rules]
            rule_class_ids = rule_class_ids[:self.n_rules]

        return centers, sigma, np.asarray(rule_class_ids, dtype=int)

    def _build_antecedents(self, X, y=None, num_classes=None, strategy='global', sample_weight=None):
        if strategy == 'classwise':
            if y is None or num_classes is None:
                raise ValueError('Classwise antecedents require labels and num_classes.')
            return self._build_classwise_antecedents(X, y, num_classes, sample_weight=sample_weight)
        return self._build_global_antecedents(X)

    def fit_antecedents(self, X, y=None, num_classes=None, strategy='global', sample_weight=None):
        self.a, self.sigma, self.rule_class_ids = self._build_antecedents(
            X,
            y=y,
            num_classes=num_classes,
            strategy=strategy,
            sample_weight=sample_weight,
        )
        return self

    def fit_consequents(self, X, Y, sample_weight=None):
        if self.a is None or self.sigma is None:
            raise ValueError('Antecedents must be initialized before fitting consequents.')
        H = self._compute_firing_strength(X, self.a, self.sigma)
        self.beta = self._solve_beta(H, Y, sample_weight=sample_weight)
        return self

    def fit_with_targets(self, X, Y, sample_weight=None, fit_antecedent=True):
        if fit_antecedent or self.a is None or self.sigma is None:
            self.fit_antecedents(X)
        self.fit_consequents(X, Y, sample_weight=sample_weight)
        return self

    def fit(self, X, Y, sample_weight=None):
        return self.fit_with_targets(X, Y, sample_weight=sample_weight, fit_antecedent=True)

    def compute_rule_activations(self, X):
        if self.a is None or self.sigma is None:
            raise ValueError('Model antecedents are not initialized.')
        return self._compute_firing_strength(X, self.a, self.sigma)

    def predict_scores(self, X):
        if self.beta is None:
            raise ValueError('Consequents are not initialized.')
        H = self.compute_rule_activations(X)
        return H @ self.beta

    def predict(self, X):
        return self.predict_scores(X)

    def predict_proba(self, X):
        scores = self.predict_scores(X)
        shifted = scores - np.max(scores, axis=1, keepdims=True)
        exp_scores = np.exp(shifted)
        return exp_scores / (np.sum(exp_scores, axis=1, keepdims=True) + self.epsilon)


class ZeroOrderTSKClassifier:
    def __init__(self, n_rules=10, reg=1e-3, epsilon=1e-12, antecedent_strategy='global'):
        self.n_rules = n_rules
        self.reg = reg
        self.epsilon = epsilon
        self.antecedent_strategy = antecedent_strategy
        self.model = BaseTSK(n_rules=n_rules, reg=reg, epsilon=epsilon)
        self.num_classes = None

    def _softmax(self, scores, temperature=1.0):
        temperature = max(float(temperature), self.epsilon)
        shifted = scores / temperature
        shifted = shifted - np.max(shifted, axis=1, keepdims=True)
        exp_scores = np.exp(shifted)
        return exp_scores / (np.sum(exp_scores, axis=1, keepdims=True) + self.epsilon)

    def _onehot(self, y):
        y = np.asarray(y, dtype=int)
        if self.num_classes is None:
            self.num_classes = int(np.max(y)) + 1
        out = np.zeros((len(y), self.num_classes), dtype=float)
        out[np.arange(len(y)), y] = 1.0
        return out

    def fit(self, X, y):
        y = np.asarray(y, dtype=int)
        Y = self._onehot(y)
        if self.antecedent_strategy == 'classwise':
            self.model.fit_antecedents(X, y=y, num_classes=self.num_classes, strategy='classwise')
            self.model.fit_consequents(X, Y)
        else:
            self.model.fit(X, Y)
        return self

    def fit_antecedents(self, X, num_classes, y=None, sample_weight=None):
        self.num_classes = int(num_classes)
        self.model.fit_antecedents(
            X,
            y=y,
            num_classes=self.num_classes,
            strategy=self.antecedent_strategy,
            sample_weight=sample_weight,
        )
        return self

    def fit_with_targets(self, X, targets, sample_weight=None):
        targets = np.asarray(targets, dtype=float)
        self.num_classes = targets.shape[1]
        self.model.fit_consequents(X, targets, sample_weight=sample_weight)
        return self

    def set_antecedents(self, a, sigma, rule_class_ids=None, num_classes=None):
        self.model.a = np.asarray(a, dtype=float)
        self.model.sigma = np.asarray(sigma, dtype=float)
        self.model.rule_class_ids = None if rule_class_ids is None else np.asarray(rule_class_ids, dtype=int)
        if num_classes is not None:
            self.num_classes = int(num_classes)
        return self

    def predict_scores(self, X):
        return self.model.predict_scores(X)

    def predict_proba(self, X, temperature=1.0):
        return self._softmax(self.predict_scores(X), temperature=temperature)

    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)

    def compute_rule_activations(self, X):
        return self.model.compute_rule_activations(X)

    def get_rule_class_probabilities(self):
        if self.model.beta is None:
            raise ValueError('Model consequents are not initialized.')
        return self._softmax(self.model.beta, temperature=1.0)

    @property
    def a(self):
        return self.model.a

    @property
    def sigma(self):
        return self.model.sigma

    @property
    def beta(self):
        return self.model.beta

    @property
    def rule_class_ids(self):
        return self.model.rule_class_ids
