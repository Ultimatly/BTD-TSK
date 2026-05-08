const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
const API_PREFIX = '/api'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${API_PREFIX}${path}`, options)
  if (!response.ok) {
    let detail = `请求失败：${response.status}`
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch (_) {}
    throw new Error(detail)
  }
  return response.json()
}

export const apiBase = API_BASE
export const apiPrefix = API_PREFIX

export const api = {
  health: () => fetch(`${API_BASE}/health`).then((r) => r.json()),
  getHomeOverview: () => request('/home/overview'),
  getHomeTrend: (days = 7) => request(`/home/trend?days=${days}`),
  getRecentRuns: (limit = 3) => request(`/home/recent-runs?limit=${limit}`),
  getPatients: () => request('/patients'),
  createPatient: (payload) => request('/patients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  updatePatient: (patientCode, payload) => request(`/patients/${patientCode}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  deletePatient: (patientCode) => request(`/patients/${patientCode}`, { method: 'DELETE' }),
  getPatientHistory: (patientCode) => request(`/patients/${patientCode}/history`),
  getModels: () => request('/models'),
  getModelDetail: (modelCode) => request(`/models/${modelCode}`),
  updateModel: async (modelCode, payload) => {
    const formData = new FormData()
    formData.append('name', payload.name)
    formData.append('version', payload.version)
    formData.append('status', payload.status)
    formData.append('model_type', payload.model_type)
    formData.append('notes', payload.notes || '')
    if (payload.file) {
      formData.append('file', payload.file)
    }
    return request(`/models/${modelCode}`, {
      method: 'PUT',
      body: formData,
    })
  },
  deleteModel: (modelCode) => request(`/models/${modelCode}`, { method: 'DELETE' }),
  uploadModel: async ({ name, version, status, modelType, notes, file }) => {
    const formData = new FormData()
    formData.append('name', name)
    formData.append('version', version)
    formData.append('status', status)
    formData.append('model_type', modelType)
    formData.append('notes', notes || '')
    formData.append('file', file)
    return request('/models/upload', { method: 'POST', body: formData })
  },
  getRules: (modelCode) => request(modelCode ? `/rules?model_code=${encodeURIComponent(modelCode)}` : '/rules'),
  getRuleDetail: (ruleId) => request(`/rules/${ruleId}`),
  getHistoryList: () => request('/history'),
  deleteHistory: (runCode) => request(`/history/${runCode}`, { method: 'DELETE' }),
  getHistoryOverview: (runCode) => request(`/history/${runCode}/overview`),
  getHistoryDetail: (runCode) => request(`/history/${runCode}/detail`),
  getHistoryRules: (runCode) => request(`/history/${runCode}/rules`),
  getHistoryWaveform: (runCode) => request(`/history/${runCode}/waveform`),
  getHistoryArtifactCsvUrl: (runCode) => `${API_BASE}${API_PREFIX}/history/${runCode}/artifact-csv`,
  createDiagnosis: async ({ patientCode, modelCode, files }) => {
    const formData = new FormData()
    formData.append('patient_code', patientCode)
    formData.append('model_code', modelCode)
    files.forEach((file) => formData.append('files', file))
    return request('/diagnosis', { method: 'POST', body: formData })
  },
  getDiagnosisStatus: (runCode) => request(`/diagnosis/${runCode}/status`),
  getDiagnosisResult: (runCode) => request(`/diagnosis/${runCode}/result`),
  getDiagnosisRules: (runCode) => request(`/diagnosis/${runCode}/rules`),
  getDiagnosisWaveform: (runCode) => request(`/diagnosis/${runCode}/waveform`),
  getDiagnosisArtifactCsvUrl: (runCode) => `${API_BASE}${API_PREFIX}/diagnosis/${runCode}/artifact-csv`,
}

function normalizeRuleType(ruleType = '') {
  const cleaned = String(ruleType).replace('蒸馏学生', '').trim()
  return cleaned || '规则'
}

function shortenFeatureLabel(label = '') {
  const mapping = {
    'EEG 相对 Delta 波功率': 'Delta波',
    'EEG 相对 Theta 波功率': 'Theta波',
    'EEG 相对 Alpha 波功率': 'Alpha波',
    'EEG 相对 Beta 波功率': 'Beta波',
    'EEG Theta/Alpha 比值': 'Theta/Alpha',
    'EEG 频谱边缘频率 SEF95': 'SEF95',
    'EEG 频谱熵': '频谱熵',
    'EEG 均方根': 'RMS',
    'EEG 标准差': 'STD',
    'EEG Hjorth 活动度': 'Hjorth活动度',
    'EEG Hjorth 移动度': 'Hjorth移动度',
    'EEG Hjorth 复杂度': 'Hjorth复杂度',
    'EEG 波形长度': '波形长度',
    'ECG 平均心率': '平均心率',
    'ECG SDNN': 'SDNN',
    'ECG RMSSD': 'RMSSD',
    'ECG pNN50': 'pNN50',
    'ECG RR 变异系数': 'RR变异系数',
    'ECG SDSD': 'SDSD',
    'ECG RR 中位绝对偏差': 'MADRR',
    'ECG LF/HF 比值': 'LF/HF',
    'ECG HF 归一化功率': 'HF功率',
  }
  return mapping[label] || label.replace(/^EEG\s*/, '').replace(/^ECG\s*/, '')
}

function scoreCondition(condition = {}) {
  const sigma = Number(condition.sigmaValue ?? condition.sigma ?? 1)
  const a = Number(condition.aValue ?? condition.a ?? 0.5)
  const sigmaScore = Number.isFinite(sigma) && sigma > 0 ? 1 / sigma : 0
  const centerScore = Number.isFinite(a) ? Math.abs(a - 0.5) : 0
  return sigmaScore + centerScore
}

function buildRuleTags(rule = {}) {
  const conditions = Array.isArray(rule.conditions) ? rule.conditions : []
  const featureTags = [...conditions]
    .sort((a, b) => scoreCondition(b) - scoreCondition(a))
    .slice(0, 3)
    .map((item) => {
      const label = shortenFeatureLabel(item.featureLabel || item.label || '')
      const level = item.linguisticLevel || item.level || ''
      return label && level ? `${label}${level}` : label || level
    })
    .filter(Boolean)

  if (featureTags.length) return featureTags

  const fallbackTags = []
  if (rule.targetClass) fallbackTags.push(`目标类别：${rule.targetClass}`)
  if (rule.consequenceLabel) fallbackTags.push(rule.consequenceLabel)
  if (conditions.length) fallbackTags.push(`条件数：${conditions.length}`)
  return fallbackTags
}

export function mapRule(rule) {
  return {
    id: Number(rule.ruleNo ?? rule.id ?? 0),
    modelId: rule.modelCode ?? rule.modelId ?? '',
    layer: Number(rule.layerIndex ?? rule.layer ?? 1),
    type: normalizeRuleType(rule.ruleType ?? rule.type),
    target: rule.targetClass ?? rule.target ?? '',
    strength: Number(rule.activationStrength ?? rule.strength ?? 0),
    description: rule.shortDescription ?? rule.description ?? '暂无规则说明',
    tags: rule.tags || buildRuleTags(rule),
    detailTitle: rule.detailTitle ?? '',
    antecedents: (rule.conditions || rule.antecedents || []).map((item) => ({
      feature: item.featureKey ?? item.feature ?? '',
      label: item.featureLabel ?? item.label ?? '',
      level: item.linguisticLevel ?? item.level ?? '',
      a: item.aValue ?? item.a ?? null,
      sigma: item.sigmaValue ?? item.sigma ?? null,
    })),
    consequence: {
      label: rule.consequenceLabel ?? rule.consequence?.label ?? (rule.targetClass ?? rule.target ?? ''),
      p: Number(rule.consequenceP ?? rule.consequence?.p ?? 0),
    },
  }
}

export function formatStageStats(stageStats = []) {
  return stageStats.map((item) => ({
    label: item.label,
    value: `${Number(item.value).toFixed(0)}%`,
  }))
}
