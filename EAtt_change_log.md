# EAtt-TSK-FC Change Log (Current Round)

Date: 2026-03-24

## 1. What was wrong

The very low accuracy was mainly caused by **over-strong class-balanced weighting** in the current implementation.

Quick check result (same data/same seed):
- `class_balanced=True` -> accuracy collapsed to around 10%~15% on some subsets
- `class_balanced=False` -> accuracy returned to a reasonable range (around 30%~50%)

So the key issue was not only model architecture, but also the weighting strategy being too aggressive.

## 2. Code changes made in this round

### A) `eatt_tsk_fc_model.py`

File: `f:\sleep\eatt_tsk_fc_model.py`

Changes:
1. Changed default setting:
- `class_balanced=True` -> `class_balanced=False`

2. Added configurable, tempered class-weight controls:
- `class_weight_power=0.5`
- `class_weight_min=0.5`
- `class_weight_max=2.0`

3. Updated sample-weight computation in `_compute_sample_weight`:
- old: direct inverse-frequency weight
- new: inverse-frequency -> power tempering -> clipping -> normalize-by-mean

Current logic:
- `raw_weights = total_samples / (num_classes * class_counts)`
- `class_weights = raw_weights ** class_weight_power`
- `class_weights = clip(class_weights, class_weight_min, class_weight_max)`
- `class_weights = class_weights / mean(class_weights)`

Goal:
- avoid over-correction and prediction collapse
- keep class balance as an optional/controlled mechanism for ablation

### B) `main.py`

File: `f:\sleep\main.py`

Changes:
1. Updated all dataset default configs:
- `class_balanced: False`

2. Added new class-weight config fields to each dataset config:
- `class_weight_power`
- `class_weight_min`
- `class_weight_max`

3. Passed new fields into model init (`EAttTSKFC(...)`).

4. Added these fields to training config print/output so each run is traceable.

### C) `compare_dp_layers.py`

File: `f:\sleep\compare_dp_layers.py`

Changes:
1. Updated comparison base config:
- `class_balanced: False`
- added `class_weight_power`, `class_weight_min`, `class_weight_max`

2. Passed these params into `EAttTSKFC(...)` in dp-layer comparison runs.

### D) `data_processor.py` (stability fix from this implementation phase)

File: `f:\sleep\data_processor.py`

Change:
- `KernelPCA(..., n_jobs=-1)` -> `KernelPCA(..., n_jobs=1)`

Reason:
- avoid Windows permission/thread-pipe issues during runtime in current environment

## 3. Re-test results (latest run)

Source run: `conda run -n sleep python main.py`

- Data-1 OA: **48.45%**
- Data-2 OA: **39.68%**
- Data-3 OA: **29.51%**
- Data-4 OA: **47.01%**

Average OA across 4 subsets: **41.16%**

Additional metrics are saved in:
- `f:\sleep\result\evaluation_metrics.txt`

## 4. Output files updated

- `f:\sleep\result\evaluation_metrics.txt`
- `f:\sleep\result\rules_Data-1.txt`
- `f:\sleep\result\rules_Data-2.txt`
- `f:\sleep\result\rules_Data-3.txt`
- `f:\sleep\result\rules_Data-4.txt`
- `f:\sleep\result\confusion_matrix_Data-1.txt`
- `f:\sleep\result\confusion_matrix_Data-2.txt`
- `f:\sleep\result\confusion_matrix_Data-3.txt`
- `f:\sleep\result\confusion_matrix_Data-4.txt`
- `f:\sleep\result\dp_layers_comparison.txt`

## 5. Notes

- There are temporary debug scripts in project root:
  - `_debug_config_check.py`
  - `_debug_fusion_check.py`
  - `_debug_unbalanced_all.py`
- They were used only for diagnosis and can be removed later.