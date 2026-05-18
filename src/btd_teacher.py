from dataclasses import dataclass

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

def build_sequence_windows(X, group_ids=None, radius=2):
    X = np.asarray(X, dtype=np.float32)
    if radius < 1 or len(X) == 0:
        return X[:, None, :]

    if group_ids is None:
        group_ids = np.zeros(len(X), dtype=int)
    group_ids = np.asarray(group_ids)

    windows = []
    start = 0
    while start < len(X):
        end = start + 1
        while end < len(X) and group_ids[end] == group_ids[start]:
            end += 1

        group_X = X[start:end]
        for idx in range(len(group_X)):
            slices = []
            for offset in range(-radius, radius + 1):
                ref_idx = min(max(idx + offset, 0), len(group_X) - 1)
                slices.append(group_X[ref_idx])
            windows.append(np.stack(slices, axis=0))
        start = end

    return np.asarray(windows, dtype=np.float32)


class BiLSTMTeacherNet(nn.Module):
    def __init__(self, input_dim, hidden_dim=64, num_layers=2, num_classes=5, dropout=0.2):
        super().__init__()
        lstm_dropout = dropout if num_layers > 1 else 0.0
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=lstm_dropout,
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_dim * 2, num_classes)

    def forward(self, x):
        output, _ = self.lstm(x)
        pooled = output[:, output.shape[1] // 2, :]
        pooled = self.dropout(pooled)
        return self.classifier(pooled)

    def encode(self, x):
        output, _ = self.lstm(x)
        pooled = output[:, output.shape[1] // 2, :]
        return self.dropout(pooled)


@dataclass
class TeacherTrainingSummary:
    best_val_loss: float
    best_val_acc: float
    epochs_ran: int


class BiLSTMSequenceClassifier:
    def __init__(
        self,
        input_dim,
        num_classes,
        hidden_dim=64,
        num_layers=2,
        dropout=0.2,
        batch_size=128,
        lr=1e-3,
        max_epochs=30,
        patience=6,
        seed=42,
        device=None,
    ):
        self.input_dim = input_dim
        self.num_classes = num_classes
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout = dropout
        self.batch_size = batch_size
        self.lr = lr
        self.max_epochs = max_epochs
        self.patience = patience
        self.seed = seed
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.summary = None

    def _build_model(self):
        self.model = BiLSTMTeacherNet(
            input_dim=self.input_dim,
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers,
            num_classes=self.num_classes,
            dropout=self.dropout,
        ).to(self.device)
        return self.model

    def _make_loader(self, X, y=None, shuffle=False):
        X_tensor = torch.tensor(X, dtype=torch.float32)
        if y is None:
            dataset = TensorDataset(X_tensor)
        else:
            y_tensor = torch.tensor(y, dtype=torch.long)
            dataset = TensorDataset(X_tensor, y_tensor)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=shuffle)

    def fit(self, X, y):
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        self._build_model()

        idx = np.arange(len(y))
        train_idx, val_idx = train_test_split(
            idx,
            test_size=0.15,
            random_state=self.seed,
            stratify=y,
        )
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]

        counts = np.bincount(y_train, minlength=self.num_classes).astype(np.float32)
        counts = np.where(counts > 0, counts, 1.0)
        class_weights = counts.max() / counts
        class_weights = class_weights / class_weights.mean()
        criterion = nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32, device=self.device))
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)

        train_loader = self._make_loader(X_train, y_train, shuffle=True)
        val_loader = self._make_loader(X_val, y_val, shuffle=False)

        best_state = None
        best_val_loss = float('inf')
        best_val_acc = 0.0
        wait = 0
        epochs_ran = 0

        for epoch in range(self.max_epochs):
            epochs_ran = epoch + 1
            self.model.train()
            for batch_X, batch_y in train_loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)
                optimizer.zero_grad()
                logits = self.model(batch_X)
                loss = criterion(logits, batch_y)
                loss.backward()
                optimizer.step()

            self.model.eval()
            total_loss = 0.0
            total_correct = 0
            total_count = 0
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    batch_X = batch_X.to(self.device)
                    batch_y = batch_y.to(self.device)
                    logits = self.model(batch_X)
                    loss = criterion(logits, batch_y)
                    total_loss += float(loss.item()) * len(batch_y)
                    pred = torch.argmax(logits, dim=1)
                    total_correct += int((pred == batch_y).sum().item())
                    total_count += int(len(batch_y))

            val_loss = total_loss / max(total_count, 1)
            val_acc = total_correct / max(total_count, 1)
            if val_loss < best_val_loss - 1e-5:
                best_val_loss = val_loss
                best_val_acc = val_acc
                best_state = {key: value.detach().cpu().clone() for key, value in self.model.state_dict().items()}
                wait = 0
            else:
                wait += 1
                if wait >= self.patience:
                    break

        if best_state is not None:
            self.model.load_state_dict(best_state)
        self.summary = TeacherTrainingSummary(
            best_val_loss=float(best_val_loss),
            best_val_acc=float(best_val_acc),
            epochs_ran=epochs_ran,
        )
        return self

    def predict_logits(self, X):
        loader = self._make_loader(X, shuffle=False)
        outputs = []
        self.model.eval()
        with torch.no_grad():
            for (batch_X,) in loader:
                batch_X = batch_X.to(self.device)
                logits = self.model(batch_X)
                outputs.append(logits.cpu().numpy())
        return np.concatenate(outputs, axis=0)

    def predict_embeddings(self, X):
        loader = self._make_loader(X, shuffle=False)
        outputs = []
        self.model.eval()
        with torch.no_grad():
            for (batch_X,) in loader:
                batch_X = batch_X.to(self.device)
                embedding = self.model.encode(batch_X)
                outputs.append(embedding.cpu().numpy())
        return np.concatenate(outputs, axis=0)

    def predict_proba(self, X, temperature=1.0):
        logits = self.predict_logits(X)
        temperature = max(float(temperature), 1e-12)
        scaled = logits / temperature
        scaled = scaled - np.max(scaled, axis=1, keepdims=True)
        exp_scores = np.exp(scaled)
        return exp_scores / (np.sum(exp_scores, axis=1, keepdims=True) + 1e-12)

    def predict(self, X):
        return np.argmax(self.predict_proba(X, temperature=1.0), axis=1)

    def state_dict(self):
        return self.model.state_dict()
