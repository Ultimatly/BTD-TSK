<template>
  <div class="page-view">
    <SectionTitle
      eyebrow="History Detail"
      title="历史诊断详情"
      :description="historyDetail ? `${historyDetail.patient.name} · ${historyDetail.createdAt?.slice(0, 10)}` : '历史详情载入中'"
    />

    <div class="page-actions">
      <RouterLink class="back-link" to="/history">返回历史记录</RouterLink>
      <button type="button" class="delete-history-btn" @click="askRemoveHistory">删除记录</button>
    </div>

    <Transition name="notice-slide">
      <div v-if="feedback.message" class="feedback-banner" :class="feedback.type">
        <div>
          <strong>{{ feedback.type === 'success' ? '操作成功' : '操作失败' }}</strong>
          <p>{{ feedback.message }}</p>
        </div>
        <button type="button" class="feedback-close" @click="clearFeedback">×</button>
      </div>
    </Transition>

    <div v-if="!historyDetail" class="loading-shell">
      <div class="spinner-ring large"></div>
      <h3>正在加载历史详情</h3>
      <p>正在读取诊断结果、规则与波形数据，请稍候。</p>
    </div>

    <DiagnosisResultDetail
      v-if="historyDetail"
      :detail="historyDetail"
      :waveform-preview="waveformPreview"
      :waveform-loading="waveformLoading"
      :rules-loading="rulesLoading"
      :status-text="historyStatusText"
      :download-file-name="historyArtifactName"
      :download-disabled="!hasHistoryArtifact"
      @download="downloadHistoryPredictionFile"
    />

    <Teleport to="body">
      <Transition name="history-modal">
        <div v-if="showDeleteDialog" class="history-modal-overlay" @click.self="closeDeleteDialog">
          <div class="delete-dialog-card">
            <div class="delete-icon-wrap">
              <div class="delete-icon">!</div>
            </div>
            <h3>确认删除这条历史记录吗？</h3>
            <p>删除后，这次诊断对应的结果、规则激活、原始上传文件和产物文件都会一并移除。</p>
            <div class="delete-actions">
              <button type="button" class="secondary-btn" @click="closeDeleteDialog">取消</button>
              <button type="button" class="danger-btn" @click="confirmRemoveHistory">确认删除</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import RuleCard from '@/components/rules/RuleCard.vue'
import DiagnosisResultDetail from '@/components/diagnosis/DiagnosisResultDetail.vue'
import { api, mapRule } from '@/api'

const STAGE_COLOR_MAP = {
  W: '#0f766e',
  N1: '#8b5cf6',
  N2: '#0284c7',
  N3: '#1d4ed8',
  R: '#ea580c',
}

const STAGE_LEVEL_MAP = {
  W: 4,
  N1: 3,
  N2: 2,
  N3: 1,
  R: 0,
}

const route = useRoute()
const router = useRouter()
const historyDetail = ref(null)
const waveformPreview = ref(null)
const waveformLoading = ref(true)
const rulesLoading = ref(true)
const showDeleteDialog = ref(false)
const feedback = ref({ type: 'success', message: '' })
const stagePieChartRef = ref(null)
const stageTrendChartRef = ref(null)
let feedbackTimer = null
let stagePieChart = null
let stageTrendChart = null
const layerFilter = ref('全部层级')
const targetFilter = ref('全部类别')
const keyword = ref('')
const sortMode = ref('按激活强度降序')

const historyStatusText = computed(() => (historyDetail.value?.status === 'done' ? '分析完成' : historyDetail.value?.status || '--'))
const rawStageStats = computed(() => historyDetail.value?.stageStats || [])
const stageLegendItems = computed(() =>
  rawStageStats.value.map((item) => ({
    label: item.label,
    value: Number(item.value) || 0,
    valueText: `${Number(item.value || 0).toFixed(0)}%`,
    color: STAGE_COLOR_MAP[item.label] || '#164e63',
  })),
)
const stageTimeline = computed(() => {
  const rows = historyDetail.value?.stageTimeline || []
  if (!rows.length) return []
  return rows.map((item) => ({
    timeMinute: Number(item.timeSec || 0) / 60,
    stage: item.stage,
    stageLevel: STAGE_LEVEL_MAP[item.stage] ?? 0,
  }))
})
const allRules = computed(() => (historyDetail.value?.rules || []).map(mapRule))
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

const topRuleActivation = computed(() => {
  const top = filteredRules.value[0]
  return top ? `规则 #${top.id} · ${top.strength.toFixed(3)}` : '暂无'
})
const historyArtifact = computed(() =>
  (historyDetail.value?.artifacts || []).find((item) => item.role === 'artifact_csv'),
)
const hasHistoryArtifact = computed(() => Boolean(historyArtifact.value?.name))
const historyArtifactName = computed(() => historyArtifact.value?.name || '预测结果暂不可用')

function ensurePieChart() {
  if (!stagePieChartRef.value) return null
  if (!stagePieChart) stagePieChart = echarts.init(stagePieChartRef.value, null, { renderer: 'svg' })
  return stagePieChart
}

function ensureTrendChart() {
  if (!stageTrendChartRef.value) return null
  if (!stageTrendChart) stageTrendChart = echarts.init(stageTrendChartRef.value, null, { renderer: 'svg' })
  return stageTrendChart
}

function buildStagePieOption() {
  const data = stageLegendItems.value
    .filter((item) => item.value > 0)
    .map((item) => ({
      name: item.label,
      value: item.value,
      itemStyle: { color: item.color },
    }))

  return {
    animationDuration: 900,
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(10, 31, 45, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: ({ name, value }) => `${name}<br/>占比 ${Number(value).toFixed(0)}%`,
    },
    series: [
      {
        type: 'pie',
        radius: ['42%', '74%'],
        center: ['50%', '52%'],
        startAngle: 90,
        avoidLabelOverlap: false,
        padAngle: 2,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: '#f7fbfb',
          borderWidth: 4,
          shadowBlur: 18,
          shadowColor: 'rgba(15, 118, 110, 0.16)',
        },
        emphasis: { scale: true, scaleSize: 8 },
        data,
      },
    ],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '40%',
        style: {
          text: `${historyDetail.value?.predictionCount || 0}`,
          fill: '#163042',
          font: '700 24px \"Segoe UI\", \"PingFang SC\", sans-serif',
          textAlign: 'center',
        },
      },
      {
        type: 'text',
        left: 'center',
        top: '55%',
        style: {
          text: '总样本',
          fill: '#6b7d90',
          font: '500 12px \"Segoe UI\", \"PingFang SC\", sans-serif',
          textAlign: 'center',
        },
      },
    ],
  }
}

function buildStageTrendOption() {
  const rows = stageTimeline.value
  return {
    animationDuration: 900,
    grid: {
      left: 50,
      right: 18,
      top: 18,
      bottom: 34,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(15, 118, 110, 0.28)' } },
      backgroundColor: 'rgba(10, 31, 45, 0.92)',
      borderWidth: 0,
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params) => {
        const point = params?.[0]
        if (!point) return ''
        const raw = rows[point.dataIndex]
        return `${raw.timeMinute.toFixed(1)} 分钟<br/>阶段 ${raw.stage}`
      },
    },
    xAxis: {
      type: 'category',
      data: rows.map((item) => item.timeMinute.toFixed(1)),
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(15, 118, 110, 0.16)' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#708399',
        fontSize: 11,
        interval: rows.length > 12 ? Math.ceil(rows.length / 6) : 0,
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 4,
      interval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: 'rgba(15, 118, 110, 0.08)' } },
      axisLabel: {
        color: '#708399',
        fontSize: 11,
        formatter: (value) => ['R', 'N3', 'N2', 'N1', 'W'][value] || '',
      },
    },
    series: [
      {
        type: 'line',
        step: 'end',
        smooth: 0.12,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: {
          width: 2.5,
          color: '#0f766e',
          shadowBlur: 12,
          shadowColor: 'rgba(15, 118, 110, 0.18)',
        },
        itemStyle: {
          color: '#0f766e',
          borderColor: '#ecfeff',
          borderWidth: 2,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(45, 212, 191, 0.18)' },
            { offset: 1, color: 'rgba(45, 212, 191, 0.02)' },
          ]),
        },
        data: rows.map((item) => item.stageLevel),
      },
    ],
  }
}

function renderHistoryCharts() {
  const pie = ensurePieChart()
  const trend = ensureTrendChart()
  pie?.setOption(buildStagePieOption(), true)
  trend?.setOption(buildStageTrendOption(), true)
  pie?.resize()
  trend?.resize()
}

function handleChartResize() {
  stagePieChart?.resize()
  stageTrendChart?.resize()
}

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

function downloadHistoryPredictionFile() {
  if (!historyDetail.value?.id || !hasHistoryArtifact.value) {
    showFeedback('当前还没有可下载的预测结果。', 'error')
    return
  }
  window.open(api.getHistoryArtifactCsvUrl(historyDetail.value.id), '_blank', 'noopener')
}

const askRemoveHistory = () => {
  showDeleteDialog.value = true
}

const closeDeleteDialog = () => {
  showDeleteDialog.value = false
}

const confirmRemoveHistory = async () => {
  try {
    await api.deleteHistory(route.params.id)
    showFeedback('历史记录已删除。')
    closeDeleteDialog()
    setTimeout(() => {
      router.push('/history')
    }, 500)
  } catch (error) {
    showFeedback(error.message || '删除历史记录失败。', 'error')
  }
}

const eegPreviewLabel = computed(() => {
  if (!waveformPreview.value?.eeg?.points?.length) return `${historyDetail.value?.patient?.code || '--'} · EEG 波形缺失`
  return `${waveformPreview.value.recordName} · ${waveformPreview.value.eeg.channel || 'EEG'}`
})

const ecgPreviewLabel = computed(() => {
  if (!waveformPreview.value?.ecg?.points?.length) return `${historyDetail.value?.patient?.code || '--'} · ECG 波形缺失`
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

const eegWavePath = computed(() => buildWavePath(waveformPreview.value?.eeg?.points || []))
const ecgWavePath = computed(() => buildWavePath(waveformPreview.value?.ecg?.points || []))

const eegMetaText = computed(() => {
  if (!waveformPreview.value?.eeg?.points?.length) return '未保留 EEG 原始采样'
  const eeg = waveformPreview.value.eeg
  return `${eeg.sampleCount} 点 · ${eeg.durationSeconds.toFixed(1)} 秒`
})

const ecgMetaText = computed(() => {
  if (!waveformPreview.value?.ecg?.points?.length) return '未保留 ECG 原始采样'
  const ecg = waveformPreview.value.ecg
  return `${ecg.sampleCount} 点 · ${ecg.durationSeconds.toFixed(1)} 秒`
})

onMounted(async () => {
  try {
    historyDetail.value = await api.getHistoryDetail(route.params.id)
    api.getHistoryRules(route.params.id)
      .then((rules) => {
        if (!historyDetail.value) return
        historyDetail.value = {
          ...historyDetail.value,
          rules,
        }
        rulesLoading.value = false
      })
      .catch(() => {
        if (!historyDetail.value) return
        historyDetail.value = {
          ...historyDetail.value,
          rules: [],
        }
        rulesLoading.value = false
      })
    api.getHistoryWaveform(route.params.id)
      .then((waveform) => {
        waveformPreview.value = waveform
        waveformLoading.value = false
      })
      .catch(() => {
        waveformPreview.value = null
        waveformLoading.value = false
      })
  } catch (error) {
    console.error('加载历史详情失败:', error)
    showFeedback(error.message || '加载历史详情失败。', 'error')
    rulesLoading.value = false
    waveformLoading.value = false
  }
})

watch(
  () => [historyDetail.value?.stageStats, historyDetail.value?.stageTimeline],
  async () => {
    if (!historyDetail.value) return
    await nextTick()
    renderHistoryCharts()
  },
  { deep: true },
)

onMounted(() => {
  window.addEventListener('resize', handleChartResize)
})

onBeforeUnmount(() => {
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

.loading-shell {
  min-height: 46vh;
  display: grid;
  place-items: center;
  text-align: center;
  gap: 12px;
  color: #5c6d7e;
}

.loading-shell h3,
.loading-shell p {
  margin: 0;
}

.notice-slide-enter-active,
.notice-slide-leave-active,
.history-modal-enter-active,
.history-modal-leave-active {
  transition: all 0.22s ease;
}

.notice-slide-enter-from,
.notice-slide-leave-to,
.history-modal-enter-from,
.history-modal-leave-to {
  opacity: 0;
}

.two-col,
.rule-grid {
  display: grid;
  gap: 24px;
}

.two-col {
  grid-template-columns: 1.1fr 0.95fr;
}

.page-actions {
  margin-bottom: 18px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.back-link {
  display: inline-flex;
  align-items: center;
  padding: 10px 16px;
  border-radius: 999px;
  text-decoration: none;
  background: rgba(15, 118, 110, 0.08);
  border: 1px solid rgba(15, 118, 110, 0.12);
  color: #164e63;
}

.delete-history-btn,
.secondary-btn,
.danger-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  border-radius: 999px;
  border: 0;
}

.delete-history-btn,
.danger-btn {
  color: #b42318;
  background: rgba(220, 38, 38, 0.1);
}

.secondary-btn {
  color: #164e63;
  background: rgba(15, 118, 110, 0.08);
}

.action-button {
  padding: 12px 18px;
  border-radius: 999px;
  border: 0;
}

.action-button.primary {
  color: #fff;
  background: linear-gradient(135deg, #0f766e, #164e63);
}

.action-button.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.spinner-ring {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 3px solid rgba(15, 118, 110, 0.14);
  border-top-color: #0f766e;
  animation: spin-ring 0.9s linear infinite;
  flex: 0 0 auto;
}

.spinner-ring.warm {
  border-color: rgba(249, 115, 22, 0.14);
  border-top-color: #f97316;
}

.spinner-ring.large {
  width: 42px;
  height: 42px;
  border-width: 4px;
}

.result-panel {
  margin-top: 20px;
  display: grid;
  gap: 18px;
}

.result-callout {
  padding: 22px 24px;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.result-callout h2 {
  margin: 10px 0 0;
  font-size: clamp(1.62rem, 1.95vw, 2.1rem);
  line-height: 1.22;
}

.result-callout p {
  margin: 14px 0 0;
  max-width: 64ch;
  color: rgba(255, 255, 255, 0.74);
  line-height: 1.72;
}

.summary-label {
  color: rgba(255, 255, 255, 0.72);
}

.result-stats {
  display: grid;
  gap: 14px;
}

.summary-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

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
.summary-box strong {
  display: block;
}

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

.wave-loading,
.rules-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  min-height: 220px;
  padding: 24px;
  text-align: left;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(15, 118, 110, 0.1);
  color: #5c6d7e;
}

.wave-loading {
  min-height: 260px;
  flex-direction: column;
  text-align: center;
}

.rules-loading strong,
.rules-loading p,
.wave-loading span {
  margin: 0;
}

.rules-loading p {
  margin-top: 6px;
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

.eeg-tone { color: #0f766e; }
.ecg-tone { color: #ea580c; }

.summary-box,
.note-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.12);
}
.summary-box span { color: #5c6d7e; margin-bottom: 8px; }

.diagnosis-side-grid,
.visual-grid { display: grid; gap: 16px; margin-top: 18px; }
.note-card h3,
.note-card p { margin: 0; }
.note-card p { margin-top: 10px; color: #5c6d7e; line-height: 1.75; }
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
.artifact-item span,
.artifact-item strong,
.download-box span,
.download-box strong {
  display: block;
}
.artifact-item span,
.download-box span {
  color: #5c6d7e;
  margin-bottom: 6px;
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
.download-box strong {
  color: #163042;
}
.subtle-download {
  white-space: nowrap;
  box-shadow: 0 10px 26px rgba(15, 118, 110, 0.18);
}
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
  gap: 0;
}
.stack-block {
  display: grid;
  gap: 14px;
}
.stack-divider {
  height: 1px;
  margin: 16px 0;
  background: linear-gradient(90deg, rgba(15, 118, 110, 0.02), rgba(15, 118, 110, 0.12), rgba(15, 118, 110, 0.02));
}
.chart-head span,
.chart-head strong,
.legend-item strong,
.legend-item em {
  display: block;
}
.chart-head span,
.legend-item em {
  color: #5c6d7e;
  margin-bottom: 8px;
}
.chart-shell.compact-split-shell {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(220px, 0.8fr);
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.08);
}
.viz-chart {
  width: 100%;
}
.compact-pie {
  min-height: 220px;
}
.compact-trend {
  min-height: 210px;
  padding: 6px 0 2px;
}
.stage-legend.compact-legend {
  display: grid;
  gap: 10px;
}
.legend-item {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(15, 118, 110, 0.08);
}
.legend-item strong {
  margin: 0;
  color: #173042;
  font-size: 0.98rem;
}
.legend-item em {
  margin: 0;
  font-style: normal;
  font-weight: 700;
}
.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: 0 0 0 5px rgba(255, 255, 255, 0.54);
}

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
.filter-bar.compact {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.filter-group { display: grid; gap: 8px; }
.filter-group label { color: #5c6d7e; }
.filter-group select,
.filter-group input {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.9);
  color: #163042;
}
.activation-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.rule-grid { grid-template-columns: repeat(3, 1fr); }

.history-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(12, 24, 34, 0.28);
  backdrop-filter: blur(14px);
}

.delete-dialog-card {
  width: min(520px, calc(100vw - 48px));
  text-align: center;
  padding: 28px;
  border-radius: 28px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 251, 251, 0.98));
  border: 1px solid rgba(15, 118, 110, 0.12);
  color: #173042;
  box-shadow: 0 32px 90px rgba(15, 35, 52, 0.24);
}

.delete-icon-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 14px;
}

.delete-icon {
  width: 64px;
  height: 64px;
  border-radius: 22px;
  display: grid;
  place-items: center;
  background: rgba(220, 38, 38, 0.08);
  color: #b42318;
  font-size: 1.8rem;
  font-weight: 700;
}

.delete-dialog-card h3,
.delete-dialog-card p {
  margin: 0;
}

.delete-dialog-card p {
  margin-top: 12px;
  line-height: 1.8;
  color: #5c6d7e;
}

.delete-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 22px;
}

@keyframes spin-ring {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .two-col,
  .summary-metrics,
  .waveform-grid,
  .filter-bar.compact,
  .activation-summary,
  .rule-grid,
  .visual-grid { grid-template-columns: 1fr; }

  .chart-shell.compact-split-shell {
    grid-template-columns: 1fr;
  }

  .download-box {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

