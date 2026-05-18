from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


CLASS_LABELS = ['W', 'N1', 'N2', 'N3', 'R']
CLASS_LABELS_CN = {
    'W': 'W',
    'N1': 'N1',
    'N2': 'N2',
    'N3': 'N3',
    'R': 'REM',
}
FEATURE_KEYS = [
    'DeltaRelPower',
    'ThetaRelPower',
    'AlphaRelPower',
    'BetaRelPower',
    'ThetaAlphaRatio',
    'SEF95',
    'SpectralEntropy',
    'RMS',
    'STD',
    'HjorthActivity',
    'HjorthMobility',
    'HjorthComplexity',
    'WaveformLength',
    'ECG_MeanHR',
    'ECG_SDNN',
    'ECG_RMSSD',
    'ECG_pNN50',
    'ECG_RRCV',
    'ECG_SDSD',
    'ECG_MADRR',
    'ECG_LFHF',
    'ECG_HFNorm',
]
FEATURE_LABELS_CN = [
    'EEG 相对 Delta 波功率',
    'EEG 相对 Theta 波功率',
    'EEG 相对 Alpha 波功率',
    'EEG 相对 Beta 波功率',
    'EEG Theta/Alpha 比值',
    'EEG 频谱边缘频率 SEF95',
    'EEG 频谱熵',
    'EEG 均方根',
    'EEG 标准差',
    'EEG Hjorth 活动度',
    'EEG Hjorth 移动度',
    'EEG Hjorth 复杂度',
    'EEG 波形长度',
    'ECG 平均心率',
    'ECG SDNN',
    'ECG RMSSD',
    'ECG pNN50',
    'ECG RR 变异系数',
    'ECG SDSD',
    'ECG RR 中位绝对偏差',
    'ECG LF/HF 比值',
    'ECG HF 归一化功率',
]
FEATURE_LABEL_MAP = dict(zip(FEATURE_KEYS, FEATURE_LABELS_CN))


def load_joblib_model(path: str | Path):
    return joblib.load(path)


def _softmax(matrix: np.ndarray) -> np.ndarray:
    shifted = matrix - np.max(matrix, axis=1, keepdims=True)
    exp_scores = np.exp(shifted)
    return exp_scores / (np.sum(exp_scores, axis=1, keepdims=True) + 1e-12)


def _linguistic_level(center_value: float) -> str:
    value = float(center_value)
    if value < 0.2:
        return '很低'
    if value < 0.4:
        return '较低'
    if value < 0.6:
        return '中等'
    if value < 0.8:
        return '较高'
    return '很高'


def build_rule_summary(target_class: str, conditions: list[dict[str, Any]]) -> str:
    top_conditions = conditions[:3]
    condition_text = '、'.join(f"{item['feature_label']}{item['linguistic_level']}" for item in top_conditions)
    target_cn = CLASS_LABELS_CN.get(target_class, target_class)
    if condition_text:
        return f'当 {condition_text} 时，规则更倾向于判为 {target_cn}。'
    return f'该规则更倾向于判为 {target_cn}。'


def build_rule_tags(target_class: str, conditions: list[dict[str, Any]]) -> list[str]:
    target_cn = CLASS_LABELS_CN.get(target_class, target_class)
    tags = [target_cn]
    tags.extend(item['feature_label'] for item in conditions[:3])
    return tags


def extract_rules_from_model(model, model_id: int = -1) -> list[dict[str, Any]]:
    if not hasattr(model, 'a') or not hasattr(model, 'sigma') or not hasattr(model, 'beta'):
        raise ValueError('当前模型不支持规则抽取。')

    antecedent_centers = np.asarray(model.a, dtype=float)
    antecedent_sigma = np.asarray(model.sigma, dtype=float)
    if antecedent_centers.ndim != 2 or antecedent_sigma.ndim != 2:
        raise ValueError('规则前件参数格式不正确。')

    if hasattr(model, 'get_rule_class_probabilities'):
        rule_class_probs = np.asarray(model.get_rule_class_probabilities(), dtype=float)
    else:
        rule_class_probs = _softmax(np.asarray(model.beta, dtype=float))

    rules: list[dict[str, Any]] = []
    for rule_idx in range(antecedent_centers.shape[0]):
        class_prob = rule_class_probs[rule_idx]
        dominant_class = CLASS_LABELS[int(np.argmax(class_prob))]
        conditions: list[dict[str, Any]] = []
        for feature_idx, feature_key in enumerate(FEATURE_KEYS):
            center_value = float(antecedent_centers[rule_idx, feature_idx])
            sigma_value = float(antecedent_sigma[rule_idx, feature_idx])
            conditions.append(
                {
                    'feature_key': feature_key,
                    'feature_label': FEATURE_LABEL_MAP[feature_key],
                    'linguistic_level': _linguistic_level(center_value),
                    'a_value': center_value,
                    'sigma_value': sigma_value,
                    'sort_order': feature_idx + 1,
                }
            )

        summary = build_rule_summary(dominant_class, conditions)
        rules.append(
            {
                'model_id': model_id,
                'rule_no': rule_idx + 1,
                'layer_index': 1,
                'rule_type': '蒸馏学生规则',
                'target_class': dominant_class,
                'short_description': summary,
                'detail_title': f'规则 {rule_idx + 1} 的完整解释',
                'consequence_label': f'偏向 {CLASS_LABELS_CN.get(dominant_class, dominant_class)}',
                'consequence_p': float(class_prob[int(np.argmax(class_prob))]),
                'conditions': conditions,
            }
        )
    return rules
