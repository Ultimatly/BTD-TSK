from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import confusion_matrix, f1_score

from btd_teacher import BiLSTMSequenceClassifier, build_sequence_windows
from btd_tsk import BTDTSKDistiller, ZeroOrderTSKGDClassifier
from data_processor import build_dataset_bundle, get_multisource_feature_names_cn
from tsk_classifier import ZeroOrderTSKClassifier

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MODEL_DIR = PROJECT_ROOT / "models"
RESULT_DIR = PROJECT_ROOT / "result"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

CLASS_LABELS = ["W", "N1", "N2", "N3", "REM"]
SLPDB_RECORDS = [
    "slp01a",
    "slp01b",
    "slp02a",
    "slp02b",
    "slp03",
    "slp04",
    "slp14",
    "slp16",
    "slp32",
    "slp37",
    "slp41",
    "slp45",
    "slp48",
    "slp59",
    "slp60",
    "slp61",
    "slp66",
    "slp67x",
]
AVERAGE_SEEDS = [42, 52, 62, 72, 82]
FINAL_SEED = 42
TEST_SIZE = 0.25
MODEL_FILENAME = "btd_tsk_student.joblib"
RULE_FILENAME = "btd_tsk_rules_student.txt"
SUMMARY_FILENAME = "model_average_compare.txt"
FIGURE_FILENAME = "多模型平均性能对比图.png"
CONFUSION_FILENAME = "BTD-TSK混淆矩阵.png"

BASELINE_CONFIG = {
    "n_rules": 20,
    "reg": 1e-3,
    "antecedent_strategy": "global",
}
GD_CONFIG = {
    "n_rules": 20,
    "reg": 1e-5,
    "batch_size": 64,
    "lr": 0.015,
    "max_epochs": 140,
    "patience": 18,
    "selection_metric": "loss",
    "antecedent_strategy": "global",
}
# 论文主线最终采用的 BTD-TSK 配置。
BTD_CONFIG = {
    "student_n_rules": 20,
    "sequence_radius": 2,
    "teacher_temperature": 1.5,
    "lambda_ce": 1.0,
    "lambda_kd": 0.06,
    "antecedent_strategy": "classwise",
    "antecedent_guidance": "teacher_embedding",
    "guidance_alpha": 0.7,
    "teacher_kwargs": {
        "max_epochs": 40,
        "patience": 8,
    },
    "student_kwargs": {
        "max_epochs": 140,
        "patience": 18,
        "reg": 1e-5,
        "lr": 0.015,
        "batch_size": 64,
        "selection_metric": "loss",
    },
}


@dataclass
class ExperimentRun:
    seed: int
    results: dict[str, dict[str, object]]
    btd_model: ZeroOrderTSKGDClassifier | None = None
    scaler: object | None = None


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, object]:
    cm = confusion_matrix(y_true, y_pred, labels=np.arange(len(CLASS_LABELS)))
    total = float(np.sum(cm))
    oa = float(np.trace(cm) / total) if total > 0 else 0.0
    recalls = []
    for class_idx in range(len(CLASS_LABELS)):
        tp = cm[class_idx, class_idx]
        fn = np.sum(cm[class_idx, :]) - tp
        recalls.append(float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0)
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    return {
        "oa": oa,
        "mean_sensitivity": float(np.mean(recalls)),
        "macro_f1": macro_f1,
        "cm": cm,
        "recalls": np.asarray(recalls, dtype=float),
    }


def prepare_split(bundle: dict[str, object], indices: np.ndarray, radius: int) -> dict[str, np.ndarray]:
    metadata = bundle["metadata"]
    ordered_indices = sorted(
        indices.tolist(),
        key=lambda idx: (metadata[idx]["record_name"], metadata[idx]["sequence_index"], idx),
    )
    x_student = bundle["X_all"][ordered_indices]
    y = bundle["y_all"][ordered_indices]
    ordered_meta = [metadata[idx] for idx in ordered_indices]

    group_ids = []
    record_to_group = {}
    next_group = 0
    for item in ordered_meta:
        record_name = item["record_name"]
        if record_name not in record_to_group:
            record_to_group[record_name] = next_group
            next_group += 1
        group_ids.append(record_to_group[record_name])
    group_ids = np.asarray(group_ids, dtype=int)
    x_sequence = build_sequence_windows(x_student, group_ids=group_ids, radius=radius)
    return {
        "X_student": np.asarray(x_student, dtype=np.float32),
        "X_sequence": np.asarray(x_sequence, dtype=np.float32),
        "y": np.asarray(y, dtype=int),
    }


def export_rules_if_then(student_model: ZeroOrderTSKGDClassifier, x_reference: np.ndarray, save_path: Path) -> None:
    feature_names = get_multisource_feature_names_cn()
    feature_mean = np.mean(x_reference, axis=0)
    feature_std = np.std(x_reference, axis=0) + 1e-12
    activations = student_model.compute_rule_activations(x_reference)
    rule_importance = np.mean(activations, axis=0)
    rule_probs = student_model.get_rule_class_probabilities()

    def level_text(value: float, mean: float, std: float) -> str:
        z_score = (value - mean) / std
        if z_score >= 1.5:
            return "显著偏高"
        if z_score >= 0.75:
            return "偏高"
        if z_score <= -1.5:
            return "显著偏低"
        if z_score <= -0.75:
            return "偏低"
        return "中等"

    lines = []
    lines.append("=== BTD-TSK 学生模型规则 ===\n\n")
    for rule_idx in range(student_model.n_rules):
        center = student_model.a[rule_idx]
        sigma = student_model.sigma[rule_idx]
        importance = float(rule_importance[rule_idx])
        class_prob = rule_probs[rule_idx]
        dominant_class = int(np.argmax(class_prob))
        lines.append(f"规则 {rule_idx + 1}\n")
        lines.append(f"重要性: {importance:.6f}\n")
        lines.append("IF\n")
        for feature_idx, feature_name in enumerate(feature_names):
            level = level_text(center[feature_idx], feature_mean[feature_idx], feature_std[feature_idx])
            lines.append(
                f"  - {feature_name}: {level} (中心={center[feature_idx]:.6f}, 宽度={sigma[feature_idx]:.6f})\n"
            )
        lines.append("THEN\n")
        lines.append(f"  - 主导类别: {CLASS_LABELS[dominant_class]}\n")
        for class_idx, class_name in enumerate(CLASS_LABELS):
            lines.append(f"    * {class_name}: {class_prob[class_idx]:.6f}\n")
        lines.append("\n")

    save_path.write_text("".join(lines), encoding="utf-8-sig")


def attach_model_metadata(
    student_model: ZeroOrderTSKGDClassifier,
    scaler: object,
    seed: int,
) -> ZeroOrderTSKGDClassifier:
    student_model.feature_scaler = scaler
    student_model.feature_names_cn = get_multisource_feature_names_cn()
    student_model.preferred_eeg_channels = [
        "EEG (C4-A1)",
        "C4-A1",
        "EEG C4-A1",
        "EEG C4-M1",
        "C4-M1",
        "PSG_C4",
        "C4",
    ]
    student_model.preferred_ecg_keywords = ["ECG", "EKG"]
    student_model.dataset_records = list(SLPDB_RECORDS)
    student_model.training_seed = int(seed)
    student_model.model_label = "BTD-TSK"
    return student_model


def run_models_for_seed(seed: int, save_model: bool = False) -> ExperimentRun:
    # 固定 NumPy 和 PyTorch 随机种子，保证同一实验配置可重复。
    np.random.seed(seed)
    torch.manual_seed(seed)
    print(f"\n========== 开始执行 seed={seed} 的实验 ==========")
    print("正在构建训练集与测试集...")

    bundle = build_dataset_bundle(
        data_dir=str(DATA_DIR),
        record_names=SLPDB_RECORDS,
        test_size=TEST_SIZE,
        random_state=seed,
    )
    train_split = prepare_split(bundle, bundle["train_idx"], radius=int(BTD_CONFIG["sequence_radius"]))
    test_split = prepare_split(bundle, bundle["test_idx"], radius=int(BTD_CONFIG["sequence_radius"]))
    print(
        f"数据准备完成：训练样本 {len(train_split['y'])} 条，测试样本 {len(test_split['y'])} 条。"
    )

    # 普通零阶 TSK-LLM 基线。
    print("正在训练 TSK-LLM 基线模型...")
    llm_model = ZeroOrderTSKClassifier(**BASELINE_CONFIG)
    llm_model.fit(train_split["X_student"], train_split["y"])
    llm_metrics = compute_metrics(test_split["y"], llm_model.predict(test_split["X_student"]))
    print(f"TSK-LLM 完成：OA={llm_metrics['oa'] * 100:.2f}%")

    gd_kwargs = dict(GD_CONFIG)
    gd_kwargs["seed"] = seed
    # 普通零阶 TSK-GD 基线。
    print("正在训练 TSK-GD 基线模型...")
    gd_model = ZeroOrderTSKGDClassifier(**gd_kwargs)
    gd_model.fit(train_split["X_student"], train_split["y"])
    gd_metrics = compute_metrics(test_split["y"], gd_model.predict(test_split["X_student"]))
    print(f"TSK-GD 完成：OA={gd_metrics['oa'] * 100:.2f}%")

    # 教师模型用于提供时序判别知识。
    print("正在训练 BiLSTM 教师模型...")
    teacher = BiLSTMSequenceClassifier(
        input_dim=train_split["X_sequence"].shape[2],
        num_classes=len(CLASS_LABELS),
        seed=seed,
        **BTD_CONFIG["teacher_kwargs"],
    )
    teacher.fit(train_split["X_sequence"], train_split["y"])
    teacher_metrics = compute_metrics(test_split["y"], teacher.predict(test_split["X_sequence"]))
    print(f"BiLSTM 完成：OA={teacher_metrics['oa'] * 100:.2f}%")

    kd_kwargs = dict(BTD_CONFIG)
    kd_kwargs["seed"] = seed
    # 蒸馏训练得到最终的 BTD-TSK 学生模型。
    print("正在训练 BTD-TSK 学生模型...")
    distiller = BTDTSKDistiller(**kd_kwargs)
    distiller.fit(train_split["X_student"], train_split["X_sequence"], train_split["y"])
    student_metrics = compute_metrics(test_split["y"], distiller.predict_student(test_split["X_student"]))
    print(f"BTD-TSK 完成：OA={student_metrics['oa'] * 100:.2f}%")

    student_model = attach_model_metadata(distiller.student_model, bundle["scaler"], seed)
    if save_model:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(student_model, MODEL_DIR / MODEL_FILENAME)
        export_rules_if_then(student_model, train_split["X_student"], RESULT_DIR / RULE_FILENAME)
        print(f"已保存学生模型：{MODEL_DIR / MODEL_FILENAME}")
        print(f"已导出规则文件：{RESULT_DIR / RULE_FILENAME}")

    return ExperimentRun(
        seed=seed,
        results={
            "TSK-LLM": llm_metrics,
            "TSK-GD": gd_metrics,
            "BiLSTM": teacher_metrics,
            "BTD-TSK": student_metrics,
        },
        btd_model=student_model if save_model else None,
        scaler=bundle["scaler"] if save_model else None,
    )


def summarize_runs(runs: list[ExperimentRun]) -> dict[str, dict[str, dict[str, float]]]:
    summary: dict[str, dict[str, dict[str, float]]] = {}
    for model_name in runs[0].results:
        summary[model_name] = {}
        for metric_key in ("oa", "mean_sensitivity", "macro_f1"):
            values = np.asarray([run.results[model_name][metric_key] for run in runs], dtype=float)
            summary[model_name][metric_key] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
            }
    return summary


def plot_average_compare(summary: dict[str, dict[str, dict[str, float]]], save_path: Path) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    methods = ["TSK-LLM", "TSK-GD", "BiLSTM", "BTD-TSK"]
    metric_names = ["OA", "MeanSen", "Macro-F1"]
    metric_keys = ["oa", "mean_sensitivity", "macro_f1"]
    colors = ["#8FB8DE", "#B8D0A1", "#F4B680"]
    x = np.arange(len(methods))
    width = 0.22

    fig, ax = plt.subplots(figsize=(10.5, 6.3), dpi=180)
    for idx, (metric_name, metric_key) in enumerate(zip(metric_names, metric_keys)):
        means = np.asarray([summary[m][metric_key]["mean"] * 100 for m in methods], dtype=float)
        stds = np.asarray([summary[m][metric_key]["std"] * 100 for m in methods], dtype=float)
        bars = ax.bar(
            x + (idx - 1) * width,
            means,
            width=width,
            yerr=stds,
            capsize=4,
            label=metric_name,
            color=colors[idx],
            edgecolor="#4A4A4A",
            linewidth=0.8,
            error_kw={"elinewidth": 1.0, "ecolor": "#4A4A4A"},
        )
        for bar, mean_value in zip(bars, means):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                mean_value + 0.6,
                f"{mean_value:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_ylabel("指标值 / %", fontsize=12)
    ax.set_xlabel("模型方法", fontsize=12)
    ax.set_title("多模型平均性能对比", fontsize=14, pad=14)
    ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_confusion_matrix(cm: np.ndarray, save_path: Path) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    cm = np.asarray(cm, dtype=float)
    row_sum = np.sum(cm, axis=1, keepdims=True)
    normalized = np.divide(cm, row_sum, out=np.zeros_like(cm), where=row_sum > 0) * 100.0

    fig, ax = plt.subplots(figsize=(7.2, 6.4), dpi=180)
    image = ax.imshow(normalized, cmap="YlOrRd", interpolation="nearest", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(CLASS_LABELS)))
    ax.set_yticks(np.arange(len(CLASS_LABELS)))
    ax.set_xticklabels(CLASS_LABELS)
    ax.set_yticklabels(CLASS_LABELS)
    ax.set_xlabel("预测类别", fontsize=12)
    ax.set_ylabel("真实类别", fontsize=12)
    ax.set_title("BTD-TSK混淆矩阵", fontsize=14, pad=12)

    threshold = 50.0
    for row_idx in range(normalized.shape[0]):
        for col_idx in range(normalized.shape[1]):
            value = normalized[row_idx, col_idx]
            color = "white" if value >= threshold else "black"
            ax.text(col_idx, row_idx, f"{value:.2f}%", ha="center", va="center", color=color, fontsize=9)

    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("百分比 / %", fontsize=11)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_summary(runs: list[ExperimentRun], summary: dict[str, dict[str, dict[str, float]]], save_path: Path) -> None:
    lines = []
    lines.append("=== SLPDB Welch13 + ECG9, 20-rule average comparison ===\n\n")
    lines.append(f"Records: {', '.join(SLPDB_RECORDS)}\n")
    lines.append(f"Seeds: {AVERAGE_SEEDS}\n")
    lines.append("BTD-TSK config:\n")
    for key, value in BTD_CONFIG.items():
        lines.append(f"  {key}: {value}\n")
    lines.append("TSK-GD config:\n")
    for key, value in GD_CONFIG.items():
        lines.append(f"  {key}: {value}\n")
    lines.append("\nPer-seed results:\n")
    for run in runs:
        lines.append(f"\n[seed={run.seed}]\n")
        for model_name, metrics in run.results.items():
            lines.append(
                f"{model_name}: OA={metrics['oa'] * 100:.2f}% | "
                f"MeanSen={metrics['mean_sensitivity'] * 100:.2f}% | "
                f"MacroF1={metrics['macro_f1'] * 100:.2f}%\n"
            )
    lines.append("\n[平均值 ± 标准差]\n")
    for model_name in ("TSK-LLM", "TSK-GD", "BiLSTM", "BTD-TSK"):
        lines.append(
            f"{model_name}: "
            f"OA={summary[model_name]['oa']['mean'] * 100:.2f}% ± {summary[model_name]['oa']['std'] * 100:.2f}% | "
            f"MeanSen={summary[model_name]['mean_sensitivity']['mean'] * 100:.2f}% ± {summary[model_name]['mean_sensitivity']['std'] * 100:.2f}% | "
            f"MacroF1={summary[model_name]['macro_f1']['mean'] * 100:.2f}% ± {summary[model_name]['macro_f1']['std'] * 100:.2f}%\n"
        )
    save_path.write_text("".join(lines), encoding="utf-8-sig")


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print("开始执行论文主线训练流程。")
    print(f"使用记录数：{len(SLPDB_RECORDS)}")
    print(f"重复实验次数：{len(AVERAGE_SEEDS)}")
    print(f"固定规则数：{BTD_CONFIG['student_n_rules']}")

    runs: list[ExperimentRun] = []
    best_btd_run: ExperimentRun | None = None
    for seed in AVERAGE_SEEDS:
        run = run_models_for_seed(seed, save_model=(seed == FINAL_SEED))
        runs.append(run)
        if best_btd_run is None or run.results["BTD-TSK"]["oa"] > best_btd_run.results["BTD-TSK"]["oa"]:
            best_btd_run = run

    print("\n正在汇总多次实验结果...")
    summary = summarize_runs(runs)
    write_summary(runs, summary, RESULT_DIR / SUMMARY_FILENAME)
    print(f"已保存结果汇总：{RESULT_DIR / SUMMARY_FILENAME}")
    plot_average_compare(summary, OUTPUT_DIR / FIGURE_FILENAME)
    print(f"已保存平均性能图：{OUTPUT_DIR / FIGURE_FILENAME}")
    if best_btd_run is not None:
        plot_confusion_matrix(best_btd_run.results["BTD-TSK"]["cm"], OUTPUT_DIR / CONFUSION_FILENAME)
        print(f"已保存混淆矩阵图：{OUTPUT_DIR / CONFUSION_FILENAME}")
    print("论文主线训练流程执行完成。")


if __name__ == "__main__":
    main()
