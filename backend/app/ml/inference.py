from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Any
from contextlib import redirect_stdout
from functools import lru_cache

import mne
import numpy as np
import wfdb

from ..config import ARTIFACT_ROOT, CLASS_LABELS, DATA_ROOT
from .rule_utils import load_joblib_model


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from data_processor import (
        _find_signal_index,
        butter_bandpass_filter,
        build_dataset_bundle,
        extract_ecg_hrv_features_optimized,
        extract_engineered_eeg_features,
        get_label_mapping,
        select_preferred_eeg_index,
        wavelet_denoise,
    )
    from predict_btd_tsk import apply_sleep_jump_smoothing, compute_metrics
except ImportError as exc:  # pragma: no cover
    raise RuntimeError('无法导入当前项目所需的模型推理依赖。') from exc


FINAL_SEED = 42
DATASET_CONFIGS = {
    'Data-A': ['slp01a', 'slp02a', 'slp02b', 'slp14', 'slp32', 'slp37', 'slp41', 'slp45', 'slp60'],
    'Data-B': ['slp01b', 'slp03', 'slp04', 'slp16', 'slp48', 'slp59', 'slp61', 'slp66', 'slp67x'],
}
DATASET_CONFIGS['Data-All'] = DATASET_CONFIGS['Data-A'] + DATASET_CONFIGS['Data-B']
CLASS_LABELS_CN = {
    'W': 'W',
    'N1': 'N1',
    'N2': 'N2',
    'N3': 'N3',
    'R': 'REM',
}
DEFAULT_C4_EEG_PREFERENCES = (
    'EEG (C4-A1)',
    'C4-A1',
    'EEG C4-A1',
    'EEG C4-M1',
    'C4-M1',
    'PSG_C4',
    'C4',
)


def _format_stage_cn(stage_label: str | None, with_stage: bool = False) -> str:
    label = stage_label or 'N2'
    base = CLASS_LABELS_CN.get(label, label)
    if with_stage:
        return f'{base}阶段'
    return base


def _infer_dataset_name(model_path: str | Path) -> str:
    stem = Path(model_path).stem
    for dataset_name in DATASET_CONFIGS:
        if dataset_name in stem:
            return dataset_name
    return 'Data-All'


@lru_cache(maxsize=len(DATASET_CONFIGS))
def _build_training_scaler(dataset_name: str):
    with redirect_stdout(io.StringIO()):
        bundle = build_dataset_bundle(
            data_dir=str(DATA_ROOT),
            record_names=DATASET_CONFIGS[dataset_name],
            test_size=0.25,
            random_state=FINAL_SEED,
        )
    return bundle['scaler']


def _get_model_scaler(model, dataset_name: str):
    scaler = getattr(model, 'feature_scaler', None)
    if scaler is not None:
        return scaler
    return _build_training_scaler(dataset_name)


def _get_model_eeg_preferences(model) -> tuple[str, ...] | None:
    preferences = getattr(model, 'preferred_eeg_channels', None)
    if preferences is None:
        return DEFAULT_C4_EEG_PREFERENCES
    return tuple(str(item) for item in preferences if str(item).strip())


def _find_record_stem(upload_dir: Path) -> tuple[str | None, str | None]:
    edf_files = sorted(upload_dir.glob('*.edf'))
    if edf_files:
        return 'edf', edf_files[0].stem

    hea_files = sorted(upload_dir.glob('*.hea'))
    dat_files = {path.stem for path in upload_dir.glob('*.dat')}
    if not hea_files:
        return None, None
    for hea_path in hea_files:
        if hea_path.stem in dat_files:
            return 'wfdb', hea_path.stem
    return None, None


def _annotation_to_label(description: str) -> int | None:
    if description is None:
        return None
    text = str(description).replace('\x00', '').strip()
    if not text:
        return None
    head = text.split()[0]
    label_map = get_label_mapping()
    return label_map.get(head)


def _extract_epoch_features(eeg_epoch: np.ndarray, ecg_epoch: np.ndarray | None, fs: float) -> np.ndarray:
    eeg_filtered = butter_bandpass_filter(eeg_epoch, lowcut=0.5, highcut=30.0, fs=fs)
    eeg_denoised = wavelet_denoise(eeg_filtered, wavelet='db6')
    eeg_features = extract_engineered_eeg_features(eeg_denoised, fs)
    ecg_features = np.zeros(9, dtype=float) if ecg_epoch is None else extract_ecg_hrv_features_optimized(ecg_epoch, fs)
    return np.concatenate([eeg_features, ecg_features], axis=0)


def _load_wfdb_epoch_features(
    upload_dir: Path,
    record_stem: str,
    preferred_eeg_channels: tuple[str, ...] | None = None,
) -> tuple[np.ndarray, np.ndarray | None, list[dict[str, Any]], dict[str, Any]]:
    record = wfdb.rdrecord(str(upload_dir / record_stem))
    fs = float(record.fs)
    eeg_idx = select_preferred_eeg_index(record.sig_name, preferred_names=preferred_eeg_channels)
    if eeg_idx == -1:
        raise ValueError(f'无适配通道：记录 {record_stem} 中未找到可用的 C4 EEG 通道。')
    ecg_idx = _find_signal_index(record.sig_name, ['ECG', 'EKG'])
    if ecg_idx == -1:
        raise ValueError(f'无适配通道：记录 {record_stem} 中未找到 ECG 通道。')
    eeg_signal = np.asarray(record.p_signal[:, eeg_idx], dtype=float)
    ecg_signal = np.asarray(record.p_signal[:, ecg_idx], dtype=float) if ecg_idx != -1 else None

    annotation = None
    annotation_path = upload_dir / f'{record_stem}.st'
    if annotation_path.exists():
        annotation = wfdb.rdann(str(upload_dir / record_stem), 'st')

    epoch_length = int(30 * fs)
    X_rows: list[np.ndarray] = []
    y_rows: list[int] = []
    metadata: list[dict[str, Any]] = []

    if annotation is not None and len(annotation.sample) > 0:
        sample_points = annotation.sample
        descriptions = list(annotation.aux_note) if hasattr(annotation, 'aux_note') else [''] * len(sample_points)
        for idx, sample_idx in enumerate(sample_points):
            if sample_idx + epoch_length > len(eeg_signal):
                continue
            label = _annotation_to_label(descriptions[idx] if idx < len(descriptions) else '')
            eeg_epoch = eeg_signal[sample_idx: sample_idx + epoch_length]
            ecg_epoch = None if ecg_signal is None else ecg_signal[sample_idx: sample_idx + epoch_length]
            X_rows.append(_extract_epoch_features(eeg_epoch, ecg_epoch, fs))
            if label is not None:
                y_rows.append(label)
            metadata.append(
                {
                    'record_name': record_stem,
                    'sequence_index': len(metadata),
                    'sample_index': int(sample_idx),
                    'time_sec': float(sample_idx / fs),
                }
            )
        y_array = np.asarray(y_rows, dtype=int) if len(y_rows) == len(X_rows) else None
    else:
        total_epochs = len(eeg_signal) // epoch_length
        for epoch_idx in range(total_epochs):
            start = epoch_idx * epoch_length
            end = start + epoch_length
            eeg_epoch = eeg_signal[start:end]
            ecg_epoch = None if ecg_signal is None else ecg_signal[start:end]
            X_rows.append(_extract_epoch_features(eeg_epoch, ecg_epoch, fs))
            metadata.append(
                {
                    'record_name': record_stem,
                    'sequence_index': epoch_idx,
                    'sample_index': start,
                    'time_sec': float(start / fs),
                }
            )
        y_array = None

    preview = {
        'recordName': record_stem,
        'samplingRate': fs,
        'signalNames': list(record.sig_name),
        'p_signal': np.asarray(record.p_signal, dtype=float),
        'eegIndex': eeg_idx,
        'ecgIndex': ecg_idx,
    }
    return np.asarray(X_rows, dtype=float), y_array, metadata, preview


def _load_edf_epoch_features(
    upload_dir: Path,
    record_stem: str,
    preferred_eeg_channels: tuple[str, ...] | None = None,
) -> tuple[np.ndarray, np.ndarray | None, list[dict[str, Any]], dict[str, Any]]:
    edf_path = upload_dir / f'{record_stem}.edf'
    raw = mne.io.read_raw_edf(str(edf_path), preload=True, verbose='ERROR')
    fs = float(raw.info['sfreq'])
    ch_names = list(raw.ch_names)
    eeg_idx = select_preferred_eeg_index(ch_names, preferred_names=preferred_eeg_channels)
    if eeg_idx == -1:
        raise ValueError(f'无适配通道：记录 {record_stem} 中未找到可用的 C4 EEG 通道。')
    ecg_idx = _find_signal_index(ch_names, ['ECG', 'EKG'])
    if ecg_idx == -1:
        raise ValueError(f'无适配通道：记录 {record_stem} 中未找到 ECG 通道。')
    signal_matrix = raw.get_data().T
    eeg_signal = np.asarray(signal_matrix[:, eeg_idx], dtype=float)
    ecg_signal = np.asarray(signal_matrix[:, ecg_idx], dtype=float) if ecg_idx != -1 else None

    annotation_map: dict[int, int] = {}
    if raw.annotations is not None and len(raw.annotations) > 0:
        for onset, description in zip(raw.annotations.onset, raw.annotations.description):
            label = _annotation_to_label(description)
            if label is None:
                continue
            annotation_map[int(round(float(onset) / 30.0))] = label

    epoch_length = int(30 * fs)
    total_epochs = len(eeg_signal) // epoch_length
    X_rows: list[np.ndarray] = []
    y_rows: list[int] = []
    metadata: list[dict[str, Any]] = []
    has_complete_labels = bool(annotation_map) and len(annotation_map) >= total_epochs

    for epoch_idx in range(total_epochs):
        start = epoch_idx * epoch_length
        end = start + epoch_length
        eeg_epoch = eeg_signal[start:end]
        ecg_epoch = None if ecg_signal is None else ecg_signal[start:end]
        X_rows.append(_extract_epoch_features(eeg_epoch, ecg_epoch, fs))
        if has_complete_labels:
            y_rows.append(annotation_map.get(epoch_idx, 0))
        metadata.append(
            {
                'record_name': record_stem,
                'sequence_index': epoch_idx,
                'sample_index': start,
                'time_sec': float(start / fs),
            }
        )

    preview = {
        'recordName': record_stem,
        'samplingRate': fs,
        'signalNames': ch_names,
        'p_signal': signal_matrix,
        'eegIndex': eeg_idx,
        'ecgIndex': ecg_idx,
    }
    y_array = np.asarray(y_rows, dtype=int) if has_complete_labels else None
    return np.asarray(X_rows, dtype=float), y_array, metadata, preview


def _load_uploaded_feature_matrix(upload_dir: Path, preferred_eeg_channels: tuple[str, ...] | None = None):
    record_type, record_stem = _find_record_stem(upload_dir)
    if not record_type or not record_stem:
        raise ValueError('未在上传目录中找到可用的记录文件。')
    if record_type == 'wfdb':
        return _load_wfdb_epoch_features(upload_dir, record_stem, preferred_eeg_channels=preferred_eeg_channels)
    return _load_edf_epoch_features(upload_dir, record_stem, preferred_eeg_channels=preferred_eeg_channels)


def _downsample_signal(signal: np.ndarray, max_points: int = 480) -> list[float]:
    if signal.size == 0:
        return []
    target_points = min(int(max_points), int(signal.size))
    if target_points <= 1:
        return [float(signal[0])]
    src_x = np.linspace(0.0, 1.0, signal.size)
    dst_x = np.linspace(0.0, 1.0, target_points)
    resampled = np.interp(dst_x, src_x, signal.astype(float))
    return [float(value) for value in resampled]


def extract_waveform_preview(upload_dir: Path, preview_seconds: float = 30.0, max_points: int = 480) -> dict[str, Any]:
    _, _, _, preview = _load_uploaded_feature_matrix(upload_dir)
    fs = float(preview['samplingRate'])
    sample_count = min(int(preview_seconds * fs), int(preview['p_signal'].shape[0]))
    preview_signal = preview['p_signal'][:sample_count]

    def build_channel(index: int, default_name: str) -> dict[str, Any]:
        if index == -1:
            return {'channel': default_name, 'points': [], 'sampleCount': 0, 'durationSeconds': 0.0}
        channel_signal = np.asarray(preview_signal[:, index], dtype=float)
        return {
            'channel': preview['signalNames'][index],
            'points': _downsample_signal(channel_signal, max_points=max_points),
            'sampleCount': int(channel_signal.size),
            'durationSeconds': float(channel_signal.size / fs) if fs > 0 else 0.0,
        }

    return {
        'recordName': preview['recordName'],
        'samplingRate': fs,
        'windowSeconds': float(sample_count / fs) if fs > 0 else 0.0,
        'eeg': build_channel(preview['eegIndex'], 'EEG'),
        'ecg': build_channel(preview['ecgIndex'], 'ECG'),
    }


def _summarize_stage_distribution(final_labels: np.ndarray) -> list[dict[str, Any]]:
    counts = np.bincount(final_labels.astype(int), minlength=len(CLASS_LABELS))
    total = max(int(np.sum(counts)), 1)
    return [{'label': label, 'value': float(counts[idx] * 100.0 / total)} for idx, label in enumerate(CLASS_LABELS)]


def _format_stage_ratio(stage_label: str, ratio: float | None, with_stage: bool = True) -> str:
    stage_text = _format_stage_cn(stage_label, with_stage=with_stage)
    if ratio is None:
        return stage_text
    return f'{stage_text}（{ratio:.1f}%）'


def _compose_diagnosis_texts(
    risk: str,
    dominant: str,
    focus: str,
    stage_map: dict[str, float] | None = None,
) -> dict[str, str]:
    stage_map = stage_map or {}
    dominant_ratio = stage_map.get(dominant)
    focus_ratio = stage_map.get(focus)

    ordered = sorted(stage_map.items(), key=lambda item: item[1], reverse=True) if stage_map else []
    secondary = ordered[1][0] if len(ordered) > 1 else None
    secondary_ratio = ordered[1][1] if len(ordered) > 1 else None

    dominant_text = _format_stage_ratio(dominant, dominant_ratio, with_stage=True)
    focus_text = _format_stage_ratio(focus, focus_ratio, with_stage=True)
    secondary_text = _format_stage_ratio(secondary, secondary_ratio, with_stage=True) if secondary else None

    if stage_map:
        if secondary_text:
            summary = f'主导阶段为 {dominant_text}，其次为 {secondary_text}，当前重点关注 {focus_text}。'
        else:
            summary = f'主导阶段为 {dominant_text}，当前重点关注 {focus_text}。'
    else:
        summary = f'主导阶段为 {_format_stage_cn(dominant, with_stage=True)}，当前重点关注 {_format_stage_cn(focus, with_stage=True)}。'

    if risk == '高风险':
        if focus == 'W':
            conclusion = f'W阶段占比达到 {focus_text}，提示夜间觉醒偏多，睡眠连续性较差。'
            advice = f'建议重点关注夜间觉醒和睡眠维持情况。若连续多次监测仍表现为 {focus_text}，可进一步结合主诉与临床评估判断是否存在睡眠维持障碍。'
        elif focus == 'N3':
            conclusion = f'当前以 {dominant_text} 为主，但 {focus_text} 占比偏低，提示深睡眠不足。'
            advice = f'建议重点关注深睡眠恢复情况。若多次结果均显示 {focus_text} 偏低，可进一步结合日间困倦、疲劳感等情况综合评估。'
        else:
            conclusion = f'当前睡眠结构以 {dominant_text} 为主，但 {focus_text} 表现异常，提示睡眠结构紊乱风险较高。'
            advice = f'建议结合重点阶段 {focus_text} 的变化趋势持续观察，并根据连续监测结果考虑进一步评估。'
    elif risk == '中风险':
        if focus == 'N3':
            conclusion = f'当前睡眠结构以 {dominant_text} 为主，但 {focus_text} 略低，提示睡眠恢复质量可能受到一定影响。'
            advice = f'建议继续关注深睡眠阶段变化，并结合后续监测结果判断是否存在持续性深睡眠不足。'
        elif focus in {'N1', 'R'}:
            conclusion = f'当前睡眠结构整体可辨，但 {focus_text} 占比偏高，提示阶段分布存在一定波动。'
            advice = f'建议继续观察 {focus_text} 的变化趋势，并结合连续记录评估睡眠结构是否稳定。'
        else:
            conclusion = f'当前睡眠结构以 {dominant_text} 为主，整体风险中等，重点关注 {focus_text} 的后续变化。'
            advice = f'建议结合阶段占比与多次监测结果持续观察 {focus_text}，必要时再进行进一步分析。'
    else:
        conclusion = f'整体睡眠结构较为稳定，目前以 {dominant_text} 为主，未见明显异常风险。'
        advice = f'建议继续保持规律作息，并结合后续监测结果观察 {_format_stage_cn(focus, with_stage=True)} 的波动情况。'

    return {
        'conclusion': conclusion,
        'summary': summary,
        'advice': advice,
    }


def _build_summary(stage_stats: list[dict[str, Any]]) -> dict[str, str]:
    dominant = max(stage_stats, key=lambda item: item['value'])['label'] if stage_stats else 'N2'
    stage_map = {item['label']: item['value'] for item in stage_stats}
    focus = dominant
    risk = '低风险'

    if stage_map.get('W', 0.0) >= 25.0:
        focus = 'W'
        risk = '高风险'
    elif stage_map.get('N3', 0.0) < 8.0:
        focus = 'N3'
        risk = '高风险'
    elif stage_map.get('R', 0.0) >= 22.0 or stage_map.get('N1', 0.0) >= 12.0:
        focus = 'R' if stage_map.get('R', 0.0) >= stage_map.get('N1', 0.0) else 'N1'
        risk = '中风险'

    texts = _compose_diagnosis_texts(risk, dominant, focus, stage_map=stage_map)
    return {
        'risk': risk,
        'dominant_stage': dominant,
        'focus_class': focus,
        'conclusion': texts['conclusion'],
        'summary': texts['summary'],
        'advice': texts['advice'],
    }


def _build_prediction_rows(
    metadata: list[dict[str, Any]],
    y_true: np.ndarray | None,
    raw_labels: np.ndarray,
    final_labels: np.ndarray,
    final_probabilities: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(metadata):
        rows.append(
            {
                'epoch_index': int(item['sequence_index']),
                'sample_index': int(item['sample_index']),
                'time_sec': float(item['time_sec']),
                'true_label': None if y_true is None else CLASS_LABELS[int(y_true[idx])],
                'pred_raw': CLASS_LABELS[int(raw_labels[idx])],
                'pred_final': CLASS_LABELS[int(final_labels[idx])],
                'prob_w': float(final_probabilities[idx, 0]),
                'prob_n1': float(final_probabilities[idx, 1]),
                'prob_n2': float(final_probabilities[idx, 2]),
                'prob_n3': float(final_probabilities[idx, 3]),
                'prob_r': float(final_probabilities[idx, 4]),
            }
        )
    return rows


def _write_prediction_csv(rows: list[dict[str, Any]], save_path: Path) -> None:
    fieldnames = [
        'epoch_index',
        'sample_index',
        'time_sec',
        'true_label',
        'pred_raw',
        'pred_final',
        'prob_w',
        'prob_n1',
        'prob_n2',
        'prob_n3',
        'prob_r',
    ]
    with save_path.open('w', newline='', encoding='utf-8-sig') as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def extract_rule_activations(
    model_path: str | Path,
    upload_dir: Path,
    scaler=None,
    model=None,
    X_scaled: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    dataset_name = _infer_dataset_name(model_path)
    if model is None:
        model = load_joblib_model(model_path)
    if scaler is None:
        scaler = _get_model_scaler(model, dataset_name)
    if X_scaled is None:
        X_raw, _, _, _ = _load_uploaded_feature_matrix(
            upload_dir,
            preferred_eeg_channels=_get_model_eeg_preferences(model),
        )
        X_scaled = scaler.transform(X_raw)
    activations = model.compute_rule_activations(X_scaled)
    mean_activation = np.mean(activations, axis=0)
    rule_probs = model.get_rule_class_probabilities()
    order = np.argsort(-mean_activation)
    rows = []
    for rank_order, rule_idx in enumerate(order, start=1):
        rows.append(
            {
                'layer_index': 1,
                'rule_no': int(rule_idx + 1),
                'activation_strength': float(mean_activation[rule_idx]),
                'target_class': CLASS_LABELS[int(np.argmax(rule_probs[rule_idx]))],
                'rank_order': rank_order,
            }
        )
    return rows


def repair_diagnosis_texts(
    risk: str | None,
    dominant_stage: str | None,
    focus_class: str | None,
    conclusion: str | None,
    summary: str | None,
    advice: str | None,
) -> dict[str, str]:
    fixed = {
        'risk': risk or '待评估',
        'dominant_stage': dominant_stage or 'N2',
        'focus_class': focus_class or dominant_stage or 'N2',
        'conclusion': conclusion or '',
        'summary': summary or '',
        'advice': advice or '',
    }

    rebuilt = _compose_diagnosis_texts(
        fixed['risk'],
        fixed['dominant_stage'],
        fixed['focus_class'],
        stage_map=None,
    )

    legacy_markers = ['???', '????', '未找到']

    def should_replace(text: str) -> bool:
        if not text:
            return True
        if '?' in text or '\ufffd' in text:
            return True
        return any(marker in text for marker in legacy_markers)

    if should_replace(fixed['conclusion']):
        fixed['conclusion'] = rebuilt['conclusion']
    if should_replace(fixed['summary']):
        fixed['summary'] = rebuilt['summary']
    if should_replace(fixed['advice']):
        fixed['advice'] = rebuilt['advice']
    return fixed


def run_diagnosis(model_path: str | Path, upload_dir: Path, run_code: str) -> dict[str, Any]:
    dataset_name = _infer_dataset_name(model_path)
    model = load_joblib_model(model_path)
    scaler = _get_model_scaler(model, dataset_name)

    X_raw, y_true, metadata, _ = _load_uploaded_feature_matrix(
        upload_dir,
        preferred_eeg_channels=_get_model_eeg_preferences(model),
    )
    if len(X_raw) == 0:
        raise ValueError('上传数据未提取到有效样本。')

    X_scaled = scaler.transform(X_raw)
    raw_probabilities = np.asarray(model.predict_proba(X_scaled), dtype=float)
    raw_labels, final_labels, final_probabilities = apply_sleep_jump_smoothing(raw_probabilities, window_radius=2)

    stage_stats = _summarize_stage_distribution(final_labels)
    summary = _build_summary(stage_stats)
    metrics = None
    if y_true is not None and len(y_true) == len(final_labels):
        metric_rows = compute_metrics(y_true, final_labels)
        metrics = {
            'oa': float(metric_rows['oa']),
            'mean_sensitivity': float(metric_rows['mean_sensitivity']),
            'macro_f1': float(metric_rows['macro_f1']),
        }

    prediction_rows = _build_prediction_rows(metadata, y_true, raw_labels, final_labels, final_probabilities)
    artifact_dir = ARTIFACT_ROOT / run_code
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_csv_path = artifact_dir / 'predictions.csv'
    _write_prediction_csv(prediction_rows, artifact_csv_path)

    return {
        'summary': summary,
        'stage_stats': stage_stats,
        'rule_activations': extract_rule_activations(
            model_path,
            upload_dir,
            scaler=scaler,
            model=model,
            X_scaled=X_scaled,
        ),
        'predictions': prediction_rows,
        'metrics': metrics,
        'artifact_csv_path': str(artifact_csv_path),
    }
