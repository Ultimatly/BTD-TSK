import numpy as np
import skfuzzy as fuzz


class BaseTSK:
    def __init__(self, n_rules=10, h=1.0, reg=1e-3):
        self.n_rules = n_rules
        self.h = h
        self.reg = reg
        self.a = None
        self.sigma = None
        self.beta = None

    def _compute_firing_strength(self, X, a, sigma):
        n_samples, _ = X.shape
        n_rules = a.shape[0]
        H = np.zeros((n_samples, n_rules))
        for rule_idx in range(n_rules):
            # A very large sigma acts like "ignore this feature" for inherited padding.
            dist = -((X - a[rule_idx, :]) ** 2) / (2 * sigma[rule_idx, :] ** 2)
            H[:, rule_idx] = np.exp(np.sum(dist, axis=1))
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

    def fit(self, X, Y, sample_weight=None):
        _, n_features = X.shape

        # Keep the first-layer antecedent estimation unchanged: FCM -> Gaussian rules.
        centers, memberships, _, _, _, _, _ = fuzz.cluster.cmeans(
            X.T, c=self.n_rules, m=2.0, error=0.005, maxiter=1000, init=None
        )
        self.a = centers
        self.sigma = np.zeros_like(self.a)

        for rule_idx in range(self.n_rules):
            membership_sum = np.sum(memberships[rule_idx, :])
            for feature_idx in range(n_features):
                numerator = np.sum(
                    memberships[rule_idx, :] * (X[:, feature_idx] - self.a[rule_idx, feature_idx]) ** 2
                )
                self.sigma[rule_idx, feature_idx] = self.h * (numerator / membership_sum) + 1e-6
        self.sigma = np.sqrt(self.sigma)

        H = self._compute_firing_strength(X, self.a, self.sigma)
        self.beta = self._solve_beta(H, Y, sample_weight=sample_weight)

    def predict(self, X):
        H = self._compute_firing_strength(X, self.a, self.sigma)
        return H @ self.beta