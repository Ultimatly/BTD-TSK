from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import confusion_matrix, f1_score

from btd_teacher import BiLSTMSequenceClassifier, build_sequence_windows
from btd_tsk import BTDTSKDistiller, ZeroOrderTSKGDClassifier
from data_processor import build_dataset_bundle, get_multimodal_feature_names_cn
from tsk_classifier import ZeroOrderTSKClassifier

NUM_CLASSES = 5
CLASS_LABELS = ['W', 'N1', 'N2', 'N3', 'R']
FINAL_SEED = 42

DATASET_CONFIGS = {
    'Data-A': ['slp01a', 'slp02a', 'slp02b', 'slp14', 'slp32', 'slp37', 'slp41', 'slp45', 'slp60'],
    'Data-B': ['slp01b', 'slp03', 'slp04', 'slp16', 'slp48', 'slp59', 'slp61', 'slp66', 'slp67x'],
}

FINAL_GD_CONFIG = {
    'n_rules': 10,
    'reg': 1e-5,
    'batch_size': 128,
    'lr': 2e-2,
    'max_epochs': 200,
    'patience': 20,
    'selection_metric': 'loss',
    'seed': FINAL_SEED,
    'antecedent_strategy': 'global',
}

FINAL_KD_CONFIG = {
    'student_n_rules': 10,
    'sequence_radius': 2,
    'teacher_temperature': 1.5,
    'lambda_ce': 1.0,
    'lambda_kd': 0.1,
    'seed': FINAL_SEED,
    'antecedent_strategy': 'global',
    'antecedent_guidance': 'teacher_embedding',
    'guidance_alpha': 0.7,
}

DATASET_CONFIG = {
    'name': 'Data-A',
    'records': DATASET_CONFIGS['Data-A'],
}


def compute_metrics(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=range(NUM_CLASSES))
    total = np.sum(cm)
    overall_acc = np.trace(cm) / total if total > 0 else 0.0
    sensitivity = []
    for class_idx in range(NUM_CLASSES):
        tp = cm[class_idx, class_idx]
        fn = np.sum(cm[class_idx, :]) - tp
        sen = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        sensitivity.append(sen)
    macro_f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
    return {
        'oa': float(overall_acc),
        'mean_sensitivity': float(np.mean(sensitivity)),
        'macro_f1': float(macro_f1),
        'cm': cm,
    }


def prepare_split(bundle, indices, radius=2):
    metadata = bundle['metadata']
    ordered_indices = sorted(
        indices.tolist(),
        key=lambda idx: (
            metadata[idx]['record_name'],
            metadata[idx]['sequence_index'],
            idx,
        ),
    )
    X = bundle['X_all'][ordered_indices]
    y = bundle['y_all'][ordered_indices]
    ordered_meta = [metadata[idx] for idx in ordered_indices]

    group_ids = []
    record_to_group = {}
    next_group = 0
    for item in ordered_meta:
        record_name = item['record_name']
        if record_name not in record_to_group:
            record_to_group[record_name] = next_group
            next_group += 1
        group_ids.append(record_to_group[record_name])

    group_ids = np.asarray(group_ids, dtype=int)
    X_sequence = build_sequence_windows(X, group_ids=group_ids, radius=radius)
    return {
        'X_student': X,
        'X_sequence': X_sequence,
        'y': y,
        'group_ids': group_ids,
    }


def _feature_level_text(value, mean, std):
    z_score = (value - mean) / (std + 1e-12)
    if z_score >= 1.5:
        return '显著偏高'
    if z_score >= 0.75:
        return '偏高'
    if z_score <= -1.5:
        return '显著偏低'
    if z_score <= -0.75:
        return '偏低'
    return '中等'


def export_student_rules_chinese(student_model, X_reference, save_path):
    feature_names = get_multimodal_feature_names_cn()
    feature_mean = np.mean(X_reference, axis=0)
    feature_std = np.std(X_reference, axis=0) + 1e-12
    rule_activation = student_model.compute_rule_activations(X_reference)
    rule_importance = np.mean(rule_activation, axis=0)
    rule_class_probs = student_model.get_rule_class_probabilities()

    lines = []
    lines.append('=== BTD-TSK 学生模型完整中文规则 ===\n\n')
    lines.append(f'规则总数: {student_model.n_rules}\n')
    lines.append('说明：以下逐条列出最终 BTD-TSK 学生模型的完整规则，每条规则均给出全部前件条件和完整类别偏好。\n\n')

    for rule_idx in range(student_model.n_rules):
        center = student_model.a[rule_idx]
        sigma = student_model.sigma[rule_idx]
        importance = float(rule_importance[rule_idx])
        class_prob = rule_class_probs[rule_idx]
        dominant_class = int(np.argmax(class_prob))

        lines.append(f'规则 {rule_idx + 1}\n')
        lines.append(f'规则重要性（平均激活度）: {importance:.6f}\n')
        lines.append('规则后件类别偏好:\n')
        for class_idx, class_name in enumerate(CLASS_LABELS):
            lines.append(f'  - {class_name}: {class_prob[class_idx]:.6f}\n')
        lines.append(f'主导类别: {CLASS_LABELS[dominant_class]}\n')
        lines.append('完整前件条件:\n')
        for feature_idx, feature_name in enumerate(feature_names):
            level_text = _feature_level_text(center[feature_idx], feature_mean[feature_idx], feature_std[feature_idx])
            lines.append(
                f'  - {feature_name}: {level_text} '
                f'(中心={center[feature_idx]:.6f}, 宽度={sigma[feature_idx]:.6f})\n'
            )
        lines.append('\n')

    save_path.write_text(''.join(lines), encoding='utf-8-sig')


def plot_confusion_matrices(results, save_path):
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    display_names = {
        'TSK-LLM': 'TSK-LLM',
        'TSK-GD': 'TSK-GD',
        'BiLSTM': 'BiLSTM',
        'BTD-TSK': 'BTD-TSK',
    }

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()
    for ax, (name, metrics) in zip(axes, results.items()):
        cm = metrics['cm']
        image = ax.imshow(cm, cmap='YlOrRd', interpolation='nearest')
        ax.set_title(display_names.get(name, name))
        ax.set_xlabel('预测标签')
        ax.set_ylabel('真实标签')
        ax.set_xticks(np.arange(NUM_CLASSES))
        ax.set_yticks(np.arange(NUM_CLASSES))
        ax.set_xticklabels(CLASS_LABELS)
        ax.set_yticklabels(CLASS_LABELS)
        threshold = cm.max() / 2.0 if cm.size > 0 else 0.0
        for row_idx in range(cm.shape[0]):
            for col_idx in range(cm.shape[1]):
                color = 'white' if cm[row_idx, col_idx] > threshold else 'black'
                ax.text(col_idx, row_idx, str(cm[row_idx, col_idx]), ha='center', va='center', color=color)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle('TSK-LLM / TSK-GD / BiLSTM / BTD-TSK 对比结果', fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(save_path, dpi=300)
    plt.close(fig)


def _format_metrics_line(name, metrics):
    return (
        f'{name}: OA={metrics["oa"] * 100:.2f}% | '
        f'MeanSen={metrics["mean_sensitivity"] * 100:.2f}% | '
        f'MacroF1={metrics["macro_f1"] * 100:.2f}%'
    )


def build_report_text(results, teacher_model, closed_form_model, gd_model, distiller, dataset_name, rule_path=None):
    llm_metrics = results['TSK-LLM']
    gd_metrics = results['TSK-GD']
    bilstm_metrics = results['BiLSTM']
    distilled_metrics = results['BTD-TSK']

    def delta_text(current, base):
        return (
            f'OA {((current["oa"] - base["oa"]) * 100):+.2f}% | '
            f'MeanSen {((current["mean_sensitivity"] - base["mean_sensitivity"]) * 100):+.2f}% | '
            f'MacroF1 {((current["macro_f1"] - base["macro_f1"]) * 100):+.2f}%'
        )

    lines = []
    lines.append('=== TSK-LLM / TSK-GD / BiLSTM / BTD-TSK 训练报告 ===\n\n')
    lines.append(f'数据集分组: {dataset_name}\n')
    lines.append('前件生成方式说明:\n')
    lines.append('  - TSK-LLM: 全局 FCM 前件 + 最小学习机后件\n')
    lines.append('  - TSK-GD: 全局 FCM 前件 + 梯度下降后件\n')
    lines.append('  - BTD-TSK: 教师隐藏表示引导的类别内原型前件 + 标准 CE+KL 蒸馏后件\n\n')
    lines.append('TSK-LLM 基线:\n')
    lines.append(f'  规则数: {closed_form_model.n_rules}\n')
    lines.append('BiLSTM 教师:\n')
    lines.append(f'  最优验证损失: {teacher_model.summary.best_val_loss:.6f}\n')
    lines.append(f'  最优验证准确率: {teacher_model.summary.best_val_acc * 100:.2f}%\n')
    lines.append(f'  实际训练轮数: {teacher_model.summary.epochs_ran}\n')
    lines.append('TSK-GD 基线:\n')
    lines.append(f'  规则数: {gd_model.n_rules}\n')
    lines.append(f'  学习率: {gd_model.lr}\n')
    lines.append(f'  正则项: {gd_model.reg}\n')
    lines.append(f'  批大小: {gd_model.batch_size}\n')
    lines.append(f'  模型选择指标: {gd_model.selection_metric}\n')
    lines.append(f'  最优验证损失: {gd_model.summary.best_val_loss:.6f}\n')
    lines.append(f'  最优验证准确率: {gd_model.summary.best_val_acc * 100:.2f}%\n')
    lines.append(f'  实际训练轮数: {gd_model.summary.epochs_ran}\n')
    lines.append('BTD-TSK:\n')
    lines.append(f'  规则数: {distiller.student_n_rules}\n')
    lines.append(f'  教师温度系数: {distiller.teacher_temperature}\n')
    lines.append(f'  lambda_ce: {distiller.lambda_ce}\n')
    lines.append(f'  lambda_kd: {distiller.lambda_kd}\n')
    lines.append(f'  前件指导方式: {distiller.antecedent_guidance}\n')
    lines.append(f'  指导权重 alpha: {distiller.guidance_alpha}\n')
    lines.append(f'  学生学习率: {distiller.student_model.lr}\n')
    lines.append(f'  学生正则项: {distiller.student_model.reg}\n')
    lines.append(f'  学生批大小: {distiller.student_model.batch_size}\n')
    lines.append(f'  学生模型选择指标: {distiller.student_model.selection_metric}\n')
    lines.append(f'  教师平均置信度: {distiller.training_details["teacher_confidence"]:.4f}\n')
    lines.append(f'  学生最优验证损失: {distiller.student_model.summary.best_val_loss:.6f}\n')
    lines.append(f'  学生最优验证准确率: {distiller.student_model.summary.best_val_acc * 100:.2f}%\n')
    lines.append(f'  学生实际训练轮数: {distiller.student_model.summary.epochs_ran}\n')
    if distiller.training_details.get('rule_class_distribution') is not None:
        lines.append(f'  规则类别分布: {distiller.training_details["rule_class_distribution"]}\n')
    lines.append('\n')
    if rule_path is not None:
        lines.append(f'中文规则文件: {rule_path}\n\n')

    lines.append(_format_metrics_line('TSK-LLM', llm_metrics) + '\n')
    lines.append(_format_metrics_line('TSK-GD', gd_metrics) + '\n')
    lines.append(_format_metrics_line('BiLSTM', bilstm_metrics) + '\n')
    lines.append(_format_metrics_line('BTD-TSK', distilled_metrics) + '\n\n')

    lines.append('相对于 TSK-LLM 的变化:\n')
    lines.append(f'  TSK-GD: {delta_text(gd_metrics, llm_metrics)}\n')
    lines.append(f'  BiLSTM: {delta_text(bilstm_metrics, llm_metrics)}\n')
    lines.append(f'  BTD-TSK: {delta_text(distilled_metrics, llm_metrics)}\n\n')

    lines.append('相对于 TSK-GD 的变化:\n')
    lines.append(f'  BiLSTM: {delta_text(bilstm_metrics, gd_metrics)}\n')
    lines.append(f'  BTD-TSK: {delta_text(distilled_metrics, gd_metrics)}\n')
    return ''.join(lines)


def run_one_dataset(dataset_name, records, save_student_model=True):
    np.random.seed(FINAL_SEED)
    torch.manual_seed(FINAL_SEED)

    project_root = Path(__file__).resolve().parents[1]
    data_dir = str(project_root / 'data')
    model_dir = project_root / 'models'
    result_dir = project_root / 'result'
    model_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    bundle = build_dataset_bundle(data_dir, records, test_size=0.25, random_state=FINAL_SEED)
    train_split = prepare_split(bundle, bundle['train_idx'], radius=2)
    test_split = prepare_split(bundle, bundle['test_idx'], radius=2)

    closed_form_model = ZeroOrderTSKClassifier(n_rules=10, antecedent_strategy='global')
    closed_form_model.fit(train_split['X_student'], train_split['y'])
    closed_form_pred = closed_form_model.predict(test_split['X_student'])

    gd_model = ZeroOrderTSKGDClassifier(**FINAL_GD_CONFIG)
    gd_model.fit(train_split['X_student'], train_split['y'])
    gd_pred = gd_model.predict(test_split['X_student'])

    teacher_model = BiLSTMSequenceClassifier(
        input_dim=train_split['X_sequence'].shape[2],
        num_classes=NUM_CLASSES,
        seed=FINAL_SEED,
    )
    teacher_model.fit(train_split['X_sequence'], train_split['y'])
    bilstm_pred = teacher_model.predict(test_split['X_sequence'])

    distiller = BTDTSKDistiller(**FINAL_KD_CONFIG)
    distiller.student_model = ZeroOrderTSKGDClassifier(**FINAL_GD_CONFIG)
    distiller.fit(train_split['X_student'], train_split['X_sequence'], train_split['y'])
    distilled_pred = distiller.predict_student(test_split['X_student'])

    results = {
        'TSK-LLM': compute_metrics(test_split['y'], closed_form_pred),
        'TSK-GD': compute_metrics(test_split['y'], gd_pred),
        'BiLSTM': compute_metrics(test_split['y'], bilstm_pred),
        'BTD-TSK': compute_metrics(test_split['y'], distilled_pred),
    }

    if save_student_model:
        joblib.dump(distiller.student_model, model_dir / f'btd_tsk_student_{dataset_name}.joblib')

    rule_path = result_dir / f'btd_tsk_rules_student_{dataset_name}.txt'
    export_student_rules_chinese(distiller.student_model, train_split['X_student'], rule_path)

    report_path = result_dir / f'btd_tsk_comparison_{dataset_name}.txt'
    report_path.write_text(
        build_report_text(
            results,
            teacher_model,
            closed_form_model,
            gd_model,
            distiller,
            dataset_name,
            rule_path=rule_path,
        ),
        encoding='utf-8-sig',
    )

    plot_confusion_matrices(results, result_dir / f'btd_tsk_confusion_{dataset_name}.png')
    return {
        'results': results,
        'distiller': distiller,
    }


def main():
    dataset_name = DATASET_CONFIG['name']
    records = DATASET_CONFIG['records']
    run_one_dataset(dataset_name, records, save_student_model=True)


if __name__ == '__main__':
    main()
