# EAtt-TSK-FC 详细实现文档（代码级）

## 1. 项目目标与当前版本定位

当前实现的模型名称：`EAtt-TSK-FC`

含义：
- `E` = Elite（精英规则继承）
- `Att` = Attention（基于熵的层间融合）
- `TSK-FC` = 多层模糊规则分类框架

当前主流程默认设置：
- 分类任务：`five_class`（W / N1 / N2 / N3 / R）
- 特征模式：`handcrafted`（单通道 EEG 13 维轻量特征）
- 层数：`dp_layers=2`
- 继承策略：`elite`
- 融合策略：`entropy_attention`

---

## 2. 代码文件分工

### 2.1 `data_processor.py`
负责：
- EEG 读取与分段
- 预处理（带通 + 小波去噪）
- 特征提取（手工特征）或 KPCA 对照
- 标签映射（five_class / six_class）
- 训练测试切分与归一化

### 2.2 `tsk_classifier.py`
负责：
- 单层 `BaseTSK` 分类器
- 第一层前件参数学习（FCM）
- 触发强度计算
- 后件参数加权最小二乘求解

### 2.3 `eatt_tsk_fc_model.py`
负责：
- 多层训练/推理流程
- 精英规则继承
- 随机模糊新规则生成
- 短规则机制
- 残差学习
- 熵注意力融合

### 2.4 `main.py`
负责：
- 四个数据子集实验入口
- 参数配置
- 训练、评估与结果保存
- 混淆矩阵文本输出
- 四张混淆矩阵热力图拼图输出（2x2）

---

## 3. 数据处理与特征工程（`data_processor.py`）

### 3.1 读取与分段
1. 读取记录：`wfdb.rdrecord` 和 `wfdb.rdann(..., 'st')`
2. 自动找到 `EEG` 通道
3. 以 30 秒为一个 epoch（`epoch_len = 30 * fs`）
4. 使用注释标签生成类别标签

### 3.2 标签映射
`get_label_mapping(class_mode)` 支持：
- `five_class`：`{'W':0, '1':1, '2':2, '3':3, '4':3, 'R':4}`
- `six_class`：`{'W':0, '1':1, '2':2, '3':3, '4':4, 'R':5}`

### 3.3 信号预处理
每个 epoch 依次做：
1. 带通滤波：`0.5~30Hz`
2. 小波去噪：`db6`

### 3.4 手工特征（当前默认）
当前 `HANDCRAFTED_FEATURE_DIM = 13`。

13 维特征如下：
1. `delta_rel`（0.5-4Hz 相对功率）
2. `theta_rel`（4-8Hz 相对功率）
3. `alpha_rel`（8-13Hz 相对功率）
4. `beta_rel`（13-30Hz 相对功率）
5. `theta_alpha_ratio = theta_rel / alpha_rel`
6. `spectral_edge_95`（0.5-30Hz 95%谱边缘频率）
7. `spectral_entropy`
8. `RMS`
9. `std`
10. `Hjorth Activity`
11. `Hjorth Mobility`
12. `Hjorth Complexity`
13. `waveform_length`

#### 3.4.1 提取总流程（单个 epoch）
对每个 30 秒 EEG epoch，特征提取按以下顺序执行：
1. 带通滤波（0.5~30Hz）。
2. 小波去噪（db6，soft threshold）。
3. Welch 功率谱估计，得到 `freqs` 与 `psd`。
4. 频域特征计算（相对功率、比值、谱边缘频率、谱熵）。
5. 时域特征计算（RMS、标准差、波形长度）。
6. Hjorth 参数计算（Activity/Mobility/Complexity）。
7. 组合成固定顺序的 13 维向量。

代码对应函数：
- `process_record(...)`
- `extract_handcrafted_features(...)`
- `_relative_band_power(...)`
- `_spectral_edge_frequency(...)`

#### 3.4.2 Welch 功率谱参数
在 `extract_handcrafted_features` 中：
- 使用 `scipy.signal.welch(epoch_signal, fs=fs, nperseg=min(1024, len(epoch_signal)))`
- 为了数值稳定，执行 `psd = max(psd, 1e-12)`（逐点）

说明：
- `nperseg` 取 1024 或更短（当样本长度不足时），保证谱估计稳定。
- `1e-12` 避免后续 `log(0)` 或除 0。

#### 3.4.3 频带相对功率（4 维）
定义总功率：
`P_total = sum(psd) + 1e-12`

某频带相对功率：
`P_band_rel = sum(psd[f in band]) / P_total`

频带定义：
- Delta: 0.5-4Hz
- Theta: 4-8Hz
- Alpha: 8-13Hz
- Beta: 13-30Hz

得到：
- `delta_rel`
- `theta_rel`
- `alpha_rel`
- `beta_rel`

#### 3.4.4 REM 相关增强特征（2 维）
1. `theta_alpha_ratio`
- 公式：`theta_rel / (alpha_rel + 1e-12)`
- 目的：增强 REM 与部分 NREM 的区分信息。

2. `spectral_edge_95`
- 在 0.5-30Hz 频段内计算累积功率曲线。
- 找到累积功率达到 `95%` 总功率时对应的频率。
- 公式思想：`SEF95 = f_k, s.t. cumulative_power(f_k) >= 0.95 * total_band_power`

#### 3.4.5 谱熵（1 维）
先归一化功率谱：
`p_i = psd_i / sum(psd)`

再计算熵并归一化：
`spectral_entropy = -sum(p_i * log(p_i + 1e-12)) / log(len(psd))`

说明：
- 分母 `log(len(psd))` 将熵归一化到相近尺度。

#### 3.4.6 时域统计特征（3 维）
1. RMS
- `rms = sqrt(mean(x^2))`

2. 标准差
- `std = std(x)`

3. 波形长度
- 设一阶差分 `d1 = diff(x)`
- `waveform_length = sum(abs(d1))`

#### 3.4.7 Hjorth 参数（3 维）
设：
- `activity = var(x)`
- `d1 = diff(x)`
- `d2 = diff(d1)`
- `var_d1 = var(d1) + 1e-12`
- `var_d2 = var(d2) + 1e-12`

则：
1. Activity
- `activity = var(x)`

2. Mobility
- `mobility = sqrt(var_d1 / (activity + 1e-12))`

3. Complexity
- `complexity = sqrt(var_d2 / var_d1) / (mobility + 1e-12)`

#### 3.4.8 特征向量顺序（实现严格一致）
最终按以下顺序拼接（用于训练与推理一致性）：
1. delta_rel
2. theta_rel
3. alpha_rel
4. beta_rel
5. theta_alpha_ratio
6. spectral_edge_95
7. spectral_entropy
8. rms
9. std
10. activity
11. mobility
12. complexity
13. waveform_length

#### 3.4.9 空样本与异常保护
1. 若某条记录无有效 epoch：
- 输出空数组并在上层跳过该记录。

2. 若某些步骤可能出现数值异常：
- 统一通过 `+1e-12` 做防除零和防 `log(0)` 处理。

3. 当 epoch 数组为空时：
- `handcrafted` 模式返回形状 `(0, 13)` 的空特征矩阵，保证后续拼接不出错。

#### 3.4.10 每个特征“说明什么”与“为什么选”
本模型选择这 13 维特征的原则是：`生理意义明确 + 计算开销低 + 与睡眠分期有已知关联 + 对 TSK 规则可解释`。

| 特征 | 主要反映的信号属性 | 选择理由（与睡眠分期关系） |
| --- | --- | --- |
| `delta_rel` | 慢波能量占比 | N3（深睡）常见慢波增强，delta 相对功率有助于识别深睡相关状态。 |
| `theta_rel` | θ节律占比 | 困倦/浅睡阶段常伴随 theta 活动变化，对 N1/N2 与 REM 区分有价值。 |
| `alpha_rel` | α节律占比 | 清醒与部分轻睡阶段 alpha 特征存在差异，可辅助 W 与非 W 区分。 |
| `beta_rel` | β节律占比 | 高频活动可反映觉醒相关成分，补充低频特征不足。 |
| `theta_alpha_ratio` | θ 与 α 的相对关系 | 比值特征比单独功率更稳健，常用于强化 REM/浅睡与其他阶段分离。 |
| `spectral_edge_95` | 频谱累计能量边界位置 | 反映“能量重心偏高或偏低”，可捕捉不同阶段的频谱整体偏移。 |
| `spectral_entropy` | 频谱复杂度/无序度 | 睡眠阶段脑电复杂度不同，谱熵可提供跨频带的整体不确定性信息。 |
| `rms` | 信号整体幅值水平 | 与脑电振幅强弱相关，可补充纯频域信息。 |
| `std` | 波动离散程度 | 与 RMS 类似但统计意义不同，增强幅值分布刻画。 |
| `activity` (Hjorth) | 方差能量 | Hjorth 系列中最基础的能量指标，计算简单、解释性强。 |
| `mobility` (Hjorth) | 一阶变化速率 | 反映信号“快慢变化”特性，对不同阶段节律变化敏感。 |
| `complexity` (Hjorth) | 波形形态复杂度 | 描述波形相对正弦模型的复杂程度，补充线性统计特征。 |
| `waveform_length` | 时间域粗糙度/曲折度 | 对波形细碎程度敏感，常用于区分节律平滑与不规则状态。 |

从建模角度看，这组特征同时覆盖了：
1. 频域能量分布（4个相对功率 + 2个REM/频谱增强特征 + 谱熵）
2. 时域幅值统计（RMS、STD、波形长度）
3. 动态形态统计（Hjorth 三参数）

这样做的好处是：
1. 比“仅 KPCA 降维后不可解释特征”更容易解释每条模糊规则的生理含义。
2. 维度仍然较低（13维），适合 TSK 规则学习，计算成本也可控。
3. 对少数类（尤其 REM）可提供更直接的判别信息（比值与谱边缘频率）。

### 3.5 对照模式（KPCA）
`feature_mode='kpca'` 时：
- 输入原始 epoch 波形
- 执行 `KernelPCA(n_components=..., kernel='rbf')`
- 用于对照实验，不是默认主路径

### 3.6 归一化与切分
- `MinMaxScaler`
- `train_test_split(test_size=0.25, random_state=42)`

---

## 4. 单层 TSK 实现（`tsk_classifier.py`）

### 4.1 前件（不改第一层逻辑）
`BaseTSK.fit` 中第一层前件保留原方案：
- 用 FCM 聚类得到规则中心 `a`
- 用簇内离散度估计每条规则每个特征的 `sigma`

### 4.2 触发强度
对每条规则 `l` 计算：
- `dist = -((X - a_l)^2) / (2*sigma_l^2)`
- `H[:, l] = exp(sum(dist))`

说明：
- 当某些维度 `sigma` 非常大（如 `1e9`）时，该维度在该规则中近似“忽略”。

### 4.3 后件求解
后件参数 `beta` 用正则化最小二乘：
- 可选样本权重 `sample_weight`
- 使用加权后的 `H` 和 `Y` 求伪逆解

---

## 5. 多层 EAtt-TSK-FC（`eatt_tsk_fc_model.py`）

### 5.1 关键超参数（默认）
- `dp_layers=2`
- `n_rules=10`
- `heritage_ratio=0.25`
- `inheritance_mode='elite'`
- `fusion_mode='entropy_attention'`
- `class_balanced=False`
- `short_rule_ratio=0.1`
- `drop_feature_ratio=0.2`
- `alpha=0.1`

### 5.2 类别权重（可选）
当 `class_balanced=True` 时，样本权重流程：
1. 逆频率权重 `raw = total/(C*n_c)`
2. 幂次平滑 `raw^class_weight_power`
3. 截断 `clip(min,max)`
4. 再归一化到均值为 1

默认关闭，避免过强加权导致类别塌缩。

### 5.3 深层新规则生成
对每个新规则：
- 中心 `a` 在特征范围内均匀采样
- 宽度 `sigma` 在 `0.1*span ~ 0.5*span` 采样

### 5.4 短规则
- 按 `short_rule_ratio` 概率把一条规则变成短规则
- 随机选部分维度把 `sigma` 置为 `1e9`

### 5.5 精英规则继承
从上一层规则中继承 `num_inherited = floor(n_rules * heritage_ratio)` 条规则：
- 计算上一层激活矩阵 `H_prev`
- 规则分数 `scores = H_prev^T * sample_weight`
- 按分数降序选 Top-K
- 继承前件 `a/sigma`，后件 `beta` 在当前层重新学习

### 5.6 残差学习
- 第 1 层拟合 `Y_onehot`
- 第 2 层及以后拟合 `residual_target = Y_onehot - cumulative_output`

### 5.7 层间输入
默认：
- `X_next = concat(X_original, alpha * layer_output)`

可选：
- `use_projection=True` 时可用随机投影矩阵

### 5.8 熵注意力融合
推理阶段收集每层输出后：
1. 每层做 softmax 得到概率
2. 计算每层熵并归一化
3. 通过 `exp(-entropy / temperature)` 归一化成注意力
4. 按注意力加权求和得到最终概率

---

## 6. 训练与评估主流程（`main.py`）

### 6.1 数据集配置
当前内置四组数据：`Data-1` 到 `Data-4`。
每组可单独设置：
- `class_mode`
- `feature_mode`
- `dp_layers`
- `n_rules`
- `heritage_ratio`
- `num_classes`
- 权重、短规则、融合相关参数

### 6.2 每个数据集实验步骤
1. 数据加载与特征提取
2. 训练 `EAttTSKFC`
3. 保存模型 `.joblib`
4. 测试集评估
5. 保存文本结果、混淆矩阵、规则解释

### 6.3 指标
`compute_metrics` 输出：
- Overall Accuracy
- Mean Class Accuracy
- Mean Sensitivity
- Mean Specificity
- Macro F1
- Confusion Matrix

---

## 7. 输出文件说明

运行 `main.py` 后，结果保存在 `f:\sleep\result`：

1. `evaluation_metrics.txt`
- 四个数据集的完整指标和混淆矩阵

2. `confusion_matrix_Data-*.txt`
- 每个数据集单独混淆矩阵文本

3. `rules_Data-*.txt`
- 每层每条规则的语言解释

4. `confusion_matrices_grid.png`
- 四个数据集混淆矩阵热力图拼图（2x2）

---

## 8. 当前版本关键实现点总结

1. 第一层前件求解保持原实现（FCM）
2. 深层规则：精英继承 + 随机新规则
3. 深层学习目标：残差
4. 融合：熵注意力
5. 默认特征：13维手工特征（包含 REM 相关 2 维）
6. KPCA 保留为对照路径
7. 输出：文本 + 四宫格热力图

---

## 9. 复现实验命令

在当前环境执行：

```powershell
conda run -n sleep python main.py
```

对比层数实验：

```powershell
conda run -n sleep python compare_dp_layers.py
```

---

## 10. 备注（你论文里可直接写）

1. 当前单通道 EEG 对某些阶段天然可分性有限，尤其少数类召回可能偏低。
2. 引入 REM 相关特征（theta/alpha、谱边缘频率）后，模型对 REM 的建模信息更充分。
3. 结果输出已支持“多数据集统一热力图展示”，便于论文横向比较。
