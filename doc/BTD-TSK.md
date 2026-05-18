# BTD-TSK 模型流程、数据处理与特征说明

## 1. 当前文档是否对应最终模型

是。

本文档现在对应项目中的**当前最终模型流程**，即：

- 数据集划分：`Data-A` 与 `Data-B`
- 教师模型：`BiLSTM`
- 学生模型：`BTD-TSK`
- 前件生成：**教师隐藏表示引导的类别内原型前件**
- 后件训练：**标准交叉熵 + KL 散度蒸馏**
- 最终部署：**仅保留学生模型**

对应代码主文件：

- [F:\sleep\src\train_btd_tsk_distill.py](F:/sleep/src/train_btd_tsk_distill.py)
- [F:\sleep\src\btd_tsk.py](F:/sleep/src/btd_tsk.py)
- [F:\sleep\src\btd_teacher.py](F:/sleep/src/btd_teacher.py)
- [F:\sleep\src\data_processor.py](F:/sleep/src/data_processor.py)

---

## 2. 模型总体流程

BTD-TSK 的整体思路可以概括为：

1. 从原始睡眠记录中提取 EEG 与 ECG 的多源数据工程化特征。
2. 用 `BiLSTM` 教师学习局部时序上下文知识。
3. 用教师隐藏表示指导 `TSK` 学生前件规则原型的生成。
4. 用标准 `CE + KL` 将教师输出知识蒸馏到学生后件。
5. 推理阶段仅保留可解释的 `TSK` 学生模型。

整体可写成：

$$
\text{原始 EEG/ECG 信号}
\rightarrow
\text{多源数据工程化特征}
\rightarrow
\begin{cases}
\text{BiLSTM 教师}\\
\text{BTD-TSK 学生}
\end{cases}
\rightarrow
\text{蒸馏训练}
\rightarrow
\text{最终 BTD-TSK 学生}
$$

---

## 3. 数据集划分

项目当前只使用两个数据集划分：

### 3.1 Data-A

`slp01a, slp02a, slp02b, slp14, slp32, slp37, slp41, slp45, slp60`

### 3.2 Data-B

`slp01b, slp03, slp04, slp16, slp48, slp59, slp61, slp66, slp67x`

这两个分组的目标是：

- 保持样本量尽量接近
- 保持五个睡眠阶段比例尽量接近
- 兼顾实验多样性

---

## 4. 符号定义

设：

- $N$：训练样本数
- $C$：类别数，固定为 $5$
- $R$：规则数，当前固定为 $10$
- $d$：输入特征维度，当前固定为 $22$
- $\mathbf{x}_i \in \mathbb{R}^d$：第 $i$ 个样本的 22 维特征向量
- $y_i \in \{1,2,\dots,C\}$：第 $i$ 个样本的真实类别
- $\mathbf{y}_i \in \{0,1\}^C$：第 $i$ 个样本的 one-hot 标签
- $\mathbf{z}_i^T$：教师模型对第 $i$ 个样本输出的 logits
- $\mathbf{z}_i^S$：学生模型对第 $i$ 个样本输出的 logits
- $\mathbf{p}_i^T$：教师普通 softmax 概率
- $\mathbf{p}_i^S$：学生普通 softmax 概率
- $\tilde{\mathbf{p}}_i^T(\tau)$：教师温度 softmax 概率
- $\tilde{\mathbf{p}}_i^S(\tau)$：学生温度 softmax 概率
- $\tau$：蒸馏温度，当前固定为 $1.5$

其中 one-hot 标签满足：

$$
y_{i,c} =
\begin{cases}
1, & \text{若样本 } i \text{ 属于类别 } c \\
0, & \text{否则}
\end{cases}
$$

---

## 5. 数据处理详细过程

数据处理主要在 [F:\sleep\src\data_processor.py](F:/sleep/src/data_processor.py) 中完成。

### 5.1 原始记录读取

对每条记录 `record_name`，读取：

- 生理信号：`wfdb.rdrecord(record_path)`
- 睡眠标注：`wfdb.rdann(record_path, 'st')`

然后自动搜索：

- EEG 通道
- ECG/EKG 通道

若未找到 ECG 通道，则 ECG 特征补零。

### 5.2 30 秒 epoch 切分

睡眠分期以 30 秒为一个 epoch。

设采样率为 $f_s$，则每个 epoch 的采样点数为：

$$
L = 30 \times f_s
$$

若第 $i$ 个 epoch 的起始采样点为 $s_i$，则该 epoch 的信号片段为：

$$
\mathbf{u}_i = [u(s_i), u(s_i+1), \dots, u(s_i+L-1)]
$$

### 5.3 标签映射

当前五分类映射为：

- `W -> 0`
- `1 -> 1`，即 `N1`
- `2 -> 2`，即 `N2`
- `3 -> 3`，即 `N3`
- `4 -> 3`，即把 `S4` 并入 `N3`
- `R -> 4`

即最终类别集合为：

$$
\{W, N1, N2, N3, R\}
$$

### 5.4 EEG 预处理

对每个 EEG epoch，先做带通滤波：

$$
\mathbf{u}_i^{(bp)} = \text{BandPass}(\mathbf{u}_i; 0.5, 30.0)
$$

再做小波去噪：

$$
\mathbf{u}_i^{(den)} = \text{WaveletDenoise}(\mathbf{u}_i^{(bp)})
$$

当前使用：

- Butterworth 带通滤波器
- `db6` 小波进行软阈值去噪

### 5.5 EEG 特征提取

对去噪后的 EEG epoch 提取 13 维特征：

$$
\mathbf{x}_i^{EEG} \in \mathbb{R}^{13}
$$

频域特征基于 Welch 功率谱估计：

$$
\text{PSD}_i(f) = \text{Welch}(\mathbf{u}_i^{(den)})
$$

### 5.6 ECG 特征提取

对 ECG epoch：

1. 带通滤波
2. 差分与能量包络增强
3. R 峰检测
4. RR 间期清洗
5. 提取 HRV 特征

得到：

$$
\mathbf{x}_i^{ECG} \in \mathbb{R}^{9}
$$

### 5.7 多源数据特征拼接

最终 22 维输入向量为：

$$
\mathbf{x}_i =
\left[
\mathbf{x}_i^{EEG},
\mathbf{x}_i^{ECG}
\right]
\in \mathbb{R}^{22}
$$

### 5.8 训练测试划分与归一化

对某个数据集分组内的所有样本先做索引划分：

$$
\mathcal{D} = \mathcal{D}_{train} \cup \mathcal{D}_{test}
$$

然后只用训练集拟合 `MinMaxScaler`：

$$
\mathbf{x}_{i,j}^{norm}
=
\frac{x_{i,j} - x_j^{min}}
{x_j^{max} - x_j^{min} + \varepsilon}
$$

其中：

- $x_j^{min}$：训练集第 $j$ 维最小值
- $x_j^{max}$：训练集第 $j$ 维最大值

---

## 6. 22 个特征的含义

当前最终输入特征一共 22 维，前 13 维来自 EEG，后 9 维来自 ECG。

### 6.1 EEG 特征（13 维）

#### 1. EEG 相对 $\delta$ 波功率

$$
P_\delta^{rel} = \frac{\sum_{f\in[0.5,4)} \text{PSD}(f)}
{\sum_{f} \text{PSD}(f)}
$$

含义：反映慢波活动强度，通常与深睡眠相关。

#### 2. EEG 相对 $\theta$ 波功率

$$
P_\theta^{rel} = \frac{\sum_{f\in[4,8)} \text{PSD}(f)}
{\sum_{f} \text{PSD}(f)}
$$

含义：反映浅睡与过渡期节律活跃程度。

#### 3. EEG 相对 $\alpha$ 波功率

$$
P_\alpha^{rel} = \frac{\sum_{f\in[8,13)} \text{PSD}(f)}
{\sum_{f} \text{PSD}(f)}
$$

含义：常与W闭眼状态相关。

#### 4. EEG 相对 $\beta$ 波功率

$$
P_\beta^{rel} = \frac{\sum_{f\in[13,30)} \text{PSD}(f)}
{\sum_{f} \text{PSD}(f)}
$$

含义：较高频节律，常与觉醒和肌电干扰有关。

#### 5. EEG $\theta/\alpha$ 功率比

$$
R_{\theta/\alpha} = \frac{P_\theta^{rel}}{P_\alpha^{rel} + \varepsilon}
$$

含义：刻画浅睡与W之间的相对变化关系。

#### 6. EEG 谱边缘频率 SEF95

SEF95 为累计谱功率达到 95% 时对应的频率：

$$
\int_{0}^{f_{SEF95}} \text{PSD}(f)\,df
=
0.95
\int_{0}^{f_{max}} \text{PSD}(f)\,df
$$

含义：刻画频谱能量的整体分布上界。

#### 7. EEG 谱熵

设归一化谱概率为：

$$
q_k = \frac{\text{PSD}_k}{\sum_m \text{PSD}_m}
$$

则谱熵为：

$$
H_{spec} = -\frac{\sum_k q_k \log(q_k + \varepsilon)}{\log K}
$$

含义：反映频谱复杂度，越高表示频谱越分散。

#### 8. EEG 均方根值

$$
\text{RMS} = \sqrt{\frac{1}{L}\sum_{t=1}^{L} u_t^2}
$$

含义：反映信号整体能量水平。

#### 9. EEG 标准差

$$
\sigma = \sqrt{\frac{1}{L}\sum_{t=1}^{L}(u_t-\bar u)^2}
$$

含义：反映波动幅度大小。

#### 10. EEG Hjorth 活动度

$$
\text{Activity} = \text{Var}(u)
$$

含义：反映信号总体活动强度。

#### 11. EEG Hjorth 移动度

$$
\text{Mobility} =
\sqrt{
\frac{\text{Var}(u')}
{\text{Var}(u)+\varepsilon}
}
$$

含义：反映信号平均频率特征。

#### 12. EEG Hjorth 复杂度

$$
\text{Complexity} =
\frac{
\sqrt{\frac{\text{Var}(u'')}{\text{Var}(u')+\varepsilon}}
}{
\text{Mobility}+\varepsilon
}
$$

含义：反映信号波形复杂程度。

#### 13. EEG 波形长度

$$
\text{WL} = \sum_{t=2}^{L} |u_t-u_{t-1}|
$$

含义：反映波形整体起伏程度。

### 6.2 ECG 特征（9 维）

设检测出的 RR 间期序列为：

$$
\mathbf{r} = [r_1, r_2, \dots, r_M]
$$

#### 14. ECG 平均心率

$$
HR = \frac{60}{\bar r + \varepsilon}
$$

含义：平均心率水平。

#### 15. ECG SDNN

$$
SDNN = \text{Std}(\mathbf{r})
$$

含义：整体心率变异性。

#### 16. ECG RMSSD

$$
RMSSD = \sqrt{\frac{1}{M-1}\sum_{k=2}^{M}(r_k-r_{k-1})^2}
$$

含义：反映短时副交感活动。

#### 17. ECG pNN50

$$
pNN50 = \frac{1}{M-1}\sum_{k=2}^{M}\mathbb{I}(|r_k-r_{k-1}|>0.05)
$$

含义：相邻 RR 差异超过 50 ms 的比例。

#### 18. ECG RR 变异系数

$$
CV_{RR} = \frac{SDNN}{\bar r + \varepsilon}
$$

含义：标准差相对于均值的归一化波动程度。

#### 19. ECG SDSD

$$
SDSD = \text{Std}(r_k-r_{k-1})
$$

含义：相邻 RR 差分序列的波动程度。

#### 20. ECG RR 中位绝对偏差

$$
MAD_{RR} = \text{median}(|r_k-\text{median}(\mathbf{r})|)
$$

含义：稳健地刻画 RR 波动。

#### 21. ECG LF/HF 比值

若 LF 与 HF 功率分别为：

$$
P_{LF}, \quad P_{HF}
$$

则：

$$
\frac{LF}{HF} = \frac{P_{LF}}{P_{HF} + \varepsilon}
$$

含义：反映交感/副交感平衡。

#### 22. ECG HF 归一化功率

$$
HF_{norm} = \frac{P_{HF}}{P_{LF}+P_{HF}+\varepsilon}
$$

含义：反映高频副交感成分在总功率中的相对占比。

---

## 7. 教师模型：BiLSTM

### 7.1 教师输入窗口

教师不只看当前样本，而是看半径为 $r=2$ 的局部时序窗口：

$$
\mathbf{X}_i^T =
[\mathbf{x}_{i-2}, \mathbf{x}_{i-1}, \mathbf{x}_{i}, \mathbf{x}_{i+1}, \mathbf{x}_{i+2}]
\in \mathbb{R}^{L\times d}
$$

其中：

- $L = 2r+1 = 5$

### 7.2 双向 LSTM 递推

前向 LSTM：

$$
\mathbf{h}_t^{(f)} = \text{LSTM}_{forward}(\mathbf{x}_t, \mathbf{h}_{t-1}^{(f)})
$$

后向 LSTM：

$$
\mathbf{h}_t^{(b)} = \text{LSTM}_{backward}(\mathbf{x}_t, \mathbf{h}_{t+1}^{(b)})
$$

中心时刻隐藏表示为：

$$
\mathbf{h}_i^T = [\mathbf{h}_i^{(f)};\mathbf{h}_i^{(b)}]
$$

### 7.3 教师输出

教师 logits：

$$
\mathbf{z}_i^T = \mathbf{W}_T \mathbf{h}_i^T + \mathbf{b}_T
$$

教师普通概率：

$$
\mathbf{p}_i^T = \text{softmax}(\mathbf{z}_i^T)
$$

温度概率：

$$
\tilde{\mathbf{p}}_i^T(\tau)
=
\text{softmax}\left(\frac{\mathbf{z}_i^T}{\tau}\right)
$$

---

## 8. 学生模型：BTD-TSK

### 8.1 规则形式

第 $r$ 条零阶 TSK 规则写成：

$$
\mathcal{R}_r:
\text{IF } \mathbf{x} \text{ is } A_r
\text{ THEN } \mathbf{b}_r
$$

其中：

- $A_r$：第 $r$ 条规则前件
- $\mathbf{b}_r \in \mathbb{R}^{C}$：第 $r$ 条规则后件类别向量

### 8.2 高斯前件激活

设：

- $a_{r,j}$：第 $r$ 条规则第 $j$ 维中心
- $\sigma_{r,j}$：第 $r$ 条规则第 $j$ 维宽度

则样本 $\mathbf{x}_i$ 对规则 $r$ 的原始激活度为：

$$
\mu_{i,r}
=
\exp\left(
-\sum_{j=1}^{d}
\frac{(x_{i,j}-a_{r,j})^2}
{2\sigma_{r,j}^2}
\right)
$$

归一化后：

$$
h_{i,r}
=
\frac{\mu_{i,r}}
{\sum_{k=1}^{R}\mu_{i,k}+\varepsilon}
$$

记规则激活向量为：

$$
\mathbf{h}_i = [h_{i,1},h_{i,2},\dots,h_{i,R}]^\top
$$

### 8.3 学生输出

设所有规则后件矩阵为：

$$
\mathbf{B}
=
\begin{bmatrix}
\mathbf{b}_1^\top\\
\mathbf{b}_2^\top\\
\vdots\\
\mathbf{b}_R^\top
\end{bmatrix}
\in \mathbb{R}^{R\times C}
$$

则学生 logits 为：

$$
\mathbf{z}_i^S = \mathbf{h}_i^\top \mathbf{B}
$$

普通概率：

$$
\mathbf{p}_i^S = \text{softmax}(\mathbf{z}_i^S)
$$

温度概率：

$$
\tilde{\mathbf{p}}_i^S(\tau)
=
\text{softmax}\left(\frac{\mathbf{z}_i^S}{\tau}\right)
$$

---

## 9. 教师隐藏表示引导的前件生成

这是当前最终模型与普通 `TSK-LLM` / `TSK-GD` 的关键区别。

### 9.1 类别规则配额

总规则数固定为 $R=10$，类别数固定为 $C=5$。

先保证每类至少一条规则：

$$
R_c \ge 1,\qquad \sum_{c=1}^{C}R_c = R
$$

剩余规则按类别样本比例分配。设第 $c$ 类样本数为 $n_c$，则：

$$
\pi_c = \frac{n_c}{\sum_{m=1}^{C}n_m}
$$

类别配额近似为：

$$
R_c = 1 + \text{round}\left((R-C)\pi_c\right)
$$

### 9.2 教师可信度权重

对真实属于第 $c$ 类的样本 $i$，教师对真实类的支持度为：

$$
p_{i,c}^T
$$

教师熵为：

$$
\mathcal{H}(\mathbf{p}_i^T)
=
-\sum_{m=1}^{C}p_{i,m}^T\log(p_{i,m}^T+\varepsilon)
$$

归一化熵为：

$$
\bar{\mathcal{H}}(\mathbf{p}_i^T)
=
\frac{\mathcal{H}(\mathbf{p}_i^T)}{\log C}
$$

样本权重定义为：

$$
w_i
=
\alpha p_{i,c}^T
+
(1-\alpha)\left(1-\bar{\mathcal{H}}(\mathbf{p}_i^T)\right)
$$

其中：

- $\alpha$：引导权重系数，当前固定为 $0.7$

### 9.3 在教师隐藏空间中做类别内聚类

设第 $i$ 个样本对应的教师隐藏表示为：

$$
\mathbf{h}_i^T \in \mathbb{R}^{d_h}
$$

对第 $c$ 类样本集合：

$$
\mathcal{S}_c = \{i\mid y_i=c\}
$$

在集合 $\{\mathbf{h}_i^T \mid i\in\mathcal{S}_c\}$ 上做加权聚类，得到 $R_c$ 个子簇。

### 9.4 映射回原始特征空间构造规则中心与宽度

若类别 $c$ 的第 $r$ 个子簇样本集合为 $\mathcal{C}_{c,r}$，则其规则中心定义为：

$$
\mathbf{a}_{c,r}
=
\frac{
\sum_{i\in\mathcal{C}_{c,r}} w_i \mathbf{x}_i
}{
\sum_{i\in\mathcal{C}_{c,r}} w_i + \varepsilon
}
$$

第 $j$ 维宽度定义为：

$$
\sigma_{c,r,j}
=
\sqrt{
\frac{
\sum_{i\in\mathcal{C}_{c,r}}
w_i (x_{i,j}-a_{c,r,j})^2
}{
\sum_{i\in\mathcal{C}_{c,r}} w_i + \varepsilon
}
+
10^{-6}
}
$$

这样得到的规则前件仍然位于原始 22 维工程化特征空间中，因此仍然可解释。

---

## 10. 标准 CE + KL 蒸馏

### 10.1 交叉熵损失

$$
L_{CE}
=
-\frac{1}{N}
\sum_{i=1}^{N}\sum_{c=1}^{C}
y_{i,c}\log p_{i,c}^S
$$

作用：让学生预测贴近真实标签。

### 10.2 KL 蒸馏损失

$$
L_{KD}
=
\tau^2 \cdot \frac{1}{N}
\sum_{i=1}^{N}
KL\left(
\tilde{\mathbf{p}}_i^T(\tau)
\parallel
\tilde{\mathbf{p}}_i^S(\tau)
\right)
$$

展开为：

$$
L_{KD}
=
\tau^2 \cdot \frac{1}{N}
\sum_{i=1}^{N}\sum_{c=1}^{C}
\tilde p_{i,c}^T(\tau)
\log
\frac{\tilde p_{i,c}^T(\tau)}
{\tilde p_{i,c}^S(\tau)+\varepsilon}
$$

作用：让学生学习教师的软输出分布。

### 10.3 总损失

$$
L = \lambda_{CE}L_{CE} + \lambda_{KD}L_{KD}
$$

当前固定参数为：

$$
\lambda_{CE}=1.0,\qquad \lambda_{KD}=0.1,\qquad \tau=1.5
$$

---

## 11. 当前最终训练参数

当前项目固定参数如下：

- `seed = 42`
- `n_rules = 10`
- `lr = 0.02`
- `reg = 1e-5`
- `batch_size = 128`
- `max_epochs = 200`
- `patience = 20`
- `selection_metric = loss`
- `teacher_temperature = 1.5`
- `lambda_ce = 1.0`
- `lambda_kd = 0.1`
- `guidance_alpha = 0.7`

---

## 12. 一个带具体数字的求解示例

下面给出一个简化示例，用来说明“教师引导前件 + 学生蒸馏”的数值过程。

### 12.1 假设某个样本的真实类别为 N2

设其 3 维简化特征为：

$$
\mathbf{x}_i = [0.42,\,0.31,\,0.27]
$$

这里只演示 3 维，实际项目中是 22 维。

### 12.2 教师输出

教师 logits 为：

$$
\mathbf{z}_i^T = [0.2,\,0.8,\,1.5,\,0.1,\,0.4]
$$

普通 softmax 后：

$$
\mathbf{p}_i^T \approx
[0.119,\ 0.217,\ 0.437,\ 0.108,\ 0.119]
$$

即教师认为该样本最可能属于 `N2`。

教师熵约为：

$$
\mathcal{H}(\mathbf{p}_i^T)\approx 1.46
$$

五分类最大熵为：

$$
\log 5 \approx 1.609
$$

归一化熵：

$$
\bar{\mathcal{H}}(\mathbf{p}_i^T)
\approx
\frac{1.46}{1.609}
\approx 0.907
$$

若真实类别为 `N2`，则：

$$
p_{i,N2}^T = 0.437
$$

取 $\alpha = 0.7$，则该样本权重为：

$$
w_i = 0.7\times 0.437 + 0.3\times (1-0.907)
$$

$$
w_i \approx 0.306 + 0.028 = 0.334
$$

这说明该样本会以权重 0.334 参与 `N2` 类别内部原型生成。

### 12.3 某条规则对样本的激活

假设第 3 条规则的中心和宽度分别为：

$$
\mathbf{a}_3 = [0.40,\,0.28,\,0.30]
$$

$$
\boldsymbol{\sigma}_3 = [0.10,\,0.08,\,0.12]
$$

则第 3 条规则的未归一化激活度为：

$$
\mu_{i,3}
=
\exp\left(
-\frac{(0.42-0.40)^2}{2\times 0.10^2}
-\frac{(0.31-0.28)^2}{2\times 0.08^2}
-\frac{(0.27-0.30)^2}{2\times 0.12^2}
\right)
$$

分别计算：

$$
\frac{(0.02)^2}{2\times 0.01} = 0.02
$$

$$
\frac{(0.03)^2}{2\times 0.0064} \approx 0.0703
$$

$$
\frac{(-0.03)^2}{2\times 0.0144} \approx 0.0313
$$

总和约为：

$$
0.02 + 0.0703 + 0.0313 = 0.1216
$$

所以：

$$
\mu_{i,3} \approx e^{-0.1216} \approx 0.8855
$$

若所有规则的未归一化激活和为：

$$
\sum_{k=1}^{R}\mu_{i,k} = 2.60
$$

则归一化激活度：

$$
h_{i,3} = \frac{0.8855}{2.60} \approx 0.3406
$$

### 12.4 学生输出

假设 10 条规则的激活向量中，与当前样本最相关的前三条规则激活为：

$$
\mathbf{h}_i =
[0.12,\ 0.18,\ 0.34,\ 0.10,\ 0.08,\ 0.05,\ 0.04,\ 0.03,\ 0.03,\ 0.03]
$$

假设后件矩阵乘积后得到学生 logits：

$$
\mathbf{z}_i^S = [0.10,\ 0.65,\ 1.20,\ 0.05,\ 0.30]
$$

则学生普通 softmax 概率约为：

$$
\mathbf{p}_i^S \approx [0.129,\ 0.224,\ 0.388,\ 0.123,\ 0.136]
$$

学生当前也预测为 `N2`，但对 `N2` 的置信度还低于教师。

### 12.5 CE 损失

若真实标签是 `N2`，则 one-hot 为：

$$
\mathbf{y}_i = [0,0,1,0,0]
$$

交叉熵损失为：

$$
L_{CE}^{(i)} = -\log(0.388) \approx 0.947
$$

### 12.6 KL 蒸馏损失

取温度 $\tau = 1.5$。

教师温度概率：

$$
\tilde{\mathbf{p}}_i^T(1.5)
=
\text{softmax}(\mathbf{z}_i^T/1.5)
\approx
[0.149,\ 0.222,\ 0.355,\ 0.139,\ 0.165]
$$

学生温度概率：

$$
\tilde{\mathbf{p}}_i^S(1.5)
=
\text{softmax}(\mathbf{z}_i^S/1.5)
\approx
[0.154,\ 0.222,\ 0.320,\ 0.149,\ 0.155]
$$

则 KL 散度项约为：

$$
KL(\tilde{\mathbf{p}}_i^T \parallel \tilde{\mathbf{p}}_i^S)
\approx 0.0039
$$

乘上温度平方：

$$
L_{KD}^{(i)}
=
1.5^2 \times 0.0039
\approx 0.0088
$$

### 12.7 总损失

当前参数：

$$
\lambda_{CE}=1.0,\qquad \lambda_{KD}=0.1
$$

所以：

$$
L^{(i)} = 1.0\times 0.947 + 0.1\times 0.0088
$$

$$
L^{(i)} \approx 0.9479
$$

这说明：

- 交叉熵负责保证分类不偏离真实标签
- KL 负责把教师的软知识压给学生
- 前件则由教师隐藏表示先行指导，保证规则原型更合理

---

## 13. 小结

当前最终 BTD-TSK 的核心不是简单“BiLSTM + TSK”，而是三层耦合：

1. **多源数据工程化特征**提供可解释的输入表示  
2. **教师隐藏表示引导前件**保证规则原型更合理  
3. **标准 CE + KL 蒸馏后件**保证学生吸收教师输出知识  

因此，最终模型同时具备：

- 时序教师知识
- 可解释规则结构
- 多源数据特征表达
- 可部署的学生模型形式
