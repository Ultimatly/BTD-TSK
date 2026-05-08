export const featureLabels = {
  DeltaRelPower: 'Delta 相对功率',
  ThetaRelPower: 'Theta 相对功率',
  AlphaRelPower: 'Alpha 相对功率',
  BetaRelPower: 'Beta 相对功率',
  ThetaAlphaRatio: 'Theta/Alpha 比值',
  SEF95: '95% 谱边缘频率',
  SpectralEntropy: '谱熵',
  RMS: '均方根幅值',
  STD: '标准差',
  HjorthActivity: 'Hjorth 活动度',
  HjorthMobility: 'Hjorth 灵活度',
  HjorthComplexity: 'Hjorth 复杂度',
  WaveformLength: '波形长度',
  ECG_MeanHR: '心电平均心率',
  ECG_SDNN: '心电 SDNN',
  ECG_RMSSD: '心电 RMSSD',
  ECG_pNN50: '心电 pNN50',
  ECG_RRCV: 'RR 间期变异系数',
  ECG_SDSD: '心电 SDSD',
  ECG_MADRR: 'RR 间期中位绝对偏差',
  ECG_LFHF: 'LF/HF 比值',
  ECG_HFNorm: 'HF 归一化功率',
}

const buildAntecedent = (feature, level, a, sigma) => ({
  feature,
  label: featureLabels[feature] ?? feature,
  level,
  a,
  sigma,
})

export const quickEntries = [
  { title: '新建诊断', subtitle: '快速进入多模态分析流程', route: '/analysis' },
  { title: '患者档案', subtitle: '查看患者信息与分析状态', route: '/patients' },
  { title: '规则中心', subtitle: '展示蒸馏后的 TSK 规则', route: '/rules' },
  { title: '历史记录', subtitle: '回看历史结果与风险摘要', route: '/history' },
  { title: '模型管理', subtitle: '查看系统已存模型并上传新模型', route: '/model' },
]

export const statusItems = [
  { label: '当前模型', value: 'BTD-TSK' },
  { label: '支持模态', value: 'EEG + ECG' },
  { label: '输入维度', value: '22 维' },
  { label: '分类任务', value: '五类睡眠分期' },
  { label: '规则核心', value: '零阶 TSK 规则可解释' },
  { label: '结果增强', value: 'BiLSTM 教师蒸馏' },
]

export const recentCases = [
  { historyId: 'history-002', name: '患者 A-021', date: '2026-03-28', risk: '中风险', summary: 'REM 比例偏高，睡眠结构轻度紊乱' },
  { historyId: 'history-001', name: '患者 B-107', date: '2026-03-29', risk: '低风险', summary: '整体结构稳定，N2 阶段分布较正常' },
  { historyId: 'history-003', name: '患者 C-044', date: '2026-03-30', risk: '高风险', summary: '深睡比例不足，夜间觉醒片段偏多' },
]

export const analysisSteps = [
  { title: '数据读取', status: 'done' },
  { title: '信号预处理', status: 'done' },
  { title: '特征提取', status: 'done' },
  { title: '模型推理', status: 'doing' },
  { title: '结果生成', status: 'todo' },
]

export const stageDistribution = [
  { label: 'W', value: '12%' },
  { label: 'N1', value: '9%' },
  { label: 'N2', value: '46%' },
  { label: 'N3', value: '18%' },
  { label: 'R', value: '15%' },
]

export const storedModels = [
  {
    id: 'model-001',
    name: 'BTD-TSK 主模型',
    version: 'v1.0.0',
    status: '主模型',
    type: 'BiLSTM 教师蒸馏零阶 TSK',
    updatedAt: '2026-03-30 21:18',
    notes: '用于主要辅助诊断流程，仅展示蒸馏后的零阶 TSK 学生规则。',
  },
  {
    id: 'model-002',
    name: 'TSK-GD 对照模型',
    version: 'v1.0.0',
    status: '备用模型',
    type: '零阶 TSK-GD',
    updatedAt: '2026-03-22 18:40',
    notes: '用于蒸馏前后对比实验展示。',
  },
  {
    id: 'model-003',
    name: 'TSK-LLM 对照模型',
    version: 'v1.0.0',
    status: '测试模型',
    type: '零阶 TSK-LLM',
    updatedAt: '2026-03-12 09:10',
    notes: '用于前端展示和接口调试，不作为最终蒸馏模型。',
  },
]

export const ruleCards = [
  {
    id: 1,
    modelId: 'model-001',
    layer: 1,
    type: '蒸馏学生规则',
    target: 'N1',
    strength: 0.842,
    description: '如果 Delta 相对功率为中、Theta 相对功率为低，且 ECG_RMSSD 很低，那么该规则更倾向支持 N1 类别。',
    tags: ['Delta 相对功率', 'Theta 相对功率', '心电 RMSSD'],
    detailTitle: '规则 #1 的语言解释',
    antecedents: [
      buildAntecedent('DeltaRelPower', '中', 0.46, 0.2291),
      buildAntecedent('ThetaRelPower', '低', 0.3238, 0.1811),
      buildAntecedent('AlphaRelPower', '低', 0.3184, 0.2571),
      buildAntecedent('BetaRelPower', '低', 0.2372, 0.1627),
      buildAntecedent('ThetaAlphaRatio', '很低', 0.1867, 0.164),
      buildAntecedent('SEF95', '中', 0.5833, 0.1878),
      buildAntecedent('SpectralEntropy', '高', 0.6777, 0.1683),
      buildAntecedent('RMS', '低', 0.207, 0.1423),
      buildAntecedent('STD', '低', 0.207, 0.1423),
      buildAntecedent('HjorthActivity', '很低', 0.0833, 0.098),
      buildAntecedent('HjorthMobility', '中', 0.478, 0.1789),
      buildAntecedent('HjorthComplexity', '很低', 0.1419, 0.1146),
      buildAntecedent('WaveformLength', '低', 0.2068, 0.1561),
      buildAntecedent('ECG_MeanHR', '低', 0.3425, 0.1863),
      buildAntecedent('ECG_SDNN', '很低', 0.1919, 0.1448),
      buildAntecedent('ECG_RMSSD', '很低', 0.1009, 0.1031),
      buildAntecedent('ECG_pNN50', '很低', 0.1453, 0.1734),
      buildAntecedent('ECG_RRCV', '很低', 0.1803, 0.1415),
      buildAntecedent('ECG_SDSD', '很低', 0.1007, 0.1031),
      buildAntecedent('ECG_MADRR', '很低', 0.1414, 0.1137),
      buildAntecedent('ECG_LFHF', '很低', 0.0334, 0.0563),
      buildAntecedent('ECG_HFNorm', '低', 0.348, 0.2521),
    ],
    consequence: { label: '类别 1（N1）', p: 9.0654 },
  },
]

export const patients = [
  { id: 'P-001', name: '张晨曦', age: 28, gender: '女', status: '已分析', risk: '低风险', modalities: ['EEG', 'ECG'] },
  { id: 'P-002', name: '李子昂', age: 35, gender: '男', status: '已分析', risk: '中风险', modalities: ['EEG', 'ECG'] },
  { id: 'P-003', name: '周若宁', age: 42, gender: '女', status: '待分析', risk: '待评估', modalities: ['EEG'] },
  { id: 'P-004', name: '王景行', age: 31, gender: '男', status: '已分析', risk: '高风险', modalities: ['EEG', 'ECG'] },
]

export const historyRecords = [
  {
    id: 'history-001',
    date: '2026-03-30',
    title: '患者 B-107',
    summary: 'REM 占比升高，轻度紊乱',
    conclusion: 'REM 占比升高，存在轻度睡眠结构紊乱风险',
    status: '分析完成',
    risk: '中风险',
    dominantStage: 'N2',
    focusClass: 'R',
    rules: '规则 #1',
    ruleIds: [1],
  },
]
