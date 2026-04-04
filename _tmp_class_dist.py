import numpy as np
from data_processor import build_dataset

datasets = {
    'Data-1': ['slp01a','slp01b','slp02a','slp02b','slp03'],
    'Data-2': ['slp04','slp14','slp16','slp32','slp37'],
    'Data-3': ['slp41','slp45','slp48','slp59'],
    'Data-4': ['slp60','slp61','slp66'],
}

for name, recs in datasets.items():
    X_train, X_test, y_train, y_test = build_dataset(
        r'f:\\sleep\\data', recs, n_components=10, class_mode='five_class', feature_mode='handcrafted'
    )
    train_counts = np.bincount(y_train, minlength=5)
    test_counts = np.bincount(y_test, minlength=5)
    print(name)
    print('  train_counts', train_counts.tolist())
    print('  test_counts ', test_counts.tolist())