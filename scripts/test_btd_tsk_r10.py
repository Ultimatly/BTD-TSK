from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import train_btd_tsk_distill as thesis_train


RESULT_PATH = PROJECT_ROOT / "result" / "btd_tsk_r10_test.txt"


def main() -> None:
    # 保持论文主线参数不变，仅将学生规则数改为 10。
    original_btd = deepcopy(thesis_train.BTD_CONFIG)
    original_baseline = deepcopy(thesis_train.BASELINE_CONFIG)
    original_gd = deepcopy(thesis_train.GD_CONFIG)

    try:
        thesis_train.BTD_CONFIG["student_n_rules"] = 10
        thesis_train.BASELINE_CONFIG["n_rules"] = 10
        thesis_train.GD_CONFIG["n_rules"] = 10

        seeds = list(thesis_train.AVERAGE_SEEDS)
        lines: list[str] = []
        lines.append("=== 论文主线参数下 10 条规则测试 ===\n\n")
        lines.append(f"测试种子: {seeds}\n")
        lines.append("仅修改规则数，其余参数与论文主线一致。\n\n")

        best_seed = None
        best_oa = -1.0
        best_metrics = None
        all_oa = []

        for seed in seeds:
            run = thesis_train.run_models_for_seed(seed, save_model=False)
            metrics = run.results["BTD-TSK"]
            oa = float(metrics["oa"])
            all_oa.append(oa)
            lines.append(
                f"seed={seed}: OA={metrics['oa'] * 100:.2f}% | "
                f"MeanSen={metrics['mean_sensitivity'] * 100:.2f}% | "
                f"MacroF1={metrics['macro_f1'] * 100:.2f}%\n"
            )
            if oa > best_oa:
                best_oa = oa
                best_seed = seed
                best_metrics = metrics

        lines.append("\n")
        lines.append(
            f"平均OA={np.mean(all_oa) * 100:.2f}% ± {np.std(all_oa) * 100:.2f}%\n"
        )
        if best_metrics is not None:
            lines.append(
                f"最佳结果: seed={best_seed}, OA={best_metrics['oa'] * 100:.2f}% | "
                f"MeanSen={best_metrics['mean_sensitivity'] * 100:.2f}% | "
                f"MacroF1={best_metrics['macro_f1'] * 100:.2f}%\n"
            )

        RESULT_PATH.write_text("".join(lines), encoding="utf-8-sig")
        print(RESULT_PATH)
        if best_metrics is not None:
            print(
                f"BEST seed={best_seed} OA={best_metrics['oa'] * 100:.2f}% "
                f"MeanSen={best_metrics['mean_sensitivity'] * 100:.2f}% "
                f"MacroF1={best_metrics['macro_f1'] * 100:.2f}%"
            )
    finally:
        thesis_train.BTD_CONFIG.clear()
        thesis_train.BTD_CONFIG.update(original_btd)
        thesis_train.BASELINE_CONFIG.clear()
        thesis_train.BASELINE_CONFIG.update(original_baseline)
        thesis_train.GD_CONFIG.clear()
        thesis_train.GD_CONFIG.update(original_gd)


if __name__ == "__main__":
    main()
