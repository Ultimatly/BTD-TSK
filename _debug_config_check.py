import numpy as np
from data_processor import build_dataset
from eatt_tsk_fc_model import EAttTSKFC

data_dir = r'f:\sleep\data'
records = ['slp01a','slp01b','slp02a','slp02b','slp03']
X_train, X_test, y_train, y_test = build_dataset(data_dir, records, n_components=10, class_mode='five_class')

configs = [
    {'name':'L1_balanced', 'dp_layers':1, 'class_balanced':True, 'fusion_mode':'entropy_attention'},
    {'name':'L1_unbalanced', 'dp_layers':1, 'class_balanced':False, 'fusion_mode':'entropy_attention'},
    {'name':'L2_balanced_entropy', 'dp_layers':2, 'class_balanced':True, 'fusion_mode':'entropy_attention'},
    {'name':'L2_unbalanced_entropy', 'dp_layers':2, 'class_balanced':False, 'fusion_mode':'entropy_attention'},
    {'name':'L2_unbalanced_avg', 'dp_layers':2, 'class_balanced':False, 'fusion_mode':'avg'},
    {'name':'L3_unbalanced_avg', 'dp_layers':3, 'class_balanced':False, 'fusion_mode':'avg'},
]

for cfg in configs:
    m = EAttTSKFC(
        dp_layers=cfg['dp_layers'],
        n_rules=10,
        heritage_ratio=0.25,
        num_classes=5,
        random_state=28738,
        class_balanced=cfg['class_balanced'],
        fusion_mode=cfg['fusion_mode'],
    )
    m.fit(X_train, y_train)
    pred = m.predict(X_test)
    acc = (pred==y_test).mean()
    print(cfg['name'], acc)