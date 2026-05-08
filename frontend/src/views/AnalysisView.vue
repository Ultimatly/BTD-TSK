<template>
  <div class="page-view">
    <SectionTitle
      eyebrow="Analysis Workspace"
      title="诊断分析工作台"
    />

    <Transition name="notice-slide">
      <div v-if="feedback.message" class="feedback-banner" :class="feedback.type">
        <div>
          <strong>{{ feedback.type === 'success' ? '操作成功' : '操作失败' }}</strong>
          <p>{{ feedback.message }}</p>
        </div>
        <button type="button" class="feedback-close" @click="clearFeedback">×</button>
      </div>
    </Transition>

    <div v-if="hasDiagnosisResult" class="page-actions">
      <button type="button" class="action-button secondary" @click="resetWorkspace">继续新诊断</button>
    </div>

    <section v-if="!hasDiagnosisResult" class="two-col">
      <GlassPanel>
        <SectionTitle title="数据输入区" />
        <div class="input-grid">
          <div class="input-box">
            <span>选择患者</span>
            <select v-model="selectedPatientId" class="model-select">
              <option v-for="patient in patients" :key="patient.id" :value="patient.id">
                {{ patient.id }} · {{ patient.name }}
              </option>
            </select>
          </div>
          <div class="input-box">
            <span>选择诊断模型</span>
            <select v-model="selectedModelId" class="model-select">
              <option v-for="model in models" :key="model.id" :value="model.id">
                {{ model.name }} · {{ model.version }}
              </option>
            </select>
          </div>
          <div class="input-box upload-box" @click="fileInputRef?.click()">
            <div class="upload-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M12 15V7" />
                <path d="M8.5 10.5 12 7l3.5 3.5" />
                <path d="M5 16.5v1a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5v-1" />
              </svg>
            </div>
            <span>点击或拖拽上传 EEG / ECG / EDF 文件</span>
            <strong>{{ uploadText }}</strong>
            <input ref="fileInputRef" class="hidden-file" type="file" multiple accept=".dat,.hea,.st,.edf" @change="handleFileChange" />
          </div>
          <div class="hero-actions">
            <button class="action-button primary loading-button" :disabled="isAnalysisRunning" @click="startDiagnosis">
              <span v-if="isAnalysisRunning" class="button-spinner" aria-hidden="true"></span>
              <span>{{ isAnalysisRunning ? '正在分析...' : '开始分析' }}</span>
            </button>
          </div>
          </div>
      </GlassPanel>

      <GlassPanel>
        <SectionTitle title="分析流程区" />
        <StepList :steps="analysisSteps" />
      </GlassPanel>
    </section>

    <DiagnosisResultDetail
      v-else
      :detail="diagnosisResult"
      :waveform-preview="waveformPreview"
      :status-text="statusText"
      :download-file-name="analysisArtifactName"
      :download-disabled="!hasAnalysisArtifact"
      @download="downloadPredictionFile"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import StepList from '@/components/common/StepList.vue'
import RuleCard from '@/components/rules/RuleCard.vue'
import DiagnosisResultDetail from '@/components/diagnosis/DiagnosisResultDetail.vue'
import { api, mapRule } from '@/api'

function normalizeModelStatus(status = '') {
  return status === '当前启用' ? '主模型' : status
}

function modelPriority(model) {
  const status = normalizeModelStatus(model?.status || '')
  if (status === '主模型') return 0
  if (status === '备用模型') return 1
  if (status === '测试模型') return 2
  return 3
}

function sortModels(models = []) {
  return [...models].sort((a, b) => {
    const priorityDiff = modelPriority(a) - modelPriority(b)
    if (priorityDiff !== 0) return priorityDiff
    return String(b?.updatedAt || '').localeCompare(String(a?.updatedAt || ''))
  })
}

const route = useRoute()
const fileInputRef = ref(null)
const patients = ref([])
const models = ref([])
const selectedPatientId = ref('')
const selectedModelId = ref('')
const selectedFiles = ref([])
const currentRunCode = ref('')
const diagnosisResult = ref(null)
const waveformPreview = ref(null)
const diagnosisStatus = ref('idle')
const diagnosisProgress = ref(0)
const isSubmitting = ref(false)
const stagePieChartRef = ref(null)
const stageTrendChartRef = ref(null)
const layerFilter = ref('全部层级')
const targetFilter = ref('全部类别')
const keyword = ref('')
const sortMode = ref('按激活强度降序')
let pollTimer = null
const feedback = ref({ type: 'success', message: '' })
let feedbackTimer = null
let stagePieChart = null
let stageTrendChart = null

const STAGE_COLOR_MAP = {
  W: '#0f766e',
  N1: '#8b5cf6',
  N2: '#0284c7',
  N3: '#1d4ed8',
  R: '#ea580c',
}
const STAGE_ORDER = ['W', 'N1', 'N2', 'N3', 'R']
const STAGE_LEVEL_MAP = { W: 4, N1: 3, N2: 2, N3: 1, R: 0 }

function showFeedback(message, type = 'success') {
  feedback.value = { message, type }
  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => {
    feedback.value = { type: 'success', message: '' }
    feedbackTimer = null
  }, 2600)
}

function clearFeedback() {
  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = null
  feedback.value = { type: 'success', message: '' }
}

const uploadText = computed(() => {
  if (!selectedFiles.value.length) return '支持 .dat + .hea 记录对、或单个 .edf 文件（可选 .st 标签）'
  return `已选择 ${selectedFiles.value.length} 个文件：${selectedFiles.value.map((item) => item.name).join(' / ')}`
})

const statusText = computed(() => {
  if (diagnosisStatus.value === 'done') return '分析完成'
  if (diagnosisStatus.value === 'uploading') return '上传诊断文件中'
  if (diagnosisStatus.value === 'processing') return '模型推理中'
  if (diagnosisStatus.value === 'queued') return '任务排队中'
  if (diagnosisStatus.value === 'failed') return '诊断失败'
  return '等待开始'
})

const isAnalysisRunning = computed(() =>
  isSubmitting.value || ['uploading', 'queued', 'processing'].includes(diagnosisStatus.value),
)

const waitingTitle = computed(() => {
  if (diagnosisStatus.value === 'uploading') return '正在上传文件'
  if (diagnosisStatus.value === 'queued') return '任务已创建'
  if (diagnosisStatus.value === 'processing') return '正在进行诊断'
  if (diagnosisStatus.value === 'failed') return '诊断失败'
  return '等待开始诊断'
})

const waitingText = computed(() => {
  if (diagnosisStatus.value === 'uploading') return '正在将诊断文件发送到服务器，请稍候。'
  if (diagnosisStatus.value === 'queued') return '任务已经进入队列，正在等待模型开始执行。'
  if (diagnosisStatus.value === 'processing') return '模型正在推理中。'
  if (diagnosisStatus.value === 'failed') return '这次诊断没有成功完成，请检查上传文件与模型是否匹配。'
  return '请选择患者、模型并上传文件后开始诊断。'
})

const hasDiagnosisResult = computed(() => diagnosisStatus.value === 'done' && !!diagnosisResult.value)
const hasWaveformPreview = computed(() => {
  return Boolean(
    waveformPreview.value &&
    ((waveformPreview.value.eeg?.points?.length || 0) > 0 || (waveformPreview.value.ecg?.points?.length || 0) > 0)
  )
})
const rawStageStats = computed(() => diagnosisResult.value?.stageStats || [])
const stageLegendItems = computed(() =>
  rawStageStats.value.map((item) => ({
    label: item.label,
    value: Number(item.value) || 0,
    valueText: `${Number(item.value || 0).toFixed(0)}%`,
    color: STAGE_COLOR_MAP[item.label] || '#164e63',
  })),
)
const stageTimeline = computed(() => {
  const rows = diagnosisResult.value?.stageTimeline || []
  if (!rows.length) return []

  const preferredLength = 120
  const stride = Math.max(1, Math.ceil(rows.length / preferredLength))
  return rows
    .filter((_, index) => index % stride === 0 || index === rows.length - 1)
    .map((item) => ({
      timeMinute: Number(item.timeSec || 0) / 60,
      stage: item.stage,
      stageLevel: STAGE_LEVEL_MAP[item.stage] ?? 0,
    }))
})

const allRules = computed(() => (diagnosisResult.value?.rules || []).map(mapRule))
const availableLayers = computed(() => [...new Set(allRules.value.map((item) => item.layer))].sort((a, b) => a - b))
const filteredRules = computed(() => {
  let list = [...allRules.value]
  if (layerFilter.value !== '全部层级') {
    const layer = Number(layerFilter.value.replace(/\D/g, ''))
    list = list.filter((rule) => rule.layer === layer)
  }
  if (targetFilter.value !== '全部类别') {
    list = list.filter((rule) => rule.target === targetFilter.value)
  }
  if (keyword.value.trim()) {
    const q = keyword.value.trim()
    list = list.filter((rule) => String(rule.id).includes(q) || rule.description.includes(q) || rule.tags.some((tag) => tag.includes(q)))
  }
  if (sortMode.value === '按规则编号') {
    list.sort((a, b) => a.id - b.id)
  } else {
    list.sort((a, b) => b.strength - a.strength)
  }
  return list
})
const topRuleText = computed(() => {
  const top = filteredRules.value[0]
  return top ? `规则 #${top.id} · ${top.strength.toFixed(3)}` : '暂无'
})
const analysisArtifact = computed(() =>
  (diagnosisResult.value?.artifacts || []).find((item) => item.role === 'artifact_csv'),
)
const hasAnalysisArtifact = computed(() => Boolean(analysisArtifact.value?.name))
const analysisArtifactName = computed(() => analysisArtifact.value?.name || 'predictions.csv')

const eegPreviewLabel = computed(() => {
  if (!waveformPreview.value?.eeg?.points?.length) return '等待载入 EEG 波形'
  return `${waveformPreview.value.recordName} · ${waveformPreview.value.eeg.channel || 'EEG'}`
})

const ecgPreviewLabel = computed(() => {
  if (!waveformPreview.value?.ecg?.points?.length) return '等待载入 ECG 波形'
  return `${waveformPreview.value.recordName} · ${waveformPreview.value.ecg.channel || 'ECG'}`
})

function buildWavePath(samples, width = 680, height = 180, padding = 10) {
  if (!samples.length) return ''
  const max = Math.max(...samples)
  const min = Math.min(...samples)
  const range = Math.max(max - min, 1e-6)
  return samples
    .map((value, index) => {
      const x = (index / Math.max(samples.length - 1, 1)) * width
      const normalized = (value - min) / range
      const y = height - padding - normalized * (height - padding * 2)
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

const eegWaveSamples = computed(() => waveformPreview.value?.eeg?.points || [])
const ecgWaveSamples = computed(() => waveformPreview.value?.ecg?.points || [])
const eegWavePath = computed(() => buildWavePath(eegWaveSamples.value))
const ecgWavePath = computed(() => buildWavePath(ecgWaveSamples.value))

const eegMetaText = computed(() => {
  if (!waveformPreview.value?.eeg?.points?.length) return '等待读取 EEG 原始采样'
  const eeg = waveformPreview.value.eeg
  return `${eeg.sampleCount} 点 · ${eeg.durationSeconds.toFixed(1)} 秒`
})

const ecgMetaText = computed(() => {
  if (!waveformPreview.value?.ecg?.points?.length) return '等待读取 ECG 原始采样'
  const ecg = waveformPreview.value.ecg
  return `${ecg.sampleCount} 点 · ${ecg.durationSeconds.toFixed(1)} 秒`
})

function ensurePieChart() {
  const el = stagePieChartRef.value
  if (!el || el.clientWidth <= 0 || el.clientHeight <= 0) return null
  if (!stagePieChart) stagePieChart = echarts.init(el, null, { renderer: 'canvas' })
  return stagePieChart
}

function ensureTrendChart() {
  const el = stageTrendChartRef.value
  if (!el || el.clientWidth <= 0 || el.clientHeight <= 0) return null
  if (!stageTrendChart) stageTrendChart = echarts.init(el, null, { renderer: 'canvas' })
  return stageTrendChart
}

function buildStagePieOption() {
  const data = stageLegendItems.value.map((item) => ({
    value: item.value,
    name: item.label,
    itemStyle: { color: item.color },
  }))
  return {
    animationDuration: 900,
    animationEasing: 'cubicOut',
    grid: { top: 0, bottom: 0 },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#f8fafc' },
      formatter: ({ name, value, percent }) => `${name}<br/>占比 ${value.toFixed(1)}% · ${percent.toFixed(0)}%`,
    },
    series: [
      {
        type: 'pie',
        radius: ['42%', '74%'],
        center: ['50%', '52%'],
        startAngle: 90,
        avoidLabelOverlap: true,
        itemStyle: {
          borderColor: '#f8fcfc',
          borderWidth: 3,
          shadowBlur: 14,
          shadowColor: 'rgba(15, 118, 110, 0.12)',
        },
        label: { show: false },
        emphasis: {
          scale: true,
          scaleSize: 8,
          itemStyle: { shadowBlur: 26, shadowColor: 'rgba(15, 118, 110, 0.22)' },
        },
        data,
      },
    ],
    graphic: [
        {
          type: 'text',
          left: 'center',
          top: '36%',
          style: {
            text: '阶段占比',
            textAlign: 'center',
            fill: '#688094',
            fontSize: 12,
            fontWeight: 600,
          },
        },
        {
          type: 'text',
          left: 'center',
          top: '46%',
          style: {
            text: `${diagnosisResult.value?.predictionCount || 0}`,
            textAlign: 'center',
            fill: '#163042',
            fontSize: 24,
            fontWeight: 700,
          },
        },
        {
          type: 'text',
          left: 'center',
          top: '60%',
          style: {
            text: '个样本',
            textAlign: 'center',
            fill: '#688094',
            fontSize: 12,
            fontWeight: 600,
          },
        },
      ],
    }
}

function buildStageTrendOption() {
  const data = stageTimeline.value.map((item) => [item.timeMinute, item.stageLevel, item.stage])
  return {
    animationDuration: 900,
    animationEasing: 'quadraticOut',
    grid: { left: 50, right: 18, top: 18, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderWidth: 0,
      axisPointer: {
        type: 'line',
        lineStyle: { color: 'rgba(14, 165, 233, 0.45)', width: 1.5 },
      },
      textStyle: { color: '#f8fafc' },
      formatter: (params) => {
        const item = params?.[0]
        if (!item) return ''
        const value = item.data || []
        return `时间 ${Number(value[0]).toFixed(1)} 分钟<br/>阶段 ${value[2]}`
      },
    },
      xAxis: {
        type: 'value',
        name: '时间（分钟）',
        nameTextStyle: { color: '#688094', padding: [8, 0, 0, 0], fontSize: 11 },
        axisLine: { lineStyle: { color: 'rgba(15, 118, 110, 0.16)' } },
        axisTick: { show: false },
        axisLabel: { color: '#688094', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(15, 118, 110, 0.08)' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
      max: 4,
      interval: 1,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#688094',
          fontSize: 11,
          formatter: (value) => ({ 4: 'W', 3: 'N1', 2: 'N2', 1: 'N3', 0: 'R' }[value] || ''),
        },
        splitLine: { lineStyle: { color: 'rgba(15, 118, 110, 0.08)' } },
      },
      series: [
        {
          type: 'line',
          step: 'middle',
          data,
          smooth: 0.12,
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: {
            width: 2.5,
            color: '#0f766e',
            shadowBlur: 10,
            shadowColor: 'rgba(15, 118, 110, 0.18)',
          },
          itemStyle: {
          color: '#ffffff',
          borderColor: '#0f766e',
          borderWidth: 2,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(45, 212, 191, 0.22)' },
            { offset: 1, color: 'rgba(45, 212, 191, 0.03)' },
          ]),
        },
      },
    ],
  }
}

function renderAnalysisCharts() {
  if (!hasDiagnosisResult.value) return false
  const pie = ensurePieChart()
  const trend = ensureTrendChart()
  if (!pie || !trend) return false
  pie.setOption(buildStagePieOption(), true)
  trend.setOption(buildStageTrendOption(), true)
  pie.resize()
  trend.resize()
  return true
}

async function scheduleRenderAnalysisCharts(retry = 0) {
  await nextTick()
  requestAnimationFrame(() => {
    const rendered = renderAnalysisCharts()
    if (!rendered && retry < 6) {
      setTimeout(() => {
        scheduleRenderAnalysisCharts(retry + 1)
      }, 120)
    }
  })
}

function handleChartResize() {
  stagePieChart?.resize()
  stageTrendChart?.resize()
}

const analysisSteps = computed(() => {
  const titles = ['数据读取', '信号预处理', '特征提取', '模型推理', '结果生成']

  if (hasDiagnosisResult.value) {
    return titles.map((title) => ({ title, status: 'done' }))
  }

  const progress = diagnosisProgress.value
  let activeIndex = -1

  if (diagnosisStatus.value === 'uploading') {
    activeIndex = 0
  } else if (progress >= 85) {
    activeIndex = 4
  } else if (progress >= 60) {
    activeIndex = 3
  } else if (progress >= 40) {
    activeIndex = 2
  } else if (progress >= 20) {
    activeIndex = 1
  } else if (progress > 0 || diagnosisStatus.value === 'queued') {
    activeIndex = 0
  }

  return titles.map((title, index) => {
    if (activeIndex === -1) {
      return { title, status: 'todo' }
    }
    if (index < activeIndex) {
      return { title, status: 'done' }
    }
    if (index === activeIndex && diagnosisStatus.value !== 'failed') {
      return { title, status: 'doing' }
    }
    return { title, status: 'todo' }
  })
})

const handleFileChange = (event) => {
  selectedFiles.value = Array.from(event.target.files || [])
  waveformPreview.value = null
}

async function pollDiagnosis(runCode) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const status = await api.getDiagnosisStatus(runCode)
      diagnosisStatus.value = status.status
      diagnosisProgress.value = Math.max(
        diagnosisProgress.value,
        Number(status.progress || 0),
      )
      if (status.status === 'done') {
        diagnosisProgress.value = 100
        clearInterval(pollTimer)
        const [result, rules, waveform] = await Promise.all([
          api.getDiagnosisResult(runCode),
          api.getDiagnosisRules(runCode),
          api.getDiagnosisWaveform(runCode).catch(() => null),
        ])
        diagnosisResult.value = {
          ...result,
          rules: rules?.length ? rules : result.rules || [],
        }
        waveformPreview.value = waveform
        await scheduleRenderAnalysisCharts()
        showFeedback('诊断已完成。')
      }
      if (status.status === 'failed') {
        clearInterval(pollTimer)
        showFeedback(status.message || '诊断失败', 'error')
      }
    } catch (error) {
      clearInterval(pollTimer)
      console.error('轮询诊断状态失败:', error)
      showFeedback('轮询诊断状态失败。', 'error')
    }
  }, 1000)
}

async function startDiagnosis() {
  if (!selectedPatientId.value || !selectedModelId.value) {
    showFeedback('请先选择患者与模型。', 'error')
    return
  }
  if (!selectedFiles.value.length) {
    showFeedback('请先上传诊断文件。', 'error')
    return
  }

  try {
    isSubmitting.value = true
    diagnosisResult.value = null
    waveformPreview.value = null
    diagnosisStatus.value = 'uploading'
    diagnosisProgress.value = 8
    await nextTick()
    const result = await api.createDiagnosis({
      patientCode: selectedPatientId.value,
      modelCode: selectedModelId.value,
      files: selectedFiles.value,
    })
    currentRunCode.value = result.runCode
    diagnosisStatus.value = 'queued'
    diagnosisProgress.value = Math.max(diagnosisProgress.value, 18)
    waveformPreview.value = await api.getDiagnosisWaveform(result.runCode).catch(() => null)
    await pollDiagnosis(result.runCode)
  } catch (error) {
    diagnosisStatus.value = 'failed'
    showFeedback(error.message || '创建诊断任务失败', 'error')
  } finally {
    isSubmitting.value = false
  }
}

function resetWorkspace() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
  diagnosisResult.value = null
  waveformPreview.value = null
  currentRunCode.value = ''
  diagnosisStatus.value = 'idle'
  diagnosisProgress.value = 0
  selectedFiles.value = []
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

function downloadPredictionFile() {
  const runCode = currentRunCode.value || diagnosisResult.value?.id
  if (!runCode) {
    showFeedback('当前还没有可下载的预测结果。', 'error')
    return
  }
  window.open(api.getDiagnosisArtifactCsvUrl(runCode), '_blank', 'noopener')
}

onMounted(async () => {
  try {
    const [patientRows, modelRows] = await Promise.all([api.getPatients(), api.getModels()])
    patients.value = patientRows
    models.value = sortModels(
      modelRows.map((model) => ({
        ...model,
        status: normalizeModelStatus(model.status),
      })),
    )
    selectedPatientId.value = route.query.patient || patientRows[0]?.id || ''
    selectedModelId.value = models.value[0]?.id || ''
  } catch (error) {
    console.error('加载诊断页面基础数据失败:', error)
    showFeedback('加载诊断页面基础数据失败。', 'error')
  }
  window.addEventListener('resize', handleChartResize)
  if (hasDiagnosisResult.value) {
    await scheduleRenderAnalysisCharts()
  }
})

watch(
  () => [hasDiagnosisResult.value, diagnosisResult.value?.stageStats, diagnosisResult.value?.stageTimeline],
  async ([ready]) => {
    if (!ready) return
    await scheduleRenderAnalysisCharts()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (feedbackTimer) clearTimeout(feedbackTimer)
  window.removeEventListener('resize', handleChartResize)
  stagePieChart?.dispose()
  stageTrendChart?.dispose()
  stagePieChart = null
  stageTrendChart = null
})
</script>

<style scoped>
.feedback-banner {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 1200;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  width: min(420px, calc(100vw - 32px));
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(15, 118, 110, 0.16);
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.16), rgba(34, 211, 238, 0.1));
  box-shadow: 0 18px 40px rgba(22, 78, 99, 0.18);
  backdrop-filter: blur(18px);
}
.feedback-banner.error {
  border-color: rgba(220, 38, 38, 0.14);
  background: linear-gradient(135deg, rgba(220, 38, 38, 0.1), rgba(248, 113, 113, 0.06));
}
.feedback-banner strong,
.feedback-banner p {
  display: block;
  margin: 0;
}
.feedback-banner p {
  margin-top: 6px;
  color: #5c6d7e;
}
.feedback-close {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.66);
  color: #164e63;
  font-size: 1.2rem;
  line-height: 1;
}
.notice-slide-enter-active,
.notice-slide-leave-active {
  transition: all 0.22s ease;
}
.notice-slide-enter-from,
.notice-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
.page-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 6px;
}
.two-col,
.rule-grid {
  display: grid;
  gap: 24px;
}
.two-col { grid-template-columns: 1.2fr 1fr; }
.input-grid,
.visual-grid { display: grid; gap: 16px; margin-top: 18px; }
.input-box {
  padding: 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.12);
}
.input-box span,
.input-box strong { display: block; }
.input-box span { color: #5c6d7e; margin-bottom: 8px; }
.model-select {
  width: 100%;
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.9);
  color: #163042;
}
.upload-box {
  min-height: 150px;
  display: grid;
  place-items: center;
  gap: 10px;
  padding: 28px 20px;
  text-align: center;
  background:
    linear-gradient(180deg, rgba(245, 251, 251, 0.96), rgba(240, 248, 247, 0.92));
  border: 1.5px dashed rgba(15, 118, 110, 0.24);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
  cursor: pointer;
}
.upload-box:hover {
  border-color: rgba(15, 118, 110, 0.38);
  background:
    linear-gradient(180deg, rgba(244, 252, 251, 0.98), rgba(235, 248, 246, 0.95));
}
.upload-box span {
  margin-bottom: 0;
}
.upload-icon {
  width: 54px;
  height: 54px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: rgba(15, 118, 110, 0.08);
  border: 1px solid rgba(15, 118, 110, 0.12);
  color: #0f766e;
}
.upload-icon svg {
  width: 24px;
  height: 24px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.hidden-file { display: none; }
.hero-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.action-button { padding: 12px 18px; border-radius: 999px; border: 0; }
.action-button.primary { color: #fff; background: linear-gradient(135deg, #0f766e, #164e63); }
.action-button.primary:disabled { opacity: 0.55; cursor: not-allowed; }
.action-button.secondary { background: rgba(15, 118, 110, 0.08); color: #164e63; }
.result-panel { margin-top: 20px; display: grid; gap: 18px; }
.result-callout {
  padding: 22px 24px;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.12);
}
.result-callout h2 { margin: 10px 0 0; font-size: clamp(1.62rem, 1.95vw, 2.1rem); line-height: 1.22; }
.result-callout p { margin: 14px 0 0; max-width: 64ch; color: rgba(255, 255, 255, 0.74); line-height: 1.72; }
.summary-label { color: rgba(255, 255, 255, 0.72); }
.result-stats { display: grid; gap: 14px; }
.summary-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.summary-chip {
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.14);
}
.status-card strong { font-size: 1.5rem; }
.summary-chip.compact { min-height: 110px; }
.summary-chip span,
.summary-chip strong,
.summary-box span,
.summary-box strong { display: block; }
.summary-chip span { color: rgba(255, 255, 255, 0.72); margin-bottom: 10px; }
.summary-chip strong { font-size: 1.7rem; line-height: 1.15; }
.waveform-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 18px;
}
.wave-card {
  padding: 18px;
  border-radius: 24px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(241, 249, 249, 0.96));
  display: grid;
  gap: 14px;
  overflow: hidden;
}
.wave-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.wave-head span,
.wave-head strong,
.wave-meta span,
.wave-meta strong {
  display: block;
}
.wave-head span,
.wave-meta span {
  color: #5f7183;
  margin-bottom: 6px;
}
.wave-head strong {
  font-size: 1rem;
}
.wave-head em {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  height: 38px;
  padding: 0 16px;
  border-radius: 999px;
  font-style: normal;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid currentColor;
  flex-shrink: 0;
}
.wave-canvas {
  border-radius: 22px;
  padding: 10px 12px;
  background:
    radial-gradient(circle at 14% 18%, rgba(255,255,255,0.9), transparent 42%),
    linear-gradient(180deg, rgba(255,255,255,0.78), rgba(245,250,250,0.88));
  border: 1px solid rgba(15, 118, 110, 0.08);
}
.wave-canvas svg {
  width: 100%;
  height: 176px;
  display: block;
}
.wave-grid-lines line {
  stroke: rgba(15, 118, 110, 0.08);
  stroke-width: 1;
}
.wave-baseline {
  stroke: rgba(15, 118, 110, 0.12);
  stroke-width: 1.2;
}
.wave-stroke {
  fill: none;
  stroke-width: 3.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 10px 18px rgba(15, 118, 110, 0.12));
}
.wave-meta {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(15, 118, 110, 0.1);
}
.eeg-tone {
  color: #0f766e;
}
.ecg-tone {
  color: #ea580c;
}
.metric-card,
.summary-box,
.note-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.12);
}
.metric-card {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 12px;
  min-height: 158px;
  align-content: start;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(244, 250, 250, 0.96));
}
.metric-card::after {
  content: '';
  position: absolute;
  inset: auto -18px -18px auto;
  width: 72px;
  height: 72px;
  border-radius: 999px;
  opacity: 0.12;
  background: currentColor;
}
.metric-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.metric-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 42px;
  padding: 0 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid currentColor;
  font-weight: 700;
}
.metric-caption {
  font-style: normal;
  font-size: 0.78rem;
  color: #6a7b8d;
}
.metric-card strong {
  display: block;
  font-size: 2rem;
  line-height: 1;
}
.metric-progress {
  height: 10px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  overflow: hidden;
}
.metric-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, currentColor, rgba(255,255,255,0.85));
}
.metric-card p {
  margin: 0;
  color: #66788a;
  font-size: 0.86rem;
}
.summary-box span { color: #5c6d7e; margin-bottom: 8px; }
.tone-w { color: #0f766e; }
.tone-n1 { color: #8b5cf6; }
.tone-n2 { color: #0284c7; }
.tone-n3 { color: #1d4ed8; }
.tone-r { color: #ea580c; }
.tone-default { color: #164e63; }
.note-card h3,
.note-card p { margin: 0; }
.note-card p { margin-top: 10px; color: #5c6d7e; line-height: 1.75; }
.visual-grid {
  grid-template-columns: 1fr;
}
.chart-card {
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.08), rgba(22, 78, 99, 0.03)), rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(15, 118, 110, 0.12);
}
.overview-stack-card {
  display: grid;
  gap: 14px;
}
.stack-block {
  display: grid;
  gap: 12px;
}
.stack-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(15, 118, 110, 0.14), transparent);
}
.chart-shell.split-shell,
.chart-shell.compact-split-shell {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(180px, 0.82fr);
  gap: 14px;
  align-items: center;
}
.viz-chart {
  width: 100%;
}
.pie-viz {
  min-height: 320px;
}
.trend-viz {
  min-height: 320px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(243,250,249,0.82));
}
.compact-pie {
  height: 220px;
  min-height: 220px;
}
.compact-trend {
  height: 210px;
  min-height: 210px;
}
.stage-legend {
  display: grid;
  gap: 12px;
}
.compact-legend {
  gap: 10px;
  align-content: center;
}
.legend-item {
  display: grid;
  grid-template-columns: 12px 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.08);
}
.compact-legend .legend-item {
  padding: 10px 12px;
}
.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: 0 0 0 5px rgba(15, 118, 110, 0.06);
}
.legend-item strong {
  font-size: 1rem;
  color: #163042;
}
.legend-item em {
  font-style: normal;
  font-weight: 700;
  color: #486174;
}
.chart-head span,
.chart-head strong,
.artifact-item span,
.artifact-item strong {
  display: block;
}
.chart-head span,
.artifact-item span {
  color: #5c6d7e;
  margin-bottom: 6px;
}
.diagnosis-side-grid {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}
.summary-card {
  min-height: 142px;
}
.summary-card p {
  font-size: 1rem;
}
.export-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.08), rgba(22, 78, 99, 0.03)), rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(15, 118, 110, 0.12);
}
.artifact-item {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(15, 118, 110, 0.1);
}
.artifact-item strong {
  font-size: 1.15rem;
  line-height: 1.25;
  color: #163042;
}
.download-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(15, 118, 110, 0.06);
  border: 1px dashed rgba(15, 118, 110, 0.18);
}
.download-box span,
.download-box strong {
  display: block;
}
.download-box span {
  color: #5c6d7e;
  margin-bottom: 8px;
}
.subtle-download {
  white-space: nowrap;
  box-shadow: 0 10px 26px rgba(15, 118, 110, 0.18);
}
.waiting-panel {
  margin-top: 18px;
  min-height: 220px;
  border-radius: 28px;
  display: grid;
  place-items: center;
  text-align: center;
  padding: 28px 32px;
  gap: 12px;
}
.deep-waiting { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.12); }
.plain-waiting { background: linear-gradient(180deg, rgba(15, 118, 110, 0.06), rgba(22, 78, 99, 0.02)), rgba(255, 255, 255, 0.78); border: 1px dashed rgba(15, 118, 110, 0.18); }
.compact-waiting { min-height: 180px; }
.wide-waiting { min-height: 260px; }
.waiting-icon {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}
.plain-waiting .waiting-icon { background: rgba(15, 118, 110, 0.12); color: #0f766e; }
.spinner-ring {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 3px solid rgba(15, 118, 110, 0.14);
  border-top-color: #0f766e;
  animation: spin-ring 0.9s linear infinite;
}
.spinner-ring.light {
  border-color: rgba(255, 255, 255, 0.22);
  border-top-color: #ffffff;
}
.loading-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.button-spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2.5px solid rgba(255, 255, 255, 0.35);
  border-top-color: #ffffff;
  animation: spin-ring 0.9s linear infinite;
}
.waiting-panel h3,
.waiting-panel p { margin: 0; }
.waiting-panel h3 { font-size: 1.28rem; }
.waiting-panel p { max-width: 48ch; line-height: 1.72; }
.deep-waiting p { color: rgba(255, 255, 255, 0.76); }
.plain-waiting p { color: #5c6d7e; }
.rule-tools { display: grid; gap: 16px; margin: 18px 0 20px; }
.mode-toggle { display: flex; gap: 12px; flex-wrap: wrap; }
.soft-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  border: 1px solid rgba(15, 118, 110, 0.12);
  color: #164e63;
}
.soft-chip.active { background: rgba(15, 118, 110, 0.16); }
.filter-bar.compact { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 0; }
.filter-group { display: grid; gap: 8px; }
.filter-group label { font-size: 0.85rem; color: #5c6d7e; }
.filter-group input,
.filter-group select {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.76);
}
.activation-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.rule-grid { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 1180px) {
  .two-col,
  .rule-grid,
  .summary-metrics,
  .filter-bar.compact,
  .activation-summary,
  .waveform-grid,
  .visual-grid { grid-template-columns: 1fr; }
  .chart-shell.split-shell,
  .chart-shell.compact-split-shell {
    grid-template-columns: 1fr;
  }
  .download-box {
    flex-direction: column;
    align-items: flex-start;
  }
}

@keyframes spin-ring {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>

