import numpy as np
from sklearn.preprocessing import OneHotEncoder

from tsk_classifier import BaseTSK


class EAttTSKFC:
    def __init__(
        self,
        dp_layers=2,
        n_rules=10,
        heritage_ratio=0.25,
        num_classes=5,
        random_state=42,
        model_name='EAtt-TSK-FC',
        inheritance_mode='elite',
        fusion_mode='entropy_attention',
        class_balanced=False,
        class_weight_power=0.5,
        class_weight_min=0.5,
        class_weight_max=2.0,
        use_projection=False,
        short_rule_ratio=0.1,
        drop_feature_ratio=0.2,
        alpha=0.1,
        temperature=1.0,
        epsilon=1e-12,
    ):
        self.dp_layers = dp_layers
        self.n_rules = n_rules
        self.heritage_ratio = heritage_ratio
        self.num_classes = num_classes
        self.random_state = random_state
        self.model_name = model_name
        self.inheritance_mode = inheritance_mode
        self.fusion_mode = fusion_mode
        self.class_balanced = class_balanced
        self.class_weight_power = class_weight_power
        self.class_weight_min = class_weight_min
        self.class_weight_max = class_weight_max
        self.use_projection = use_projection
        self.short_rule_ratio = short_rule_ratio
        self.drop_feature_ratio = drop_feature_ratio
        self.alpha = alpha
        self.temperature = temperature
        self.epsilon = epsilon

        self.classifiers = []
        self.projection_matrices = []
        self.rule_scores = []
        self.enc = OneHotEncoder(sparse_output=False, categories=[range(num_classes)])
        self.rng = np.random.RandomState(random_state)

    def _compute_sample_weight(self, y):
        if not self.class_balanced:
            return np.ones_like(y, dtype=float)

        class_counts = np.bincount(y, minlength=self.num_classes).astype(float)
        class_counts[class_counts == 0] = 1.0
        total_samples = float(len(y))
        # Use tempered and clipped class weights to avoid over-correction collapse.
        raw_weights = total_samples / (self.num_classes * class_counts)
        class_weights = np.power(raw_weights, self.class_weight_power)
        class_weights = np.clip(class_weights, self.class_weight_min, self.class_weight_max)
        class_weights = class_weights / np.mean(class_weights)
        return class_weights[y]

    def _generate_random_fuzzy_rules(self, X, num_rules):
        num_features = X.shape[1]
        mins = X.min(axis=0)
        maxs = X.max(axis=0)
        spans = np.maximum(maxs - mins, 1e-6)

        rules_a = self.rng.uniform(mins, maxs, size=(num_rules, num_features))
        sigma_low = 0.1 * spans
        sigma_high = 0.5 * spans
        rules_sigma = self.rng.uniform(sigma_low, sigma_high, size=(num_rules, num_features))
        return rules_a, rules_sigma

    def _build_projection_matrix(self, prev_dim, proj_dim):
        return self.rng.randn(prev_dim, proj_dim) / np.sqrt(max(prev_dim, 1))

    def _apply_short_rule_mask(self, sigma):
        for rule_idx in range(sigma.shape[0]):
            if self.rng.rand() < self.short_rule_ratio:
                num_drop = max(1, int(sigma.shape[1] * self.drop_feature_ratio))
                drop_indices = self.rng.choice(sigma.shape[1], num_drop, replace=False)
                sigma[rule_idx, drop_indices] = 1e9
        return sigma

    def _select_inherited_indices(self, prev_tsk, prev_input, sample_weight, num_inherited):
        if num_inherited <= 0:
            return np.array([], dtype=int)

        num_inherited = min(num_inherited, prev_tsk.n_rules)
        if self.inheritance_mode != 'elite':
            return self.rng.choice(prev_tsk.n_rules, num_inherited, replace=False)

        H_prev = prev_tsk._compute_firing_strength(prev_input, prev_tsk.a, prev_tsk.sigma)
        scores = H_prev.T @ sample_weight
        self.rule_scores.append(scores)
        return np.argsort(scores)[::-1][:num_inherited]

    def _pad_inherited_rules(self, inherited_a, inherited_sigma, target_dim):
        if inherited_a.size == 0:
            return inherited_a.reshape(0, target_dim), inherited_sigma.reshape(0, target_dim)

        current_dim = inherited_a.shape[1]
        pad_width = target_dim - current_dim
        if pad_width <= 0:
            return inherited_a, inherited_sigma

        inherited_a_padded = np.pad(
            inherited_a, ((0, 0), (0, pad_width)), mode='constant', constant_values=0.0
        )
        inherited_sigma_padded = np.pad(
            inherited_sigma, ((0, 0), (0, pad_width)), mode='constant', constant_values=1e9
        )
        return inherited_a_padded, inherited_sigma_padded

    def _augment_input_fit(self, X_original, layer_output, layer_index):
        if self.use_projection:
            R = self._build_projection_matrix(self.num_classes, self.num_classes)
            self.projection_matrices.append(R)
            projected = layer_output @ R
            return np.concatenate([X_original, self.alpha * projected], axis=1)
        return np.concatenate([X_original, self.alpha * layer_output], axis=1)

    def _augment_input_predict(self, X_original, layer_output, layer_index):
        if self.use_projection:
            projected = layer_output @ self.projection_matrices[layer_index]
            return np.concatenate([X_original, self.alpha * projected], axis=1)
        return np.concatenate([X_original, self.alpha * layer_output], axis=1)

    def _softmax(self, logits):
        shifted = logits - np.max(logits, axis=1, keepdims=True)
        exp_logits = np.exp(shifted)
        return exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

    def _entropy_attention_fusion(self, layer_outputs):
        layer_probs = [self._softmax(output) for output in layer_outputs]
        entropies = []
        normalizer = np.log(self.num_classes)
        for probs in layer_probs:
            entropy = -np.sum(probs * np.log(probs + self.epsilon), axis=1)
            entropies.append(entropy / normalizer)

        entropy_matrix = np.column_stack(entropies)
        attention_logits = -entropy_matrix / self.temperature
        attention_logits -= np.max(attention_logits, axis=1, keepdims=True)
        attention = np.exp(attention_logits)
        attention /= np.sum(attention, axis=1, keepdims=True)

        fused = np.zeros_like(layer_probs[0])
        for layer_idx, probs in enumerate(layer_probs):
            fused += attention[:, [layer_idx]] * probs
        return fused

    def fit(self, X, y):
        Y_onehot = self.enc.fit_transform(y.reshape(-1, 1))
        sample_weight = self._compute_sample_weight(y)

        self.classifiers = []
        self.projection_matrices = []
        self.rule_scores = []

        X_original = X.copy()
        current_X = X.copy()
        layer_inputs = []
        layer_outputs = []
        cumulative_output = np.zeros_like(Y_onehot)

        for layer_idx in range(self.dp_layers):
            layer_inputs.append(current_X.copy())
            tsk = BaseTSK(n_rules=self.n_rules)

            if layer_idx == 0:
                tsk.fit(current_X, Y_onehot, sample_weight=sample_weight)
                layer_output = tsk.predict(current_X)
                cumulative_output += layer_output
                print(f'  [Layer {layer_idx + 1}] Base classifier trained. Rules: {self.n_rules}')
            else:
                num_inherited = int(self.n_rules * self.heritage_ratio)
                if num_inherited == 0 and self.heritage_ratio > 0:
                    num_inherited = 1

                prev_tsk = self.classifiers[layer_idx - 1]
                prev_input = layer_inputs[layer_idx - 1]
                inherited_indices = self._select_inherited_indices(
                    prev_tsk, prev_input, sample_weight, num_inherited
                )
                inherited_a = prev_tsk.a[inherited_indices, :]
                inherited_sigma = prev_tsk.sigma[inherited_indices, :]

                num_generated = max(0, self.n_rules - len(inherited_indices))
                gen_a, gen_sigma = self._generate_random_fuzzy_rules(current_X, num_generated)
                gen_sigma = self._apply_short_rule_mask(gen_sigma)

                inherited_a, inherited_sigma = self._pad_inherited_rules(
                    inherited_a, inherited_sigma, current_X.shape[1]
                )
                tsk.a = np.vstack([inherited_a, gen_a])
                tsk.sigma = np.vstack([inherited_sigma, gen_sigma])

                H = tsk._compute_firing_strength(current_X, tsk.a, tsk.sigma)
                residual_target = Y_onehot - cumulative_output
                tsk.beta = tsk._solve_beta(H, residual_target, sample_weight=sample_weight)
                layer_output = tsk.predict(current_X)
                cumulative_output += layer_output

                print(
                    f'  [Layer {layer_idx + 1}] Residual classifier trained. '
                    f'Inherited {len(inherited_indices)} rules, generated {num_generated} rules.'
                )

            self.classifiers.append(tsk)
            layer_outputs.append(layer_output)

            if layer_idx < self.dp_layers - 1:
                current_X = self._augment_input_fit(X_original, layer_output, layer_idx)

        return self

    def predict_proba(self, X):
        X_original = X.copy()
        current_X = X.copy()
        layer_outputs = []

        for layer_idx, tsk in enumerate(self.classifiers):
            layer_output = tsk.predict(current_X)
            layer_outputs.append(layer_output)
            if layer_idx < len(self.classifiers) - 1:
                current_X = self._augment_input_predict(X_original, layer_output, layer_idx)

        if self.fusion_mode == 'entropy_attention':
            return self._entropy_attention_fusion(layer_outputs)

        layer_probs = [self._softmax(output) for output in layer_outputs]
        return np.mean(layer_probs, axis=0)

    def predict(self, X):
        probs = self.predict_proba(X)
        return np.argmax(probs, axis=1)

