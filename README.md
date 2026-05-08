# 多元数据睡眠障碍病症轻量化辅助诊断系统

## 项目简介

本项目围绕睡眠分期辅助分析任务，构建了一套“算法研究 + 系统落地”一体化的轻量化辅助诊断原型。项目以脑电信号（EEG）和心电信号（ECG）为输入来源，通过工程特征构建、`BiLSTM` 教师模型时序建模、`BTD-TSK` 学生模型蒸馏训练，以及前后端系统封装，形成可训练、可推理、可解释、可回看的完整流程。

项目当前对应的核心思路是：

- 利用 `BiLSTM` 教师模型学习局部时序上下文信息
- 利用教师隐藏表示引导规则前件生成
- 利用教师输出分布约束学生后件训练
- 最终仅保留零阶 `TSK` 学生模型用于部署
- 在系统侧提供患者管理、模型管理、诊断分析、规则解释和历史结果回看

本仓库适合用于：

- 睡眠分期 / 医学信号处理课程设计与毕业设计展示
- `TSK` 模糊分类器与知识蒸馏结合方案的工程实现参考
- 轻量可解释智能诊断原型的前后端一体化示例

## 项目特点

### 1. 算法与系统一体化

仓库不是单纯的模型训练代码，也不是单纯的展示页面，而是同时包含：

- 数据处理与特征提取
- `BiLSTM` 教师训练
- `BTD-TSK` 学生蒸馏训练
- 已训练模型推理
- FastAPI 后端服务
- Vue 3 前端工作台

### 2. 强调轻量化与可解释性

部署阶段不依赖完整教师网络，而是使用规则结构更清晰、参数量更小的零阶 `TSK` 学生模型。系统中可以直接展示规则条件、主导类别、阶段分布和历史结果，便于做可解释分析。

### 3. 面向真实数据流程

项目围绕公开多导睡眠图数据集 `MIT-BIH Polysomnographic Database` 的数据组织方式实现，支持：

- `WFDB` 记录对：`.dat + .hea`
- 单文件 `EDF`
- 睡眠阶段标注解析
- 整段记录的分期结果导出

## 技术栈

### 算法与数据处理

- Python 3
- NumPy / SciPy
- scikit-learn
- PyTorch
- scikit-fuzzy
- WFDB
- MNE
- PyWavelets
- Matplotlib

### 后端

- FastAPI
- Uvicorn
- SQLite
- Pydantic
- python-multipart

### 前端

- Vue 3
- Vue Router
- Vite
- Sass
- ECharts

## 核心算法说明

### 1. 多元特征构建

项目不是直接把原始整段波形端到端送入部署模型，而是先将每个 30 s epoch 转换为 22 维工程特征：

- 13 维 EEG 特征
  - 相对 δ / θ / α / β 功率
  - θ/α 比值
  - SEF95
  - 谱熵
  - RMS
  - 标准差
  - Hjorth 活动度 / 移动度 / 复杂度
  - 波形长度
- 9 维 ECG/HRV 特征
  - 平均心率
  - SDNN
  - RMSSD
  - pNN50
  - RR 变异系数
  - SDSD
  - RR 中位绝对偏差
  - LF/HF
  - HF 归一化功率

### 2. BiLSTM 教师模型

教师模型以局部序列窗口为输入，对中心 epoch 进行时序判别。当前实现中：

- 序列半径：`2`
- 窗口长度：`5`
- 教师结构：`BiLSTM`
- 作用：
  - 输出教师 logits
  - 输出教师概率分布
  - 输出隐藏表示，用于引导规则前件生成

### 3. BTD-TSK 学生模型

学生模型为最终部署模型，核心是零阶 `TSK` 模糊分类器。项目中主要通过两种方式利用教师知识：

- `BiLSTM` 教师引导的规则前件生成
- `BiLSTM` 教师知识引导的学生后件训练

这样做的目标是让规则模型不仅“可解释”，还尽可能保留时序判别能力。

### 4. 推理后处理

模型推理后还会进行轻量级后处理，包括：

- 滑动窗口平滑
- 不合理睡眠阶段跳变修正

其目的是提升整夜预测序列的连续性和系统展示稳定性。

## 系统功能

项目当前前后端已经实现以下主要能力：

- 首页概览：展示系统概况、近期趋势和近期分析记录
- 患者管理：新增、修改、删除、查看患者历史
- 模型管理：上传、更新、删除模型，并自动抽取规则
- 诊断分析：上传睡眠记录、创建异步诊断任务、查看进度
- 规则中心：浏览规则、查看规则细节
- 历史记录：查看历史分析结果、波形预览、CSV 导出
- 风险提示：根据阶段占比生成启发式辅助提示

## 目录结构

```text
sleep/
├─ backend/                    # FastAPI 后端
│  └─ app/
│     ├─ main.py               # API 入口
│     ├─ config.py             # 路径、常量、运行配置
│     ├─ database.py           # SQLite 表结构与连接管理
│     ├─ ml/                   # 推理与规则抽取
│     └─ services/             # 患者、模型、诊断、历史等服务
├─ frontend/                   # Vue 3 前端
│  ├─ src/api/                 # API 封装
│  ├─ src/views/               # 页面视图
│  ├─ src/components/          # 组件
│  └─ vite.config.js
├─ src/                        # 算法主代码
│  ├─ data_processor.py        # 数据读取与特征提取
│  ├─ btd_teacher.py           # BiLSTM 教师模型
│  ├─ btd_tsk.py               # BTD-TSK 学生模型与蒸馏训练
│  ├─ train_btd_tsk_distill.py # 主训练脚本
│  ├─ train_btd_tsk_all.py     # 批量训练 / 汇总脚本
│  └─ predict_btd_tsk.py       # 已训练模型推理与平滑修正
├─ scripts/                    # 辅助脚本
├─ doc/                        # 项目说明文档
├─ run_backend.py              # 启动后端
├─ start_backend.ps1           # Windows 后端启动脚本
├─ start_frontend.ps1          # Windows 前端启动脚本
└─ README.md
```

## 环境准备

### Python 依赖

建议使用独立虚拟环境安装：

```bash
pip install -r requirements.txt
```

### 前端依赖

```bash
cd frontend
npm install
```

## 快速开始

### 1. 启动后端

推荐方式：

```bash
python run_backend.py
```

默认地址：

- 后端服务：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/health`

也可以直接使用：

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### 2. 启动前端

```bash
cd frontend
npm run dev
```

默认地址：

- 前端页面：`http://127.0.0.1:5173`

### 3. 一键开发模式

仓库提供了 Windows 下的开发脚本：

```powershell
./start_dev.ps1
```

注意：`start_backend.ps1` 会直接调用当前环境中的 `python` 命令。运行前请先激活你的项目虚拟环境，或者确认 `python` 已经指向可用的解释器。

## 训练与推理

### 1. 训练 BTD-TSK 模型

主训练脚本：

```bash
python src/train_btd_tsk_distill.py
```

如果需要批量训练并输出汇总：

```bash
python src/train_btd_tsk_all.py
```

### 2. 使用已训练模型推理

```bash
python src/predict_btd_tsk.py
```

后端在线推理时会调用：

- `backend/app/ml/inference.py`
- `backend/app/services/diagnosis_ops.py`

## 数据说明

项目使用的公开数据来源为：

- `MIT-BIH Polysomnographic Database`
- 数据平台：PhysioNet

出于 GitHub 仓库体积和公开发布的考虑，仓库默认不跟踪以下内容：

- 原始睡眠数据文件
- 已训练模型文件
- 实验结果图片与文本
- 论文导出文件
- 临时脚本与缓存目录

如果你需要在本地运行训练流程，请自行准备数据，并放置到：

```text
data/
```

常见文件包括：

- `slpxx.dat`
- `slpxx.hea`
- `slpxx.st`
- `slpxx.ecg`

## 后端 API 概览

主要接口前缀为：

```text
/api
```

典型接口包括：

- `/api/home/overview`
- `/api/home/trend`
- `/api/patients`
- `/api/models`
- `/api/rules`
- `/api/history`
- `/api/diagnosis`
- `/api/diagnosis/{run_code}/status`
- `/api/diagnosis/{run_code}/result`

## 模型文件与系统运行说明

系统模型管理支持两种使用方式：

### 方式一：本地已有模型

将训练好的 `joblib` / `pkl` 文件放在本地模型目录中，再通过后端或前端导入。

### 方式二：前端上传模型

系统支持在模型管理页上传模型文件，后端会：

- 校验模型结构
- 自动抽取规则
- 写入 SQLite
- 在规则中心和历史页提供展示
