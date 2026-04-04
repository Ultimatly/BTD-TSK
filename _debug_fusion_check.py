import numpy as np
from data_processor import build_dataset
from eatt_tsk_fc_model import EAttTSKFC

def softmax(z):
    z = z - np.max(z, axis=1, keepdims=True)
    e = np.exp(z)
    return e / np.sum(e, axis=1, keepdims=True)

data_dir = r'f:\sleep\data'
records = ['slp01a', 'slp01b', 'slp02a', 'slp02b', 'slp03']
X_train, X_test, y_train, y_test = build_dataset(data_dir, records, n_components=10, class_mode='five_class')

model = EAttTSKFC(dp_layers=2, n_rules=10, heritage_ratio=0.25, num_classes=5, random_state=28738)
model.fit(X_train, y_train)

pred_model = model.predict(X_test)
acc_model = (pred_model == y_test).mean()
print('model_acc', acc_model)

X0 = X_test.copy()
cur = X_test.copy()
cumulative = np.zeros((X_test.shape[0], 5))
cum_snapshots = []

for i, tsk in enumerate(model.classifiers):
    out = tsk.predict(cur)
    cumulative += out
    cum_snapshots.append(cumulative.copy())
    if i < len(model.classifiers) - 1:
        cur = np.concatenate([X0, model.alpha * out], axis=1)

pred_cum_last = np.argmax(cum_snapshots[-1], axis=1)
acc_cum_last = (pred_cum_last == y_test).mean()
print('cum_last_acc', acc_cum_last)

probs = [softmax(s) for s in cum_snapshots]
entropies = []
for p in probs:
    entropies.append((-np.sum(p * np.log(p + 1e-12), axis=1)) / np.log(5))

E = np.column_stack(entropies)
A = np.exp(-E / 1.0)
A /= np.sum(A, axis=1, keepdims=True)
P = np.zeros_like(probs[0])
for i, p in enumerate(probs):
    P += A[:, [i]] * p

pred_entropy_cum = np.argmax(P, axis=1)
acc_entropy_cum = (pred_entropy_cum == y_test).mean()
print('cum_entropy_acc', acc_entropy_cum)