import argparse
import csv
from pathlib import Path

import joblib
import numpy as np

from data_processor import build_dataset_bundle, process_record_with_metadata
from train_btd_tsk_distill import DATASET_CONFIGS, FINAL_SEED

CLASS_LABELS = ['W', 'N1', 'N2', 'N3', 'R']
CLASS_LABELS_CN = ['清醒(W)', 'N1', 'N2', 'N3', 'REM(R)']

# 仅约束通常不应直接发生的跳变
IMPOSSIBLE_TRANSITIONS = {
    (0, 3),  # W -> N3
    (3, 0),  # N3 -> W
    (1, 3),  # N1 -> N3
    (3, 1),  # N3 -> N1
    (3, 4),  # N3 -> R
    (4, 3),  # R -> N3
}


def compute_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    num_classes = len(CLASS_LABELS)
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for true_label, pred_label in zip(y_true, y_pred):
        cm[true_label, pred_label] += 1

    total = np.sum(cm)
    oa = np.trace(cm) / total if total > 0 else 0.0
    sensitivity = []
    for class_idx in range(num_classes):
        tp = cm[class_idx, class_idx]
        fn = np.sum(cm[class_idx, :]) - tp
        sen = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        sensitivity.append(sen)

    f1_list = []
    for class_idx in range(num_classes):
        tp = cm[class_idx, class_idx]
        fp = np.sum(cm[:, class_idx]) - tp
        fn = np.sum(cm[class_idx, :]) - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        if precision + recall == 0:
            f1_list.append(0.0)
        else:
            f1_list.append(2 * precision * recall / (precision + recall))

    return {
        'oa': float(oa),
        'mean_sensitivity': float(np.mean(sensitivity)),
        'macro_f1': float(np.mean(f1_list)),
        'cm': cm,
    }


def smooth_probabilities_with_window(probabilities, radius):
    probabilities = np.asarray(probabilities, dtype=float)
    if radius <= 0 or len(probabilities) == 0:
        return probabilities.copy()

    smoothed = np.zeros_like(probabilities)
    for idx in range(len(probabilities)):
        left = max(0, idx - radius)
        right = min(len(probabilities), idx + radius + 1)
        smoothed[idx] = np.mean(probabilities[left:right], axis=0)

    row_sum = np.sum(smoothed, axis=1, keepdims=True) + 1e-12
    return smoothed / row_sum


def is_transition_valid(prev_label, next_label):
    if prev_label is None or next_label is None:
        return True
    return (int(prev_label), int(next_label)) not in IMPOSSIBLE_TRANSITIONS


def correct_impossible_jumps(raw_labels, smoothed_probabilities, max_passes=3):
    labels = np.asarray(raw_labels, dtype=int).copy()
    smoothed_probabilities = np.asarray(smoothed_probabilities, dtype=float)
    num_classes = smoothed_probabilities.shape[1]

    if len(labels) <= 1:
        return labels

    for _ in range(max_passes):
        changed = False

        for idx in range(1, len(labels) - 1):
            prev_label = labels[idx - 1]
            curr_label = labels[idx]
            next_label = labels[idx + 1]
            if prev_label == next_label and curr_label != prev_label:
                if (not is_transition_valid(prev_label, curr_label)) or (not is_transition_valid(curr_label, next_label)):
                    labels[idx] = prev_label
                    changed = True

        for idx in range(len(labels)):
            prev_label = labels[idx - 1] if idx > 0 else None
            curr_label = labels[idx]
            next_label = labels[idx + 1] if idx < len(labels) - 1 else None

            if is_transition_valid(prev_label, curr_label) and is_transition_valid(curr_label, next_label):
                continue

            candidate_scores = smoothed_probabilities[idx].copy()
            valid_mask = np.ones(num_classes, dtype=bool)
            for class_idx in range(num_classes):
                if not is_transition_valid(prev_label, class_idx):
                    valid_mask[class_idx] = False
                if not is_transition_valid(class_idx, next_label):
                    valid_mask[class_idx] = False

            if np.any(valid_mask):
                masked_scores = np.where(valid_mask, candidate_scores, -1.0)
                best_label = int(np.argmax(masked_scores))
                if best_label != curr_label:
                    labels[idx] = best_label
                    changed = True

        if not changed:
            break

    return labels


def apply_sleep_jump_smoothing(probabilities, window_radius=2):
    smoothed_probabilities = smooth_probabilities_with_window(probabilities, radius=window_radius)
    raw_labels = np.argmax(probabilities, axis=1)
    smooth_labels = correct_impossible_jumps(raw_labels, smoothed_probabilities, max_passes=3)
    return raw_labels, smooth_labels, smoothed_probabilities


def build_training_scaler(data_dir, dataset_name):
    if dataset_name not in DATASET_CONFIGS:
        raise ValueError(f'未知数据集分组: {dataset_name}')
    bundle = build_dataset_bundle(
        data_dir=data_dir,
        record_names=DATASET_CONFIGS[dataset_name],
        test_size=0.25,
        random_state=FINAL_SEED,
    )
    return bundle['scaler']


def discover_available_records(data_dir):
    data_path = Path(data_dir)
    candidates = {}
    for path in data_path.glob('slp*.hea'):
        candidates.setdefault(path.stem, set()).add('.hea')
    for path in data_path.glob('slp*.st'):
        candidates.setdefault(path.stem, set()).add('.st')

    available_records = []
    for record_name, suffixes in candidates.items():
        if '.hea' in suffixes and '.st' in suffixes:
            available_records.append(record_name)
    return sorted(set(available_records))


def select_prediction_records(data_dir, dataset_name, manual_records=None):
    if manual_records:
        return list(manual_records)

    training_records = set(DATASET_CONFIGS[dataset_name])
    available_records = discover_available_records(data_dir)
    external_records = [name for name in available_records if name not in training_records]
    if external_records:
        return external_records
    return list(DATASET_CONFIGS[dataset_name])


def predict_one_record(model, scaler, data_dir, record_name, window_radius):
    X_raw, y_true, metadata = process_record_with_metadata(data_dir, record_name)
    if len(X_raw) == 0:
        raise ValueError(f'记录 {record_name} 未提取到有效样本。')

    X_scaled = scaler.transform(X_raw)
    raw_probabilities = model.predict_proba(X_scaled)
    raw_labels, smooth_labels, smoothed_probabilities = apply_sleep_jump_smoothing(
        raw_probabilities,
        window_radius=window_radius,
    )

    rows = []
    for idx, item in enumerate(metadata):
        raw_label = int(raw_labels[idx])
        smooth_label = int(smooth_labels[idx])
        true_label = int(y_true[idx]) if y_true is not None else -1
        rows.append(
            {
                'record_name': item['record_name'],
                'epoch_index': int(item['sequence_index']),
                'raw_label_id': raw_label,
                'raw_label': CLASS_LABELS[raw_label],
                'raw_label_cn': CLASS_LABELS_CN[raw_label],
                'raw_confidence': float(raw_probabilities[idx, raw_label]),
                'smoothed_label_id': smooth_label,
                'smoothed_label': CLASS_LABELS[smooth_label],
                'smoothed_label_cn': CLASS_LABELS_CN[smooth_label],
                'smoothed_confidence': float(smoothed_probabilities[idx, smooth_label]),
                'true_label_id': true_label,
                'true_label': '' if true_label < 0 else CLASS_LABELS[true_label],
                'true_label_cn': '' if true_label < 0 else CLASS_LABELS_CN[true_label],
            }
        )

    raw_metrics = None if y_true is None else compute_metrics(y_true, raw_labels)
    smooth_metrics = None if y_true is None else compute_metrics(y_true, smooth_labels)
    return rows, raw_metrics, smooth_metrics


def write_prediction_csv(rows, save_path):
    fieldnames = [
        'record_name',
        'epoch_index',
        'raw_label_id',
        'raw_label',
        'raw_label_cn',
        'raw_confidence',
        'smoothed_label_id',
        'smoothed_label',
        'smoothed_label_cn',
        'smoothed_confidence',
        'true_label_id',
        'true_label',
        'true_label_cn',
    ]
    with save_path.open('w', newline='', encoding='utf-8-sig') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_summary_text(dataset_name, model_path, record_names, raw_metrics_by_record, smooth_metrics_by_record):
    lines = []
    lines.append('=== BTD-TSK 已训练学生模型预测结果 ===\n\n')
    lines.append(f'数据分组: {dataset_name}\n')
    lines.append(f'学生模型: {model_path}\n')
    lines.append(f'预测记录: {", ".join(record_names)}\n\n')

    def fmt(metrics):
        return (
            f'OA={metrics["oa"] * 100:.2f}% | '
            f'MeanSen={metrics["mean_sensitivity"] * 100:.2f}% | '
            f'MacroF1={metrics["macro_f1"] * 100:.2f}%'
        )

    all_true = []
    all_raw = []
    all_smooth = []

    for record_name in record_names:
        raw_metrics = raw_metrics_by_record[record_name]['metrics']
        smooth_metrics = smooth_metrics_by_record[record_name]['metrics']
        if raw_metrics is None or smooth_metrics is None:
            lines.append(f'记录 {record_name}\n')
            lines.append('  当前记录缺少真实标签，仅输出逐 epoch 预测结果。\n\n')
            continue
        all_true.extend(raw_metrics_by_record[record_name]['true'])
        all_raw.extend(raw_metrics_by_record[record_name]['pred'])
        all_smooth.extend(smooth_metrics_by_record[record_name]['pred'])
        lines.append(f'记录 {record_name}\n')
        lines.append(f'  原始预测: {fmt(raw_metrics)}\n')
        lines.append(f'  平滑预测: {fmt(smooth_metrics)}\n')
        lines.append(
            '  平滑增益: '
            f'OA {(smooth_metrics["oa"] - raw_metrics["oa"]) * 100:+.2f}% | '
            f'MeanSen {(smooth_metrics["mean_sensitivity"] - raw_metrics["mean_sensitivity"]) * 100:+.2f}% | '
            f'MacroF1 {(smooth_metrics["macro_f1"] - raw_metrics["macro_f1"]) * 100:+.2f}%\n\n'
        )

    if all_true:
        overall_raw = compute_metrics(all_true, all_raw)
        overall_smooth = compute_metrics(all_true, all_smooth)
        lines.append('整体结果\n')
        lines.append(f'  原始预测: {fmt(overall_raw)}\n')
        lines.append(f'  平滑预测: {fmt(overall_smooth)}\n')
        lines.append(
            '  平滑增益: '
            f'OA {(overall_smooth["oa"] - overall_raw["oa"]) * 100:+.2f}% | '
            f'MeanSen {(overall_smooth["mean_sensitivity"] - overall_raw["mean_sensitivity"]) * 100:+.2f}% | '
            f'MacroF1 {(overall_smooth["macro_f1"] - overall_raw["macro_f1"]) * 100:+.2f}%\n'
        )
    return ''.join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description='使用已训练的 BTD-TSK 学生模型进行预测。')
    parser.add_argument('--dataset', default='Data-A', choices=sorted(DATASET_CONFIGS.keys()), help='选择训练模型对应的数据分组。')
    parser.add_argument('--records', nargs='*', default=None, help='要预测的记录名；不填则优先预测不属于该模型训练分组的记录。')
    parser.add_argument('--model-path', default=None, help='已训练学生模型路径；不填则使用 models 目录下默认命名。')
    parser.add_argument('--data-dir', default=None, help='数据目录；默认使用项目下 data 目录。')
    parser.add_argument('--output-dir', default=None, help='预测结果输出目录；默认使用项目下 result 目录。')
    parser.add_argument('--window-radius', type=int, default=2, help='滑动窗口半径，默认 2。')
    return parser.parse_args()


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    data_dir = Path(args.data_dir) if args.data_dir else project_root / 'data'
    output_dir = Path(args.output_dir) if args.output_dir else project_root / 'result'
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = Path(args.model_path) if args.model_path else project_root / 'models' / f'btd_tsk_student_{args.dataset}.joblib'
    if not model_path.exists():
        raise FileNotFoundError(f'未找到学生模型文件: {model_path}')

    record_names = select_prediction_records(str(data_dir), args.dataset, manual_records=args.records)
    scaler = build_training_scaler(str(data_dir), args.dataset)
    model = joblib.load(model_path)

    all_rows = []
    raw_metrics_by_record = {}
    smooth_metrics_by_record = {}

    for record_name in record_names:
        rows, raw_metrics, smooth_metrics = predict_one_record(
            model=model,
            scaler=scaler,
            data_dir=str(data_dir),
            record_name=record_name,
            window_radius=args.window_radius,
        )
        all_rows.extend(rows)
        raw_metrics_by_record[record_name] = {
            'metrics': raw_metrics,
            'true': [row['true_label_id'] for row in rows if row['true_label_id'] >= 0],
            'pred': [row['raw_label_id'] for row in rows if row['true_label_id'] >= 0],
        }
        smooth_metrics_by_record[record_name] = {
            'metrics': smooth_metrics,
            'pred': [row['smoothed_label_id'] for row in rows if row['true_label_id'] >= 0],
        }

    scope_name = record_names[0] if len(record_names) == 1 else f'{args.dataset}_all'
    csv_path = output_dir / f'btd_tsk_prediction_{scope_name}.csv'
    summary_path = output_dir / f'btd_tsk_prediction_{scope_name}_summary.txt'
    write_prediction_csv(all_rows, csv_path)
    summary_text = build_summary_text(
        dataset_name=args.dataset,
        model_path=model_path,
        record_names=record_names,
        raw_metrics_by_record=raw_metrics_by_record,
        smooth_metrics_by_record=smooth_metrics_by_record,
    )
    summary_path.write_text(summary_text, encoding='utf-8-sig')

    print(summary_text)
    print(f'逐 epoch 预测结果已保存到: {csv_path}')
    print(f'预测汇总已保存到: {summary_path}')


if __name__ == '__main__':
    main()
