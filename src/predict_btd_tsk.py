from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import joblib
import mne
import numpy as np

from data_processor import (
    ECG_HRV_FEATURE_DIM_OPT,
    butter_bandpass_filter,
    extract_ecg_hrv_features_optimized,
    extract_engineered_eeg_features,
    wavelet_denoise,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "btd_tsk_student.joblib"
EXTERNAL_ROOT = PROJECT_ROOT / "data" / "haaglanden-medisch-centrum-sleep-staging-database-1.1" / "recordings"
RESULT_DIR = PROJECT_ROOT / "result"
CLASS_LABELS = ["W", "N1", "N2", "N3", "REM"]
# 在这里填写默认预测记录，例如 "SN022.edf"；留空则按随机方式选择。
DEFAULT_RECORD = "SN003.edf"
SCORING_MAP = {
    "W": "W",
    "WAKE": "W",
    "0": "W",
    "N1": "N1",
    "1": "N1",
    "N2": "N2",
    "2": "N2",
    "N3": "N3",
    "3": "N3",
    "4": "N3",
    "R": "REM",
    "REM": "REM",
}


def normalize_stage(stage_token: str) -> str:
    text = str(stage_token).strip().upper().replace("SLEEP STAGE", "").strip()
    return SCORING_MAP.get(text, "")


def discover_available_records(data_root: Path) -> list[str]:
    return [
        path.name
        for path in sorted(data_root.glob("SN*.edf"))
        if not path.name.endswith("_sleepscoring.edf")
    ]


def choose_random_record(data_root: Path, seed: int = 42) -> str:
    records = discover_available_records(data_root)
    if not records:
        raise ValueError(f"No EDF records found in {data_root}")
    rng = random.Random(seed)
    return rng.choice(records)


def resolve_record_name(record_value: str | None, data_root: Path, seed: int = 42) -> str:
    """解析待预测记录名；未指定时默认随机选择一条记录。"""
    if not record_value:
        if DEFAULT_RECORD:
            return resolve_record_name(DEFAULT_RECORD, data_root, seed=seed)
        return choose_random_record(data_root, seed=seed)

    record_text = str(record_value).strip()
    if not record_text:
        if DEFAULT_RECORD:
            return resolve_record_name(DEFAULT_RECORD, data_root, seed=seed)
        return choose_random_record(data_root, seed=seed)

    record_path = Path(record_text)
    if record_path.exists():
        return record_path.name

    candidate_name = record_text if record_text.lower().endswith(".edf") else f"{record_text}.edf"
    candidate_path = data_root / candidate_name
    if not candidate_path.exists():
        raise ValueError(f"指定的记录文件不存在：{candidate_name}")
    return candidate_name


def parse_scoring_file(scoring_path: Path, fs: float) -> list[tuple[int, int]]:
    epochs: list[tuple[int, int]] = []
    with scoring_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
        for row in reader:
            row = {str(key).strip(): value for key, value in row.items()}
            annotation = str(row.get("Annotation", "")).strip()
            if not annotation.startswith("Sleep stage"):
                continue
            stage_token = annotation.replace("Sleep stage", "", 1).strip()
            normalized = normalize_stage(stage_token)
            if normalized not in CLASS_LABELS:
                continue
            onset_seconds = float(row.get("Recording onset", "0") or 0)
            duration_seconds = float(row.get("Duration", "0") or 0)
            if duration_seconds <= 0:
                continue
            sample_idx = int(round(onset_seconds * fs))
            epochs.append((sample_idx, CLASS_LABELS.index(normalized)))
    return epochs


def select_channel_indices(ch_names: list[str], preferred_eeg_channels: list[str], preferred_ecg_keywords: list[str]) -> tuple[int, int]:
    normalized_names = {str(name).upper(): idx for idx, name in enumerate(ch_names)}
    eeg_index = -1
    for preferred in preferred_eeg_channels:
        idx = normalized_names.get(str(preferred).upper())
        if idx is not None:
            eeg_index = idx
            break
    if eeg_index == -1:
        for idx, name in enumerate(ch_names):
            upper_name = str(name).upper()
            if "EEG" in upper_name and "C4" in upper_name:
                eeg_index = idx
                break
    if eeg_index == -1:
        raise ValueError(f"无适配通道：未找到可用的 C4 EEG 通道。可用通道: {ch_names}")

    ecg_index = -1
    upper_keywords = [keyword.upper() for keyword in preferred_ecg_keywords]
    for idx, name in enumerate(ch_names):
        upper_name = str(name).upper()
        if any(keyword in upper_name for keyword in upper_keywords):
            ecg_index = idx
            break
    if ecg_index == -1:
        raise ValueError(f"无适配通道：未找到 ECG 通道。可用通道: {ch_names}")
    return eeg_index, ecg_index


def extract_record_features(record_name: str, preferred_eeg_channels: list[str], preferred_ecg_keywords: list[str]) -> tuple[np.ndarray, np.ndarray, list[dict[str, object]]]:
    record_path = EXTERNAL_ROOT / record_name
    scoring_path = EXTERNAL_ROOT / record_name.replace(".edf", "_sleepscoring.txt")
    raw = mne.io.read_raw_edf(str(record_path), preload=False, verbose="ERROR")
    fs = float(raw.info["sfreq"])
    eeg_index, ecg_index = select_channel_indices(raw.ch_names, preferred_eeg_channels, preferred_ecg_keywords)

    signals = raw.get_data(picks=[eeg_index, ecg_index])
    eeg_signal = np.asarray(signals[0], dtype=float)
    ecg_signal = np.asarray(signals[1], dtype=float)
    epoch_len = int(round(30 * fs))
    epochs = parse_scoring_file(scoring_path, fs)

    x_rows: list[np.ndarray] = []
    y_rows: list[int] = []
    metadata: list[dict[str, object]] = []
    for sample_idx, label_id in epochs:
        if sample_idx < 0 or sample_idx + epoch_len > len(eeg_signal):
            continue
        eeg_epoch = eeg_signal[sample_idx:sample_idx + epoch_len]
        eeg_filtered = butter_bandpass_filter(eeg_epoch, lowcut=0.5, highcut=30.0, fs=fs)
        eeg_denoised = wavelet_denoise(eeg_filtered, wavelet="db6")
        eeg_features = extract_engineered_eeg_features(eeg_denoised, fs)

        ecg_epoch = ecg_signal[sample_idx:sample_idx + epoch_len]
        ecg_features = extract_ecg_hrv_features_optimized(ecg_epoch, fs)
        if len(ecg_features) != ECG_HRV_FEATURE_DIM_OPT:
            raise ValueError("Unexpected ECG feature dimension.")

        x_rows.append(np.concatenate([eeg_features, ecg_features], axis=0))
        y_rows.append(label_id)
        metadata.append(
            {
                "record_name": record_name,
                "sequence_index": len(metadata),
                "time_sec": float(sample_idx / fs),
                "true_label": CLASS_LABELS[label_id],
            }
        )

    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int), metadata


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, object]:
    cm = np.zeros((len(CLASS_LABELS), len(CLASS_LABELS)), dtype=int)
    for true_label, pred_label in zip(y_true, y_pred):
        cm[int(true_label), int(pred_label)] += 1
    total = int(np.sum(cm))
    oa = float(np.trace(cm) / total) if total > 0 else 0.0
    recalls = []
    for class_idx in range(len(CLASS_LABELS)):
        tp = cm[class_idx, class_idx]
        fn = np.sum(cm[class_idx, :]) - tp
        recalls.append(float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0)
    macro_f1 = []
    for class_idx in range(len(CLASS_LABELS)):
        tp = cm[class_idx, class_idx]
        fp = np.sum(cm[:, class_idx]) - tp
        fn = np.sum(cm[class_idx, :]) - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        macro_f1.append(0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall))
    return {
        "oa": oa,
        "mean_sensitivity": float(np.mean(recalls)),
        "macro_f1": float(np.mean(macro_f1)),
        "cm": cm,
    }


def apply_sleep_jump_smoothing(probabilities: np.ndarray, window_radius: int = 2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """对逐 epoch 概率做局部平滑，减少不合理的单点跳变。"""
    probs = np.asarray(probabilities, dtype=float)
    if probs.ndim != 2 or probs.shape[0] == 0:
        raise ValueError("概率矩阵为空或维度不正确。")

    raw_labels = np.argmax(probs, axis=1).astype(int)
    if window_radius <= 0 or probs.shape[0] == 1:
        row_sum = probs.sum(axis=1, keepdims=True)
        normalized = np.divide(probs, row_sum, out=np.zeros_like(probs), where=row_sum > 0)
        return raw_labels, raw_labels.copy(), normalized

    smoothed = np.zeros_like(probs, dtype=float)
    total = probs.shape[0]
    for idx in range(total):
        start = max(0, idx - window_radius)
        end = min(total, idx + window_radius + 1)
        local_probs = probs[start:end]
        local_weights = np.ones(end - start, dtype=float)
        local_center = idx - start
        for pos in range(end - start):
            distance = abs(pos - local_center)
            local_weights[pos] = 1.0 / (1.0 + distance)
        weighted_sum = np.sum(local_probs * local_weights[:, None], axis=0)
        smoothed[idx] = weighted_sum / np.sum(local_weights)

    row_sum = smoothed.sum(axis=1, keepdims=True)
    normalized = np.divide(smoothed, row_sum, out=np.zeros_like(smoothed), where=row_sum > 0)
    final_labels = np.argmax(normalized, axis=1).astype(int)

    # 若单个 epoch 与前后两个同标签片段冲突，则回填为邻域主导类别。
    if total >= 3:
        adjusted = final_labels.copy()
        for idx in range(1, total - 1):
            prev_label = adjusted[idx - 1]
            next_label = adjusted[idx + 1]
            current_label = adjusted[idx]
            if prev_label == next_label and current_label != prev_label:
                adjusted[idx] = prev_label
        final_labels = adjusted

    return raw_labels, final_labels, normalized


def write_outputs(record_name: str, metadata: list[dict[str, object]], y_true: np.ndarray, y_pred: np.ndarray, probabilities: np.ndarray) -> tuple[Path, Path]:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stem = record_name.replace(".edf", "")
    csv_path = RESULT_DIR / f"prediction_{stem}.csv"
    txt_path = RESULT_DIR / f"prediction_{stem}.txt"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["record_name", "sequence_index", "time_sec", "true_label", "pred_label", "confidence"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item, pred_id, prob in zip(metadata, y_pred, probabilities):
            writer.writerow(
                {
                    "record_name": item["record_name"],
                    "sequence_index": item["sequence_index"],
                    "time_sec": f"{float(item['time_sec']):.2f}",
                    "true_label": item["true_label"],
                    "pred_label": CLASS_LABELS[int(pred_id)],
                    "confidence": f"{float(np.max(prob)):.6f}",
                }
            )

    metrics = compute_metrics(y_true, y_pred)
    counts_true = np.bincount(y_true, minlength=len(CLASS_LABELS))
    counts_pred = np.bincount(y_pred, minlength=len(CLASS_LABELS))
    lines = []
    lines.append("=== 外部记录预测结果 ===\n\n")
    lines.append(f"记录文件: {record_name}\n")
    lines.append(
        f"评估指标: OA={metrics['oa'] * 100:.2f}% | MeanSen={metrics['mean_sensitivity'] * 100:.2f}% | MacroF1={metrics['macro_f1'] * 100:.2f}%\n\n"
    )
    lines.append("真实标签分布:\n")
    for label, count in zip(CLASS_LABELS, counts_true):
        lines.append(f"  {label}: {int(count)}\n")
    lines.append("\n预测标签分布:\n")
    for label, count in zip(CLASS_LABELS, counts_pred):
        lines.append(f"  {label}: {int(count)}\n")
    txt_path.write_text("".join(lines), encoding="utf-8-sig")
    return csv_path, txt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="使用论文主线 BTD-TSK 模型预测外部 C4+ECG 睡眠记录。")
    parser.add_argument("--model", type=Path, default=MODEL_PATH, help="Path to the trained BTD-TSK student model.")
    parser.add_argument("--record", type=str, default="", help="指定记录文件名或完整路径，例如 SN001.edf；留空时默认随机选择。")
    parser.add_argument("--file", type=str, default="", help="与 --record 等价，用于显式指定待预测的 EDF 文件。")
    parser.add_argument("--seed", type=int, default=42, help="Random seed used when selecting a random record.")
    args = parser.parse_args()

    model = joblib.load(args.model)
    preferred_eeg_channels = list(getattr(model, "preferred_eeg_channels", ["EEG C4-M1", "C4-M1"]))
    preferred_ecg_keywords = list(getattr(model, "preferred_ecg_keywords", ["ECG", "EKG"]))
    scaler = getattr(model, "feature_scaler", None)
    if scaler is None:
        raise ValueError("Loaded model does not contain a feature scaler.")

    record_name = resolve_record_name(args.file or args.record, EXTERNAL_ROOT, seed=args.seed)
    x_raw, y_true, metadata = extract_record_features(record_name, preferred_eeg_channels, preferred_ecg_keywords)
    x_scaled = scaler.transform(x_raw)
    probabilities = model.predict_proba(x_scaled)
    predictions = np.argmax(probabilities, axis=1)
    csv_path, txt_path = write_outputs(record_name, metadata, y_true, predictions, probabilities)
    print(f"已选择记录：{record_name}")
    print(csv_path)
    print(txt_path)


if __name__ == "__main__":
    main()
