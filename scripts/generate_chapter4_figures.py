from __future__ import annotations

import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix

sys.path.insert(0, r"F:/sleep/src")
from data_processor import build_dataset_bundle  # noqa: E402


OUTPUT_DIR = Path(r"F:/sleep/outputs")
DATA_DIR = Path(r"F:/sleep/data")
MODEL_DIR = Path(r"F:/sleep/models")

CLASS_LABELS = ["W", "N1", "N2", "N3", "R"]
DATASET_CONFIGS = {
    "Data-A": ["slp01a", "slp02a", "slp02b", "slp14", "slp32", "slp37", "slp41", "slp45", "slp60"],
    "Data-B": ["slp01b", "slp03", "slp04", "slp16", "slp48", "slp59", "slp61", "slp66", "slp67x"],
}

PERFORMANCE = {
    "Data-A": {
        "TSK-LLM": {"OA": 57.91, "MeanSen": 45.67, "Macro-F1": 45.26},
        "TSK-GD": {"OA": 56.12, "MeanSen": 44.02, "Macro-F1": 43.39},
        "BiLSTM": {"OA": 66.28, "MeanSen": 69.66, "Macro-F1": 64.57},
        "BTD-TSK": {"OA": 63.18, "MeanSen": 55.69, "Macro-F1": 55.84},
    },
    "Data-B": {
        "TSK-LLM": {"OA": 57.09, "MeanSen": 42.91, "Macro-F1": 38.93},
        "TSK-GD": {"OA": 56.93, "MeanSen": 44.77, "Macro-F1": 40.08},
        "BiLSTM": {"OA": 61.62, "MeanSen": 66.09, "Macro-F1": 59.76},
        "BTD-TSK": {"OA": 62.82, "MeanSen": 54.99, "Macro-F1": 55.14},
    },
}

BAR_COLORS = ["#8FB8DE", "#B8D0A1", "#F4B680"]


def configure_fonts() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def plot_performance(dataset_name: str, save_path: Path) -> None:
    records = PERFORMANCE[dataset_name]
    methods = list(records.keys())
    metrics = ["OA", "MeanSen", "Macro-F1"]
    values = np.array([[records[method][metric] for metric in metrics] for method in methods], dtype=float)

    x = np.arange(len(methods))
    width = 0.22

    fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=150)
    for idx, metric in enumerate(metrics):
        bars = ax.bar(
            x + (idx - 1) * width,
            values[:, idx],
            width=width,
            label=metric,
            color=BAR_COLORS[idx],
            edgecolor="#3A4A5A",
            linewidth=0.8,
        )
        for bar, value in zip(bars, values[:, idx], strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.7,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
                color="#2B2B2B",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=11)
    ax.set_ylim(0, 80)
    ax.set_ylabel("指标值 / %", fontsize=12)
    ax.set_xlabel("模型方法", fontsize=12)
    ax.set_title(f"{dataset_name} 多模型性能对比", fontsize=14, pad=14)
    ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper left", frameon=False, ncol=3)

    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def compute_btd_confusion(dataset_name: str) -> np.ndarray:
    bundle = build_dataset_bundle(str(DATA_DIR), DATASET_CONFIGS[dataset_name], test_size=0.25, random_state=42)
    x_test = bundle["X_all"][bundle["test_idx"]]
    y_test = bundle["y_all"][bundle["test_idx"]]
    model = joblib.load(MODEL_DIR / f"btd_tsk_student_{dataset_name}.joblib")
    pred = model.predict(x_test)
    return confusion_matrix(y_test, pred, labels=range(len(CLASS_LABELS)))


def plot_confusion(dataset_name: str, cm: np.ndarray, save_path: Path) -> None:
    row_sum = cm.sum(axis=1, keepdims=True)
    norm_cm = np.divide(cm, row_sum, out=np.zeros_like(cm, dtype=float), where=row_sum != 0)

    fig, ax = plt.subplots(figsize=(7.3, 6.4), dpi=150)
    image = ax.imshow(norm_cm, cmap="YlGnBu", vmin=0, vmax=max(0.6, float(norm_cm.max())))
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("归一化比例", fontsize=10)

    ax.set_xticks(np.arange(len(CLASS_LABELS)))
    ax.set_yticks(np.arange(len(CLASS_LABELS)))
    ax.set_xticklabels(CLASS_LABELS, fontsize=11)
    ax.set_yticklabels(CLASS_LABELS, fontsize=11)
    ax.set_xlabel("预测类别", fontsize=12)
    ax.set_ylabel("真实类别", fontsize=12)
    ax.set_title(f"{dataset_name} 中 BTD-TSK 模型混淆矩阵", fontsize=14, pad=12)

    threshold = norm_cm.max() * 0.55 if norm_cm.size else 0.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            color = "white" if norm_cm[i, j] >= threshold else "#1F2933"
            ax.text(
                j,
                i,
                f"{cm[i, j]}\n{norm_cm[i, j] * 100:.1f}%",
                ha="center",
                va="center",
                fontsize=9,
                color=color,
            )

    ax.set_xticks(np.arange(-0.5, len(CLASS_LABELS), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(CLASS_LABELS), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    configure_fonts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    plot_performance("Data-A", OUTPUT_DIR / "图4-1_Data-A多模型性能对比柱状图.png")
    plot_performance("Data-B", OUTPUT_DIR / "图4-2_Data-B多模型性能对比柱状图.png")

    cm_a = compute_btd_confusion("Data-A")
    cm_b = compute_btd_confusion("Data-B")
    plot_confusion("Data-A", cm_a, OUTPUT_DIR / "图4-3_Data-A_BTD-TSK混淆矩阵.png")
    plot_confusion("Data-B", cm_b, OUTPUT_DIR / "图4-4_Data-B_BTD-TSK混淆矩阵.png")


if __name__ == "__main__":
    main()
