import os

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score

from data_processor import build_dataset
from eatt_tsk_fc_model import EAttTSKFC


def compute_metrics(y_true, y_pred, num_classes=5):
    cm = confusion_matrix(y_true, y_pred, labels=range(num_classes))
    acc_list, sen_list, spe_list = [], [], []

    total_samples = np.sum(cm)
    if total_samples == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, cm

    overall_acc = np.sum(np.diag(cm)) / total_samples
    for class_idx in range(num_classes):
        tp = cm[class_idx, class_idx]
        fn = np.sum(cm[class_idx, :]) - tp
        fp = np.sum(cm[:, class_idx]) - tp
        tn = total_samples - tp - fn - fp

        acc = (tp + tn) / (tp + fn + fp + tn) if (tp + fn + fp + tn) > 0 else 0
        sen = tp / (tp + fn) if (tp + fn) > 0 else 0
        spe = tn / (tn + fp) if (tn + fp) > 0 else 0

        acc_list.append(acc)
        sen_list.append(sen)
        spe_list.append(spe)

    macro_f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
    return overall_acc, np.mean(acc_list), np.mean(sen_list), np.mean(spe_list), macro_f1, cm


def main():
    data_dir = r'f:\sleep\data'
    result_dir = r'f:\sleep\result'
    os.makedirs(result_dir, exist_ok=True)

    base_config = {
        'class_mode': 'five_class',
        'feature_mode': 'handcrafted',
        'n_features': 10,
        'n_rules': 10,
        'heritage_ratio': 0.25,
        'num_classes': 5,
        'random_seed': 20260324,
        'inheritance_mode': 'elite',
        'fusion_mode': 'entropy_attention',
        'class_balanced': False,
        'class_weight_power': 0.5,
        'class_weight_min': 0.5,
        'class_weight_max': 2.0,
        'use_projection': False,
        'short_rule_ratio': 0.1,
        'drop_feature_ratio': 0.2,
        'alpha': 0.1,
        'temperature': 1.0,
        'epsilon': 1e-12,
    }

    dataset_configs = {
        'Data-1': ['slp01a', 'slp01b', 'slp02a', 'slp02b', 'slp03'],
        'Data-2': ['slp04', 'slp14', 'slp16', 'slp32', 'slp37'],
        'Data-3': ['slp41', 'slp45', 'slp48', 'slp59'],
        'Data-4': ['slp60', 'slp61', 'slp66'],
    }
    dp_layers_candidates = [2, 3, 4]

    loaded_data = {}
    for dataset_name, records in dataset_configs.items():
        print(f'Loading {dataset_name} once for dp_layers comparison...')
        loaded_data[dataset_name] = build_dataset(
            data_dir,
            records,
            n_components=base_config['n_features'],
            class_mode=base_config['class_mode'],
            feature_mode=base_config['feature_mode'],
        )

    summary_lines = []
    summary_lines.append('=== EAtt-TSK-FC dp_layers Comparison ===\n')
    summary_lines.append(f"Base Config: {base_config}\n")

    for dataset_name, data_tuple in loaded_data.items():
        X_train, X_test, y_train, y_test = data_tuple
        summary_lines.append(f'\n[{dataset_name}]\n')

        for dp_layers in dp_layers_candidates:
            print(f'Running {dataset_name} with dp_layers={dp_layers}...')
            model = EAttTSKFC(
                dp_layers=dp_layers,
                n_rules=base_config['n_rules'],
                heritage_ratio=base_config['heritage_ratio'],
                num_classes=base_config['num_classes'],
                random_state=base_config['random_seed'],
                model_name='EAtt-TSK-FC',
                inheritance_mode=base_config['inheritance_mode'],
                fusion_mode=base_config['fusion_mode'],
                class_balanced=base_config['class_balanced'],
                class_weight_power=base_config['class_weight_power'],
                class_weight_min=base_config['class_weight_min'],
                class_weight_max=base_config['class_weight_max'],
                use_projection=base_config['use_projection'],
                short_rule_ratio=base_config['short_rule_ratio'],
                drop_feature_ratio=base_config['drop_feature_ratio'],
                alpha=base_config['alpha'],
                temperature=base_config['temperature'],
                epsilon=base_config['epsilon'],
            )
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            overall_acc, mean_acc, mean_sen, mean_spe, macro_f1, cm = compute_metrics(
                y_test, y_pred, num_classes=base_config['num_classes']
            )

            summary_lines.append(f'  dp_layers={dp_layers}\n')
            summary_lines.append(f'    Overall Accuracy:    {overall_acc * 100:.2f}%\n')
            summary_lines.append(f'    Mean Class Accuracy: {mean_acc * 100:.2f}%\n')
            summary_lines.append(f'    Mean Sensitivity:    {mean_sen * 100:.2f}%\n')
            summary_lines.append(f'    Mean Specificity:    {mean_spe * 100:.2f}%\n')
            summary_lines.append(f'    Macro F1:            {macro_f1 * 100:.2f}%\n')
            summary_lines.append('    Confusion Matrix:\n')
            summary_lines.append(np.array2string(cm) + '\n')

        summary_lines.append('-' * 50 + '\n')

    save_path = os.path.join(result_dir, 'dp_layers_comparison.txt')
    with open(save_path, 'w', encoding='utf-8') as file_obj:
        file_obj.writelines(summary_lines)

    print(f'dp_layers comparison saved to {save_path}')


if __name__ == '__main__':
    main()
