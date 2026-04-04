import os

import joblib
import matplotlib.pyplot as plt
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

    for i in range(num_classes):
        tp = cm[i, i]
        fn = np.sum(cm[i, :]) - tp
        fp = np.sum(cm[:, i]) - tp
        tn = total_samples - tp - fn - fp

        acc = (tp + tn) / (tp + fn + fp + tn) if (tp + fn + fp + tn) > 0 else 0
        sen = tp / (tp + fn) if (tp + fn) > 0 else 0
        spe = tn / (tn + fp) if (tn + fp) > 0 else 0

        acc_list.append(acc)
        sen_list.append(sen)
        spe_list.append(spe)

    macro_f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
    return overall_acc, np.mean(acc_list), np.mean(sen_list), np.mean(spe_list), macro_f1, cm


HANDCRAFTED_FEATURE_NAMES = [
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
]


def linguistic_interpret_base(a_val):
    if a_val < 0.2:
        return 'very low'
    if a_val < 0.4:
        return 'low'
    if a_val < 0.6:
        return 'medium'
    if a_val < 0.8:
        return 'high'
    return 'very high'


def linguistic_interpret_augmented(a_val, alpha):
    # Layer-augmented evidence features usually have a smaller scale (multiplied by alpha).
    if a_val < -0.25 * alpha:
        return 'strongly suppressing'
    if a_val < 0:
        return 'slightly suppressing'
    if a_val < 0.25 * alpha:
        return 'near neutral'
    if a_val < 0.6 * alpha:
        return 'supporting'
    return 'strongly supporting'


def get_feature_name(feature_idx, base_feature_dim, class_labels):
    if feature_idx < base_feature_dim and feature_idx < len(HANDCRAFTED_FEATURE_NAMES):
        return HANDCRAFTED_FEATURE_NAMES[feature_idx]
    if feature_idx < base_feature_dim:
        return f'Feature_{feature_idx}'

    aug_idx = feature_idx - base_feature_dim
    if class_labels and 0 <= aug_idx < len(class_labels):
        return f'PrevLayerEvidence_{class_labels[aug_idx]}'
    return f'PrevLayerEvidence_{aug_idx}'


def print_fuzzy_rules(model, num_features, class_labels=None, save_path=None):
    rule_str = ''
    current_features = num_features

    for layer_idx, tsk in enumerate(model.classifiers):
        rule_str += '=' * 60 + '\n'
        rule_str += f'=== Sub-classifier Layer {layer_idx + 1} (Input Dimensions: {current_features}) ===\n'
        rule_str += '=' * 60 + '\n\n'

        for rule_idx in range(tsk.n_rules):
            a_centers = tsk.a[rule_idx, :]
            sigmas = tsk.sigma[rule_idx, :]
            conse_weights = tsk.beta[rule_idx, :]
            pred_class = np.argmax(conse_weights)
            pred_val = conse_weights[pred_class]

            rule_str += '-' * 50 + '\n'
            rule_str += f'Linguistic Explanations of Rule #{rule_idx + 1}:\n'
            rule_str += 'IF-part: '

            condition_parts = []
            for feature_idx in range(current_features):
                if sigmas[feature_idx] > 1e6:
                    feature_name = get_feature_name(feature_idx, num_features, class_labels)
                    condition_parts.append(
                        f'{feature_name} is IGNORED (Inherited padded feature)'
                    )
                else:
                    feature_name = get_feature_name(feature_idx, num_features, class_labels)
                    if feature_idx < num_features:
                        ling_val = linguistic_interpret_base(a_centers[feature_idx])
                    else:
                        ling_val = linguistic_interpret_augmented(a_centers[feature_idx], model.alpha)
                    condition_parts.append(
                        f'{feature_name} is {ling_val} '
                        f'(a={a_centers[feature_idx]:.4f}, sigma={sigmas[feature_idx]:.4f})'
                    )

            rule_str += ' AND\n         '.join(condition_parts) + '\n'
            rule_str += (
                f'THEN-part: Output indicates Class {pred_class} '
                f'with consequence weight P={pred_val:.4f}\n'
            )
            rule_str += '-' * 50 + '\n\n'

        if layer_idx == 0:
            current_features = num_features + model.num_classes

    if save_path:
        with open(save_path, 'w', encoding='utf-8') as file_obj:
            file_obj.write(rule_str)
    else:
        print(rule_str)


def format_training_config(train_cfg):
    ordered_keys = [
        'class_mode',
        'feature_mode',
        'n_features',
        'dp_layers',
        'n_rules',
        'heritage_ratio',
        'num_classes',
        'class_balanced',
        'class_weight_power',
        'short_rule_ratio',
        'drop_feature_ratio',
        'alpha',
        'temperature',
        'use_projection',
    ]
    return ', '.join(f'{key}={train_cfg[key]}' for key in ordered_keys)


def get_class_labels(class_mode):
    if class_mode == 'five_class':
        return ['W', 'N1', 'N2', 'N3', 'R']
    if class_mode == 'six_class':
        return ['W', '1', '2', '3', '4', 'R']
    raise ValueError(f'Unsupported class_mode: {class_mode}')


def plot_confusion_matrices_grid(confusion_results, save_path):
    dataset_names = list(confusion_results.keys())
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    axes = axes.flatten()

    for idx, dataset_name in enumerate(dataset_names):
        cm = confusion_results[dataset_name]['cm']
        class_labels = confusion_results[dataset_name]['labels']
        ax = axes[idx]

        image = ax.imshow(cm, cmap='YlOrRd', interpolation='nearest')
        ax.set_title(dataset_name)
        ax.set_xlabel('Predicted')
        ax.set_ylabel('True')
        ax.set_xticks(np.arange(len(class_labels)))
        ax.set_yticks(np.arange(len(class_labels)))
        ax.set_xticklabels(class_labels)
        ax.set_yticklabels(class_labels)

        threshold = cm.max() / 2.0 if cm.size > 0 else 0.0
        for row_idx in range(cm.shape[0]):
            for col_idx in range(cm.shape[1]):
                color = 'white' if cm[row_idx, col_idx] > threshold else 'black'
                ax.text(
                    col_idx,
                    row_idx,
                    str(cm[row_idx, col_idx]),
                    ha='center',
                    va='center',
                    color=color,
                    fontsize=10,
                )

        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    for idx in range(len(dataset_names), len(axes)):
        axes[idx].axis('off')

    fig.suptitle('Confusion Matrices (2x2 Grid)', fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(save_path, dpi=300)
    plt.close(fig)


def main():
    data_dir = r'f:\sleep\data'

    dataset_configs = {
        'Data-1': {
            'records': ['slp01a', 'slp01b', 'slp02a', 'slp02b', 'slp03'],
            'training': {
                'class_mode': 'five_class',
                'feature_mode': 'handcrafted',
                'n_features': 10,
                'dp_layers': 2,
                'n_rules': 10,
                'heritage_ratio': 0.25,
                'num_classes': 5,
                'random_seed': None,
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
            },
        },
        'Data-2': {
            'records': ['slp04', 'slp14', 'slp16', 'slp32', 'slp37'],
            'training': {
                'class_mode': 'five_class',
                'feature_mode': 'handcrafted',
                'n_features': 10,
                'dp_layers': 2,
                'n_rules': 10,
                'heritage_ratio': 0.25,
                'num_classes': 5,
                'random_seed': None,
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
            },
        },
        'Data-3': {
            'records': ['slp41', 'slp45', 'slp48', 'slp59'],
            'training': {
                'class_mode': 'five_class',
                'feature_mode': 'handcrafted',
                'n_features': 10,
                'dp_layers': 2,
                'n_rules': 10,
                'heritage_ratio': 0.25,
                'num_classes': 5,
                'random_seed': None,
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
            },
        },
        'Data-4': {
            'records': ['slp60', 'slp61', 'slp66'],
            'training': {
                'class_mode': 'five_class',
                'feature_mode': 'handcrafted',
                'n_features': 10,
                'dp_layers': 2,
                'n_rules': 10,
                'heritage_ratio': 0.25,
                'num_classes': 5,
                'random_seed': None,
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
            },
        },
    }

    model_save_dir = r'f:\sleep\models'
    result_save_dir = r'f:\sleep\result'
    os.makedirs(model_save_dir, exist_ok=True)
    os.makedirs(result_save_dir, exist_ok=True)

    metrics_save_path = os.path.join(result_save_dir, 'evaluation_metrics.txt')
    with open(metrics_save_path, 'w', encoding='utf-8') as metrics_file:
        metrics_file.write('=== EAtt-TSK-FC Evaluation Metrics ===\n\n')

    confusion_results = {}
    for dataset_name, dataset_config in dataset_configs.items():
        records = dataset_config['records']
        train_cfg = dataset_config['training']

        print(f'=== Running experiment on {dataset_name} ===')

        current_seed = train_cfg['random_seed']
        if current_seed is None:
            current_seed = np.random.randint(0, 100000)

        np.random.seed(current_seed)
        print(f'Random Seed for this run: {current_seed}')
        print(f'Training Config -> {format_training_config(train_cfg)}')

        X_train, X_test, y_train, y_test = build_dataset(
            data_dir,
            records,
            n_components=train_cfg['n_features'],
            class_mode=train_cfg['class_mode'],
            feature_mode=train_cfg['feature_mode'],
        )
        input_feature_dim = X_train.shape[1]

        print(f'\n[{dataset_name}] Data processed. Starting training of EAtt-TSK-FC model...')
        model = EAttTSKFC(
            dp_layers=train_cfg['dp_layers'],
            n_rules=train_cfg['n_rules'],
            heritage_ratio=train_cfg['heritage_ratio'],
            num_classes=train_cfg['num_classes'],
            random_state=current_seed,
            model_name='EAtt-TSK-FC',
            inheritance_mode=train_cfg['inheritance_mode'],
            fusion_mode=train_cfg['fusion_mode'],
            class_balanced=train_cfg['class_balanced'],
            class_weight_power=train_cfg['class_weight_power'],
            class_weight_min=train_cfg['class_weight_min'],
            class_weight_max=train_cfg['class_weight_max'],
            use_projection=train_cfg['use_projection'],
            short_rule_ratio=train_cfg['short_rule_ratio'],
            drop_feature_ratio=train_cfg['drop_feature_ratio'],
            alpha=train_cfg['alpha'],
            temperature=train_cfg['temperature'],
            epsilon=train_cfg['epsilon'],
        )
        model.fit(X_train, y_train)

        model_path = os.path.join(model_save_dir, f'eatt_tsk_fc_model_{dataset_name}.joblib')
        joblib.dump(model, model_path)
        print(f'[{dataset_name}] Training complete. Model saved to {model_path}.')

        print('\nEvaluating on test set...')
        y_pred = model.predict(X_test)
        overall_acc, mean_acc, mean_sen, mean_spe, macro_f1, cm = compute_metrics(
            y_test, y_pred, num_classes=train_cfg['num_classes']
        )

        eval_str = f'Results on {dataset_name} (Seed: {current_seed}):\n'
        eval_str += f'  Model: EAtt-TSK-FC\n'
        eval_str += f'  Training Config: {format_training_config(train_cfg)}\n'
        eval_str += f'  Overall Accuracy:    {overall_acc * 100:.2f}%\n'
        eval_str += f'  Mean Class Accuracy: {mean_acc * 100:.2f}%\n'
        eval_str += f'  Mean Sensitivity:    {mean_sen * 100:.2f}%\n'
        eval_str += f'  Mean Specificity:    {mean_spe * 100:.2f}%\n'
        eval_str += f'  Macro F1:            {macro_f1 * 100:.2f}%\n'

        print(eval_str, end='')
        with open(metrics_save_path, 'a', encoding='utf-8') as metrics_file:
            metrics_file.write(eval_str)
            metrics_file.write('  Confusion Matrix:\n')
            metrics_file.write(np.array2string(cm))
            metrics_file.write('\n' + '-' * 40 + '\n')

        cm_save_path = os.path.join(result_save_dir, f'confusion_matrix_{dataset_name}.txt')
        with open(cm_save_path, 'w', encoding='utf-8') as cm_file:
            cm_file.write(np.array2string(cm))
        confusion_results[dataset_name] = {
            'cm': cm,
            'labels': get_class_labels(train_cfg['class_mode']),
        }

        rule_save_path = os.path.join(result_save_dir, f'rules_{dataset_name}.txt')
        print_fuzzy_rules(
            model,
            input_feature_dim,
            class_labels=get_class_labels(train_cfg['class_mode']),
            save_path=rule_save_path,
        )
        print(f'[{dataset_name}] Rule explanations saved to {rule_save_path}.')
        print(f'[{dataset_name}] Confusion matrix saved to {cm_save_path}.\n')

    grid_save_path = os.path.join(result_save_dir, 'confusion_matrices_grid.png')
    plot_confusion_matrices_grid(confusion_results, grid_save_path)
    print(f'Combined confusion matrix heatmap saved to {grid_save_path}.')


if __name__ == '__main__':
    main()
