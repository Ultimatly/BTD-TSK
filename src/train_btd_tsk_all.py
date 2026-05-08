from pathlib import Path

from train_btd_tsk_distill import DATASET_CONFIGS, run_one_dataset


def main():
    project_root = Path(__file__).resolve().parents[1]
    result_dir = project_root / 'result'
    summary_path = result_dir / 'btd_tsk_summary_all.txt'

    summary_lines = []
    for dataset_name, records in DATASET_CONFIGS.items():
        output = run_one_dataset(dataset_name, records, save_student_model=True)
        llm = output['results']['TSK-LLM']
        gd = output['results']['TSK-GD']
        btd = output['results']['BTD-TSK']
        summary_lines.append(
            f'{dataset_name}\n'
            f'  TSK-LLM: OA {llm["oa"] * 100:.2f}% | MeanSen {llm["mean_sensitivity"] * 100:.2f}% | MacroF1 {llm["macro_f1"] * 100:.2f}%\n'
            f'  TSK-GD: OA {gd["oa"] * 100:.2f}% | MeanSen {gd["mean_sensitivity"] * 100:.2f}% | MacroF1 {gd["macro_f1"] * 100:.2f}%\n'
            f'  BTD-TSK: OA {btd["oa"] * 100:.2f}% | MeanSen {btd["mean_sensitivity"] * 100:.2f}% | MacroF1 {btd["macro_f1"] * 100:.2f}%\n'
            f'  BTD-TSK 相对 TSK-LLM: OA {(btd["oa"] - llm["oa"]) * 100:+.2f}% | MeanSen {(btd["mean_sensitivity"] - llm["mean_sensitivity"]) * 100:+.2f}% | MacroF1 {(btd["macro_f1"] - llm["macro_f1"]) * 100:+.2f}%\n'
            f'  BTD-TSK 相对 TSK-GD: OA {(btd["oa"] - gd["oa"]) * 100:+.2f}% | MeanSen {(btd["mean_sensitivity"] - gd["mean_sensitivity"]) * 100:+.2f}% | MacroF1 {(btd["macro_f1"] - gd["macro_f1"]) * 100:+.2f}%\n'
        )

    summary_path.write_text('\n'.join(summary_lines), encoding='utf-8-sig')


if __name__ == '__main__':
    main()
