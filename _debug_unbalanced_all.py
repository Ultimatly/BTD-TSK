import numpy as np
from data_processor import build_dataset
from eatt_tsk_fc_model import EAttTSKFC

datasets = {
    'Data-1': ['slp01a','slp01b','slp02a','slp02b','slp03'],
    'Data-2': ['slp04','slp14','slp16','slp32','slp37'],
    'Data-3': ['slp41','slp45','slp48','slp59'],
    'Data-4': ['slp60','slp61','slp66'],
}
seeds = {'Data-1':28738,'Data-2':4835,'Data-3':76965,'Data-4':67906}

for name, records in datasets.items():
    X_train, X_test, y_train, y_test = build_dataset(r'f:\sleep\data', records, n_components=10, class_mode='five_class')
    m = EAttTSKFC(dp_layers=2,n_rules=10,heritage_ratio=0.25,num_classes=5,random_state=seeds[name],class_balanced=False,fusion_mode='entropy_attention')
    m.fit(X_train,y_train)
    pred=m.predict(X_test)
    print(name, 'acc', (pred==y_test).mean())