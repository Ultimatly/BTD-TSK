<template>
  <div v-if="detail" class="result-detail" :class="{ 'reveal-ready': revealReady }">
    <section class="two-col">
      <GlassPanel tone="deep" class="reveal-shell reveal-delay-1">
        <SectionTitle title="结果总览" />
        <div class="result-panel">
          <div class="result-callout">
            <span class="summary-label">最终结论</span>
            <h2>{{ diagnosisNarrative.conclusion }}</h2>
            <p>{{ diagnosisNarrative.advice }}</p>
          </div>
          <div class="result-stats">
            <div class="summary-chip status-card">
              <span>诊断状态</span>
              <strong>{{ statusText }}</strong>
            </div>
            <div class="summary-metrics">
              <div class="summary-chip compact">
                <span>风险等级</span>
                <strong>{{ detail.risk }}</strong>
              </div>
              <div class="summary-chip compact">
                <span>主导阶段</span>
                <strong>{{ detail.dominantStage }}</strong>
              </div>
              <div class="summary-chip compact">
                <span>重点类别</span>
                <strong>{{ detail.focusClass }}</strong>
              </div>
            </div>
          </div>
        </div>
      </GlassPanel>

      <GlassPanel class="reveal-shell reveal-delay-2">
        <SectionTitle title="输入波形回看" />
        <div v-if="waveformLoading" class="wave-loading-shell">
          <div class="spinner-ring"></div>
          <h3>正在读取波形数据</h3>
          <p>正在准备 EEG / ECG 波形回看，请稍候。</p>
        </div>
        <div v-else-if="hasWaveformPreview" class="waveform-grid">
          <div class="wave-card eeg-tone">
            <div class="wave-head">
              <div>
                <span>EEG 输入波形</span>
                <strong>{{ eegPreviewLabel }}</strong>
              </div>
              <em>EEG</em>
            </div>
            <div class="wave-canvas">
              <svg viewBox="0 0 680 180" preserveAspectRatio="none" aria-label="EEG waveform">
                <defs>
                  <linearGradient id="sharedEegLineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#0f766e" />
                    <stop offset="50%" stop-color="#14b8a6" />
                    <stop offset="100%" stop-color="#22d3ee" />
                  </linearGradient>
                </defs>
                <g class="wave-grid-lines">
                  <line v-for="y in [24, 58, 92, 126, 160]" :key="`shared-eeg-${y}`" x1="0" :y1="y" x2="680" :y2="y" />
                </g>
                <path class="wave-baseline" d="M0 92 H680" />
                <path class="wave-stroke" :d="eegWavePath" stroke="url(#sharedEegLineGradient)" />
              </svg>
            </div>
            <div class="wave-meta">
              <span>采样片段</span>
              <strong>{{ eegMetaText }}</strong>
            </div>
          </div>

          <div class="wave-card ecg-tone">
            <div class="wave-head">
              <div>
                <span>ECG 输入波形</span>
                <strong>{{ ecgPreviewLabel }}</strong>
              </div>
              <em>ECG</em>
            </div>
            <div class="wave-canvas">
              <svg viewBox="0 0 680 180" preserveAspectRatio="none" aria-label="ECG waveform">
                <defs>
                  <linearGradient id="sharedEcgLineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#ea580c" />
                    <stop offset="50%" stop-color="#f97316" />
                    <stop offset="100%" stop-color="#fb7185" />
                  </linearGradient>
                </defs>
                <g class="wave-grid-lines">
                  <line v-for="y in [24, 58, 92, 126, 160]" :key="`shared-ecg-${y}`" x1="0" :y1="y" x2="680" :y2="y" />
                </g>
                <path class="wave-baseline" d="M0 104 H680" />
                <path class="wave-stroke" :d="ecgWavePath" stroke="url(#sharedEcgLineGradient)" />
              </svg>
            </div>
            <div class="wave-meta">
              <span>心律片段</span>
              <strong>{{ ecgMetaText }}</strong>
            </div>
          </div>
        </div>
        <div v-else class="waiting-panel plain-waiting compact-waiting">
          <div class="waiting-icon">
            <div class="spinner-ring"></div>
          </div>
          <h3>暂无可回看的波形</h3>
          <p>当前记录没有保留可展示的 EEG / ECG 原始采样。</p>
        </div>
      </GlassPanel>
    </section>

    <section class="two-col">
      <GlassPanel class="reveal-shell reveal-delay-3">
        <SectionTitle title="可视化结果区" />
        <div class="visual-grid">
          <div class="chart-card overview-stack-card">
            <div class="stack-block top-block">
              <div class="chart-head">
                <span>阶段分布</span>
                <strong>睡眠分期占比</strong>
              </div>
              <div class="chart-shell compact-split-shell">
                <div ref="stagePieChartRef" class="viz-chart pie-viz compact-pie"></div>
                <div class="stage-legend compact-legend">
                  <div v-for="item in stageLegendItems" :key="item.label" class="legend-item">
                    <span class="legend-dot" :style="{ background: item.color }"></span>
                    <strong>{{ item.label }}</strong>
                    <em>{{ item.valueText }}</em>
                  </div>
                </div>
              </div>
            </div>
            <div class="stack-divider"></div>
            <div class="stack-block bottom-block">
              <div class="chart-head">
                <span>阶段演变</span>
                <strong>睡眠阶段随时间变化</strong>
              </div>
              <div ref="stageTrendChartRef" class="viz-chart trend-viz compact-trend"></div>
            </div>
          </div>
        </div>
      </GlassPanel>

      <GlassPanel class="reveal-shell reveal-delay-4">
        <SectionTitle title="诊断摘要与导出" />
        <div class="diagnosis-side-grid">
          <div class="note-card summary-card">
            <h3>诊断摘要</h3>
            <p>{{ diagnosisNarrative.summary }}</p>
          </div>
          <div class="export-card">
            <div class="artifact-item">
              <span>运行编号</span>
              <strong>{{ detail.id }}</strong>
            </div>
            <div class="artifact-item">
              <span>预测样本数</span>
              <strong>{{ detail.predictionCount }}</strong>
            </div>
            <div class="artifact-item">
              <span>使用模型</span>
              <strong>{{ modelDisplayName }}</strong>
            </div>
            <div class="download-box">
              <div>
                <span>预测结果文件</span>
                <strong>{{ downloadFileName }}</strong>
              </div>
              <button
                class="action-button primary subtle-download"
                type="button"
                :disabled="downloadDisabled"
                @click="emit('download')"
              >
                下载预测文件
              </button>
            </div>
          </div>
        </div>
      </GlassPanel>
    </section>

    <GlassPanel class="reveal-shell reveal-delay-5">
      <SectionTitle eyebrow="Rule Evidence" title="规则激活检测区" />
      <div class="rule-tools">
        <div class="filter-bar compact">
          <div class="filter-group">
            <label>类别筛选</label>
            <select v-model="targetFilter">
              <option>全部类别</option>
              <option>W</option>
              <option>N1</option>
              <option>N2</option>
              <option>N3</option>
              <option>R</option>
            </select>
          </div>
          <div class="filter-group">
            <label>排序方式</label>
            <select v-model="sortMode">
              <option>按激活强度降序</option>
              <option>按规则编号</option>
            </select>
          </div>
          <div class="filter-group">
            <label>搜索规则</label>
            <input v-model="keyword" placeholder="输入规则编号或特征关键词" />
          </div>
        </div>
      </div>

      <div v-if="rulesLoading" class="rules-loading">
        <div class="spinner-ring"></div>
        <div>
          <strong>正在补充规则激活结果</strong>
          <p>规则证据正在准备中，稍后会自动显示。</p>
        </div>
      </div>

      <template v-else-if="filteredRules.length">
        <div class="activation-summary">
            <div class="summary-box">
              <span>当前显示</span>
              <strong>{{ filteredRules.length }} 条规则</strong>
            </div>
          <div class="summary-box">
            <span>记录类别焦点</span>
            <strong>{{ detail.focusClass }} 倾向规则</strong>
          </div>
          <div class="summary-box">
            <span>最高激活规则</span>
            <strong>{{ topRuleActivation }}</strong>
          </div>
        </div>

        <div class="rule-grid">
          <RuleCard v-for="rule in filteredRules" :key="rule.id" :rule="rule" compact />
        </div>
      </template>

      <div v-else class="waiting-panel plain-waiting wide-waiting">
        <div class="waiting-icon">
          <div class="spinner-ring"></div>
        </div>
        <h3>暂无规则激活结果</h3>
        <p>当前记录还没有可展示的规则证据。</p>
      </div>
    </GlassPanel>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import RuleCard from '@/components/rules/RuleCard.vue'
import { mapRule } from '@/api'

const props = defineProps({
  detail: {
    type: Object,
    required: true,
  },
  waveformPreview: {
    type: Object,
    default: null,
  },
  waveformLoading: {
    type: Boolean,
    default: false,
  },
  rulesLoading: {
    type: Boolean,
    default: false,
  },
  statusText: {
    type: String,
    default: '分析完成',
  },
  downloadFileName: {
    type: String,
    default: 'predictions.csv',
  },
  downloadDisabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['download'])

const modelDisplayName = computed(() => props.detail?.model?.name || props.detail?.model?.code || '--')

const STAGE_NAME_MAP = {
  W: '清醒',
  N1: 'N1',
  N2: 'N2',
  N3: 'N3',
  R: 'REM',
}

const STAGE_COLOR_MAP = {
  W: '#0f766e',
  N1: '#8b5cf6',
  N2: '#0284c7',
  N3: '#1d4ed8',
  R: '#ea580c',
}
const STAGE_LEVEL_MAP = { W: 4, N1: 3, N2: 2, N3: 1, R: 0 }

function formatStageLabel(label, withStage = true) {
  const base = STAGE_NAME_MAP[label] || label || 'N2'
  return withStage ? `${base}阶段` : base
}

function formatStageWithRatio(label, ratio, withStage = true) {
  const stageText = formatStageLabel(label, withStage)
  return Number.isFinite(ratio) ? `${stageText}（${Number(ratio).toFixed(1)}%）` : stageText
}

const stagePieChartRef = ref(null)
const stageTrendChartRef = ref(null)
const targetFilter = ref('全部类别')
const keyword = ref('')
const sortMode = ref('按激活强度降序')
const revealReady = ref(false)
let stagePieChart = null
let stageTrendChart = null

const hasWaveformPreview = computed(() =>
  Boolean(
    props.waveformPreview &&
    ((props.waveformPreview.eeg?.points?.length || 0) > 0 || (props.waveformPreview.ecg?.points?.length || 0) > 0),
  ),
)

const stageLegendItems = computed(() =>
  (props.detail?.stageStats || []).map((item) => ({
    label: item.label,
    value: Number(item.value) || 0,
    valueText: `${Number(item.value || 0).toFixed(0)}%`,
    color: STAGE_COLOR_MAP[item.label] || '#164e63',
  })),
)

const stagePercentMap = computed(() => {
  const map = {}
  for (const item of props.detail?.stageStats || []) {
    map[item.label] = Number(item.value) || 0
  }
  return map
})

const diagnosisNarrative = computed(() => {
  const risk = props.detail?.risk || '待评估'
  const dominant = props.detail?.dominantStage || 'N2'
  const focus = props.detail?.focusClass || dominant
  const distribution = stagePercentMap.value
  const ordered = Object.entries(distribution).sort((a, b) => b[1] - a[1])
  const dominantRatio = distribution[dominant]
  const focusRatio = distribution[focus]
  const secondary = ordered.find(([label]) => label !== dominant)?.[0] || null
  const secondaryRatio = secondary ? distribution[secondary] : null

  const dominantText = formatStageWithRatio(dominant, dominantRatio, true)
  const focusText = formatStageWithRatio(focus, focusRatio, true)
  const secondaryText = secondary ? formatStageWithRatio(secondary, secondaryRatio, true) : null

  let conclusion = ''
  let advice = ''

  if (risk === '高风险') {
    if (focus === 'W') {
      conclusion = `本次记录提示${focusText}占比偏高，睡眠连续性下降，整体睡眠结构异常较为明显，需重点关注觉醒相关波动。`
      advice = '建议结合入睡困难、夜间觉醒增多及日间困倦等临床表现综合评估，必要时复查多导睡眠监测。'
    } else if (focus === 'N3') {
      conclusion = `本次记录以${dominantText}为主，但${focusText}相对不足，提示深睡眠恢复能力下降，睡眠结构紊乱较明显。`
      advice = '建议结合疲劳恢复情况、睡眠片段化程度及伴随症状进一步评估，必要时开展连续随访。'
    } else {
      conclusion = `本次记录以${dominantText}为主，伴随${focusText}异常波动，提示睡眠结构失衡较明显，需要重点干预。`
      advice = '建议结合主诉症状、既往病史及夜间事件综合判断，并根据临床需要安排进一步检查。'
    }
  } else if (risk === '中风险') {
    if (focus === 'N3') {
      conclusion = `本次记录整体睡眠结构存在一定波动，以${dominantText}为主，${focusText}偏低，提示深睡眠维持能力一般。`
      advice = '建议结合睡眠恢复感、白天精神状态及复查结果持续观察，必要时进行阶段性干预。'
    } else if (focus === 'N1' || focus === 'R') {
      conclusion = `本次记录以${dominantText}为主，${focusText}波动相对突出，提示阶段转换稳定性仍需关注。`
      advice = '建议结合夜间觉醒、梦境活动及入睡后阶段转换情况综合分析，并继续动态随访。'
    } else {
      conclusion = `本次记录提示睡眠结构存在一定波动，以${dominantText}为主，需继续关注${focusText}相关变化。`
      advice = '建议结合近期作息、主观睡眠质量及必要的复查结果做综合评估。'
    }
  } else {
    conclusion = `本次记录整体睡眠结构相对稳定，以${dominantText}为主，未见明显高风险分期异常。`
    advice = '建议保持规律作息，并结合后续随访结果持续观察睡眠结构变化。'
  }

  const summary = secondaryText
    ? `睡眠分期分布以${dominantText}为主，其次为${secondaryText}，当前重点关注${focusText}相关变化。`
    : `睡眠分期分布以${dominantText}为主，当前重点关注${focusText}相关变化。`

  return { conclusion, summary, advice }
})

const stageTimeline = computed(() => {
  const rows = props.detail?.stageTimeline || []
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

const allRules = computed(() => (props.detail?.rules || []).map(mapRule))
const filteredRules = computed(() => {
  let list = [...allRules.value]
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

const eegPreviewLabel = computed(() => {
  if (!props.waveformPreview?.eeg?.points?.length) return `${props.detail?.patient?.code || '--'} · EEG 波形缺失`
  return `${props.waveformPreview.recordName} · ${props.waveformPreview.eeg.channel || 'EEG'}`
})

const ecgPreviewLabel = computed(() => {
  if (!props.waveformPreview?.ecg?.points?.length) return `${props.detail?.patient?.code || '--'} · ECG 波形缺失`
  return `${props.waveformPreview.recordName} · ${props.waveformPreview.ecg.channel || 'ECG'}`
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

const eegWavePath = computed(() => buildWavePath(props.waveformPreview?.eeg?.points || []))
const ecgWavePath = computed(() => buildWavePath(props.waveformPreview?.ecg?.points || []))

const eegMetaText = computed(() => {
  if (!props.waveformPreview?.eeg?.points?.length) return '未保留 EEG 原始采样'
  const eeg = props.waveformPreview.eeg
  return `${eeg.sampleCount} 点 · ${eeg.durationSeconds.toFixed(1)} 秒`
})

const ecgMetaText = computed(() => {
  if (!props.waveformPreview?.ecg?.points?.length) return '未保留 ECG 原始采样'
  const ecg = props.waveformPreview.ecg
  return `${ecg.sampleCount} 点 · ${ecg.durationSeconds.toFixed(1)} 秒`
})

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
          text: `${props.detail?.predictionCount || 0}`,
          fill: '#163042',
          font: '700 24px "Segoe UI", "PingFang SC", sans-serif',
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
          font: '500 12px "Segoe UI", "PingFang SC", sans-serif',
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

function renderCharts() {
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

function triggerReveal() {
  revealReady.value = false
  window.requestAnimationFrame(() => {
    revealReady.value = true
  })
}

watch(
  () => [props.detail?.stageStats, props.detail?.stageTimeline],
  async () => {
    if (!props.detail) return
    await nextTick()
    renderCharts()
  },
  { deep: true },
)

watch(
  () => props.detail?.id,
  async () => {
    if (!props.detail) return
    await nextTick()
    triggerReveal()
  },
)

onMounted(() => {
  window.addEventListener('resize', handleChartResize)
  triggerReveal()
  nextTick(() => {
    renderCharts()
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleChartResize)
  stagePieChart?.dispose()
  stageTrendChart?.dispose()
  stagePieChart = null
  stageTrendChart = null
})
</script>

<style scoped>
.result-detail {
  display: grid;
  gap: 14px;
}

.reveal-shell {
  opacity: 0;
  transform: translateY(20px) scale(0.988);
  transition:
    opacity 0.58s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.58s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.28s ease;
  transition-delay: var(--reveal-delay, 0ms);
}

.result-detail.reveal-ready .reveal-shell {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.reveal-delay-1 {
  --reveal-delay: 0ms;
}

.reveal-delay-2 {
  --reveal-delay: 90ms;
}

.reveal-delay-3 {
  --reveal-delay: 170ms;
}

.reveal-delay-4 {
  --reveal-delay: 250ms;
}

.reveal-delay-5 {
  --reveal-delay: 330ms;
}

.two-col,
.rule-grid {
  display: grid;
  gap: 18px;
}

.two-col {
  grid-template-columns: 1.1fr 0.95fr;
}

.result-panel {
  margin-top: 20px;
  display: grid;
  gap: 20px;
}

.result-callout {
  position: relative;
  overflow: hidden;
  padding: 24px 26px 22px;
  border-radius: 28px;
  background:
    radial-gradient(circle at 86% 18%, rgba(125, 249, 236, 0.16), transparent 22%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.12), rgba(125, 249, 236, 0.06)),
    rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 16px 36px rgba(5, 29, 40, 0.12);
}

.result-callout::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, rgba(255, 255, 255, 0.12), transparent 38%, transparent 62%, rgba(255, 255, 255, 0.08));
  pointer-events: none;
}

.result-callout h2 {
  position: relative;
  margin: 12px 0 0;
  max-width: 30ch;
  font-size: clamp(1.42rem, 1.7vw, 1.86rem);
  line-height: 1.28;
  letter-spacing: 0.01em;
  text-wrap: pretty;
}

.result-callout p {
  position: relative;
  margin: 16px 0 0;
  max-width: 62ch;
  padding-top: 14px;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.76;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.summary-label {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.74);
  font-size: 0.96rem;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.summary-label::before {
  content: '';
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #7df9ec, #d7fffa);
  box-shadow: 0 0 0 6px rgba(125, 249, 236, 0.12);
}

.result-stats {
  display: grid;
  gap: 16px;
}

.summary-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.summary-metrics > *,
.waveform-grid > *,
.diagnosis-side-grid > *,
.activation-summary > *,
.rule-grid > * {
  opacity: 0;
  transform: translateY(16px);
}

.result-detail.reveal-ready .summary-metrics > *,
.result-detail.reveal-ready .waveform-grid > *,
.result-detail.reveal-ready .diagnosis-side-grid > *,
.result-detail.reveal-ready .activation-summary > *,
.result-detail.reveal-ready .rule-grid > * {
  animation: reveal-fragment 0.56s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

.result-detail.reveal-ready .summary-metrics > *:nth-child(1),
.result-detail.reveal-ready .waveform-grid > *:nth-child(1),
.result-detail.reveal-ready .diagnosis-side-grid > *:nth-child(1),
.result-detail.reveal-ready .activation-summary > *:nth-child(1),
.result-detail.reveal-ready .rule-grid > *:nth-child(1) {
  animation-delay: 120ms;
}

.result-detail.reveal-ready .summary-metrics > *:nth-child(2),
.result-detail.reveal-ready .waveform-grid > *:nth-child(2),
.result-detail.reveal-ready .diagnosis-side-grid > *:nth-child(2),
.result-detail.reveal-ready .activation-summary > *:nth-child(2),
.result-detail.reveal-ready .rule-grid > *:nth-child(2) {
  animation-delay: 190ms;
}

.result-detail.reveal-ready .summary-metrics > *:nth-child(3),
.result-detail.reveal-ready .activation-summary > *:nth-child(3),
.result-detail.reveal-ready .rule-grid > *:nth-child(3) {
  animation-delay: 260ms;
}

.summary-chip {
  padding: 18px 20px;
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.13), rgba(255, 255, 255, 0.08)),
    rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.status-card strong {
  font-size: 1.42rem;
}

.summary-chip.compact {
  min-height: 104px;
}

.summary-chip span,
.summary-chip strong,
.summary-box span,
.summary-box strong,
.wave-head span,
.wave-head strong,
.wave-meta span,
.wave-meta strong,
.chart-head span,
.chart-head strong,
.artifact-item span,
.artifact-item strong,
.download-box span,
.download-box strong {
  display: block;
}

.summary-chip span {
  color: rgba(255, 255, 255, 0.72);
  margin-bottom: 10px;
}

.summary-chip strong {
  font-size: 1.56rem;
  line-height: 1.12;
}

.waveform-grid {
  display: grid;
  grid-template-columns: 1fr;
  grid-auto-rows: minmax(0, 1fr);
  gap: 14px;
  margin-top: 18px;
  height: 500px;
}

.wave-card {
  height: 100%;
  padding: 14px 16px;
  border-radius: 24px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(241, 249, 249, 0.96));
  display: grid;
  gap: 10px;
  align-content: start;
  overflow: hidden;
  transition:
    transform 0.28s ease,
    box-shadow 0.28s ease,
    border-color 0.28s ease;
}

.wave-card:hover {
  transform: translateY(-3px);
  border-color: rgba(15, 118, 110, 0.18);
  box-shadow: 0 18px 36px rgba(15, 35, 52, 0.07);
}

.wave-loading-shell,
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
  margin-top: 18px;
}

.wave-loading-shell {
  flex-direction: column;
  text-align: center;
}

.wave-loading-shell h3,
.wave-loading-shell p,
.rules-loading strong,
.rules-loading p {
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
.wave-meta span,
.chart-head span,
.artifact-item span,
.download-box span {
  color: #5f7183;
  margin-bottom: 6px;
}

.wave-head strong {
  font-size: 0.95rem;
  line-height: 1.3;
}

.wave-head em {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  height: 34px;
  padding: 0 14px;
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
  padding: 8px 10px;
  background:
    radial-gradient(circle at 14% 18%, rgba(255, 255, 255, 0.9), transparent 42%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(245, 250, 250, 0.88));
  border: 1px solid rgba(15, 118, 110, 0.08);
  position: relative;
  overflow: hidden;
}

.wave-canvas::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, rgba(255, 255, 255, 0) 20%, rgba(255, 255, 255, 0.42) 50%, rgba(255, 255, 255, 0) 80%);
  transform: translateX(-140%);
  opacity: 0;
}

.result-detail.reveal-ready .wave-canvas::after {
  opacity: 1;
  animation: waveform-sheen 1.1s ease 0.34s 1 forwards;
}

.wave-canvas svg {
  width: 100%;
  height: 108px;
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

.wave-meta,
.summary-box,
.note-card {
  padding: 12px 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.12);
}

.wave-meta {
  display: none;
}

.eeg-tone {
  color: #0f766e;
}

.ecg-tone {
  color: #ea580c;
}

@keyframes reveal-fragment {
  from {
    opacity: 0;
    transform: translateY(16px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes waveform-sheen {
  from {
    transform: translateX(-140%);
  }

  to {
    transform: translateX(140%);
  }
}

.summary-box span {
  color: #5c6d7e;
  margin-bottom: 8px;
}

.diagnosis-side-grid,
.visual-grid {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

.note-card h3,
.note-card p {
  margin: 0;
}

.note-card p {
  margin-top: 10px;
  color: #5c6d7e;
  line-height: 1.75;
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

.download-box strong {
  color: #163042;
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

.subtle-download {
  white-space: nowrap;
  box-shadow: 0 10px 26px rgba(15, 118, 110, 0.18);
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
  color: #486174;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: 0 0 0 5px rgba(255, 255, 255, 0.54);
}

.rule-tools {
  display: grid;
  gap: 16px;
  margin: 18px 0 20px;
}

.filter-bar.compact {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.filter-group {
  display: grid;
  gap: 8px;
}

.filter-group label {
  color: #5c6d7e;
}

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

.rule-grid {
  grid-template-columns: repeat(3, 1fr);
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

.plain-waiting {
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.06), rgba(22, 78, 99, 0.02)), rgba(255, 255, 255, 0.78);
  border: 1px dashed rgba(15, 118, 110, 0.18);
}

.compact-waiting {
  min-height: 180px;
}

.wide-waiting {
  min-height: 260px;
}

.waiting-icon {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
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

.waiting-panel h3,
.waiting-panel p {
  margin: 0;
}

.waiting-panel p {
  max-width: 48ch;
  line-height: 1.72;
  color: #5c6d7e;
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
  .visual-grid {
    grid-template-columns: 1fr;
  }

  .chart-shell.compact-split-shell {
    grid-template-columns: 1fr;
  }

  .waveform-grid {
    height: auto;
    grid-auto-rows: auto;
  }

  .download-box {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
