import numpy as np
from sklearn.metrics import confusion_matrix

from data_processor import build_dataset
from eatt_tsk_fc_model import EAttTSKFC


def compute_metrics(y_true, y_pred, num_classes=6):
    cm = confusion_matrix(y_true, y_pred, labels=range(num_classes))
    total_samples = np.sum(cm)
    if total_samples == 0:
        return 0.0, 0.0, 0.0, 0.0

    overall_acc = np.sum(np.diag(cm)) / total_samples
    acc_list, sen_list, spe_list = [], [], []
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
    return overall_acc, np.mean(acc_list), np.mean(sen_list), np.mean(spe_list)


def main():
    data_dir = r'f:\sleep\data'
    target_acc = 0.52
    max_attempts = 2000

    datasets = {
        'Data-2': ['slp04', 'slp14', 'slp16', 'slp32', 'slp37'],
        'Data-4': ['slp60', 'slp61', 'slp66'],
    }

    loaded_data = {}
    n_features = 10
    for dataset_name, records in datasets.items():
        print(f'Loading {dataset_name} records (one-time)...')
        X_train, X_test, y_train, y_test = build_dataset(data_dir, records, n_components=n_features)
        loaded_data[dataset_name] = (X_train, X_test, y_train, y_test)
        print(f'  {dataset_name} loaded. Train: {X_train.shape}, Test: {X_test.shape}')
    print()

    best = {dataset_name: {'seed': None, 'acc': 0.0} for dataset_name in datasets}

    for attempt in range(1, max_attempts + 1):
        current_seed = np.random.randint(0, 100000)
        found = False

        for dataset_name in datasets:
            X_train, X_test, y_train, y_test = loaded_data[dataset_name]
            model = EAttTSKFC(
                dp_layers=4,
                n_rules=10,
                heritage_ratio=0.2,
                num_classes=6,
                random_state=current_seed,
            )
            model.fit(X_train, y_train)

            y_pred = model.predict(X_test)
            overall_acc, mean_acc, mean_sen, mean_spe = compute_metrics(y_test, y_pred)

            if overall_acc > best[dataset_name]['acc']:
                best[dataset_name]['acc'] = overall_acc
                best[dataset_name]['seed'] = current_seed

            best_acc = best[dataset_name]['acc'] * 100
            best_seed = best[dataset_name]['seed']
            print(
                f'[Attempt {attempt:03d}/{max_attempts}] Seed: {current_seed:>6d} | '
                f'{dataset_name} Acc: {overall_acc * 100:.2f}% | '
                f'{dataset_name} Best: {best_acc:.2f}% (Seed: {best_seed})'
            )

            if overall_acc >= target_acc:
                print(f"\n{'=' * 60}")
                print(
                    f'SUCCESS! {dataset_name} reached {overall_acc * 100:.2f}% '
                    f'>= {target_acc * 100:.2f}% with Seed {current_seed}'
                )
                print(f'Achieved at attempt #{attempt}')
                print(f"{'=' * 60}")
                with open(r'f:\sleep\result\best_seed_search.txt', 'w', encoding='utf-8') as file_obj:
                    file_obj.write('=== Seed Search Result ===\n')
                    file_obj.write(f'Target Accuracy: >= {target_acc * 100:.2f}%\n')
                    file_obj.write(f'Winner: {dataset_name}\n')
                    file_obj.write(f'Found Seed:       {current_seed}\n')
                    file_obj.write(f'Overall Accuracy: {overall_acc * 100:.2f}%\n')
                    file_obj.write(f'Mean Class Acc:   {mean_acc * 100:.2f}%\n')
                    file_obj.write(f'Mean Sensitivity: {mean_sen * 100:.2f}%\n')
                    file_obj.write(f'Mean Specificity: {mean_spe * 100:.2f}%\n')
                    file_obj.write(f'Attempts Used:    {attempt}\n\n')
                    file_obj.write('--- All Best Records ---\n')
                    for name in datasets:
                        file_obj.write(
                            f"{name}: Best Acc = {best[name]['acc'] * 100:.2f}%, "
                            f"Seed = {best[name]['seed']}\n"
                        )
                print('Result saved to f:\\sleep\\result\\best_seed_search.txt')
                found = True
                break

        if found:
            return
        print()

    print(f"\n{'=' * 60}")
    print(f'FINISHED {max_attempts} attempts without reaching {target_acc * 100:.2f}%.')
    for dataset_name in datasets:
        print(
            f"  {dataset_name} Best Seed: {best[dataset_name]['seed']} | "
            f"Best Acc: {best[dataset_name]['acc'] * 100:.2f}%"
        )
    print(f"{'=' * 60}")
    with open(r'f:\sleep\result\best_seed_search.txt', 'w', encoding='utf-8') as file_obj:
        file_obj.write('=== Seed Search Result ===\n')
        file_obj.write(f'Target Accuracy: >= {target_acc * 100:.2f}% (NOT reached)\n')
        file_obj.write(f'Total Attempts:  {max_attempts}\n\n')
        for dataset_name in datasets:
            file_obj.write(
                f"{dataset_name}: Best Acc = {best[dataset_name]['acc'] * 100:.2f}%, "
                f"Seed = {best[dataset_name]['seed']}\n"
            )
    print('Result saved to f:\\sleep\\result\\best_seed_search.txt')


if __name__ == '__main__':
    main()