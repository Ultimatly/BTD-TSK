<template>
  <div class="page-view patient-detail-page">
    <SectionTitle eyebrow="Patient Detail" title="患者详情" />

    <div class="detail-topbar">
      <RouterLink class="back-link" to="/patients">返回患者管理</RouterLink>
    </div>

    <div v-if="loading" class="loading-shell">
      <div class="spinner-ring large"></div>
      <h3>正在加载患者详情</h3>
      <p>正在读取患者基本信息与历史诊断记录，请稍候。</p>
    </div>

    <div v-else-if="!patient" class="empty-shell">
      <h3>未找到该患者</h3>
      <p>当前编号对应的患者不存在或已被删除。</p>
      <RouterLink class="back-link strong" to="/patients">返回患者管理</RouterLink>
    </div>

    <template v-else>
      <GlassPanel class="patient-summary-card white-card">
        <div class="patient-summary-layout">
          <div class="patient-identity">
            <span class="mini-eyebrow">患者档案</span>
            <h2>{{ patient.name }}</h2>
            <p>{{ patient.id }}</p>
            <div class="patient-basic-row">
              <span>{{ patient.gender }} · {{ patient.age }} 岁</span>
              <span>{{ latestDateText }}</span>
            </div>
          </div>

          <div class="patient-highlight-grid">
            <div class="highlight-card soft">
              <span>当前风险</span>
              <strong :class="['risk-text', riskClass(latestRisk)]">{{ latestRisk }}</strong>
            </div>
            <div class="highlight-card soft">
              <span>历史记录</span>
              <strong>{{ historyList.length }}</strong>
            </div>
            <div class="highlight-card soft">
              <span>重点阶段</span>
              <strong>{{ latestFocus }}</strong>
            </div>
          </div>
        </div>
      </GlassPanel>

      <section class="detail-grid two-up">
        <GlassPanel class="white-card chart-panel">
          <SectionTitle title="风险变化趋势" />
          <div class="trend-stage">
            <div class="trend-head-meta">
              <div class="meta-chip">
                <span>最高风险</span>
                <strong :class="['risk-text', riskClass(peakRiskLabel)]">{{ peakRiskLabel }}</strong>
              </div>
              <div class="meta-chip">
                <span>最新风险</span>
                <strong :class="['risk-text', riskClass(latestRisk)]">{{ latestRisk }}</strong>
              </div>
            </div>
            <div class="trend-chart-shell">
              <div ref="trendChartRef" class="risk-trend-chart"></div>
            </div>
          </div>
        </GlassPanel>

        <GlassPanel class="white-card chart-panel">
          <SectionTitle title="风险等级占比" />
          <div class="distribution-head">
            <div class="distribution-stat-card">
              <span>诊断次数</span>
              <strong>{{ historyList.length }}</strong>
            </div>
            <div class="distribution-stat-card subtle">
              <span>主要风险</span>
              <strong :class="['risk-text', riskClass(dominantRiskLabel)]">{{ dominantRiskLabel }}</strong>
            </div>
          </div>
          <div class="distribution-chart-shell">
            <div ref="pieChartRef" class="risk-pie-chart"></div>
          </div>
        </GlassPanel>
      </section>

      <GlassPanel class="white-card history-list-panel">
        <SectionTitle title="历史记录" />
        <div class="history-list">
          <RouterLink
            v-for="item in sortedHistoryDesc"
            :key="item.id"
            :to="`/history/${item.id}`"
            class="history-item"
          >
            <div class="history-top">
              <strong class="history-date">{{ item.date }}</strong>
              <div class="history-side">
                <span class="focus-tag">{{ deriveFocusLabel(item) }}</span>
                <span class="risk-pill" :class="riskClass(item.risk)">{{ item.risk }}</span>
              </div>
            </div>
            <p class="history-conclusion">{{ item.conclusion }}</p>
            <div class="history-summary">{{ item.summary }}</div>
          </RouterLink>
        </div>
      </GlassPanel>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import * as echarts from 'echarts'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import { api } from '@/api'

const route = useRoute()
const loading = ref(true)
const patient = ref(null)
const historyList = ref([])
const trendChartRef = ref(null)
const pieChartRef = ref(null)
let trendChart = null
let pieChart = null

const riskScoreMap = { 待评估: 0, 低风险: 1, 中风险: 2, 高风险: 3 }
const riskColorMap = {
  待评估: '#94a3b8',
  低风险: '#0f766e',
  中风险: '#f59e0b',
  高风险: '#e11d48',
}

const STAGE_LABEL_MAP = {
  W: 'W',
  N1: 'N1',
  N2: 'N2',
  N3: 'N3',
  R: 'R',
  REM: 'R',
  清醒阶段: 'W',
  清醒: 'W',
}

function deriveFocusLabel(record) {
  if (!record) return '--'

  const direct =
    record.focusClass ||
    record.focus_class ||
    record.dominantStage ||
    record.dominant_stage

  if (direct && STAGE_LABEL_MAP[direct]) return STAGE_LABEL_MAP[direct]
  if (direct) return direct

  const text = `${record.summary || ''} ${record.conclusion || ''}`
  const patterns = [
    [/清醒阶段|清醒相关变化/, 'W'],
    [/\bN1\b|N1阶段/, 'N1'],
    [/\bN2\b|N2阶段/, 'N2'],
    [/\bN3\b|N3阶段/, 'N3'],
    [/\bREM\b|REM阶段/, 'R'],
  ]

  for (const [pattern, label] of patterns) {
    if (pattern.test(text)) return label
  }

  return '--'
}

function toTimeValue(item) {
  return Date.parse(item?.created_at || item?.finished_at || item?.date || '') || 0
}

function formatTrendTick(item, hasMultipleDays) {
  const source = item?.created_at || item?.finished_at || ''
  if (!source) return item?.date?.slice(5) || '--'

  const [datePart, timePart = ''] = source.split(' ')
  const shortDate = datePart.length >= 10 ? datePart.slice(5) : datePart
  const shortTime = timePart.length >= 5 ? timePart.slice(0, 5) : ''
  if (!shortTime) return shortDate
  return hasMultipleDays ? `${shortDate} ${shortTime}` : shortTime
}

function riskClass(risk = '') {
  if (String(risk).includes('高')) return 'high'
  if (String(risk).includes('中')) return 'mid'
  if (String(risk).includes('低')) return 'low'
  return 'neutral'
}

const sortedHistoryAsc = computed(() => [...historyList.value].sort((a, b) => toTimeValue(a) - toTimeValue(b)))
const sortedHistoryDesc = computed(() => [...historyList.value].sort((a, b) => toTimeValue(b) - toTimeValue(a)))
const latestRecord = computed(() => sortedHistoryDesc.value[0] || null)
const latestRisk = computed(() => latestRecord.value?.risk || patient.value?.risk || '待评估')
const latestFocus = computed(() => deriveFocusLabel(latestRecord.value))
const latestDateText = computed(() => latestRecord.value ? `最近诊断 ${latestRecord.value.date}` : '暂无历史诊断')
const peakRiskLabel = computed(() => {
  const list = sortedHistoryAsc.value
  if (!list.length) return latestRisk.value
  const peak = [...list].sort((a, b) => (riskScoreMap[b.risk] || 0) - (riskScoreMap[a.risk] || 0))[0]
  return peak?.risk || latestRisk.value
})
const dominantRiskLabel = computed(() => {
  const list = historyList.value
  if (!list.length) return latestRisk.value

  const counts = new Map()
  for (const item of list) {
    const label = item.risk || '待评估'
    counts.set(label, (counts.get(label) || 0) + 1)
  }

  return [...counts.entries()]
    .sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1]
      if ((riskScoreMap[b[0]] || 0) !== (riskScoreMap[a[0]] || 0)) {
        return (riskScoreMap[b[0]] || 0) - (riskScoreMap[a[0]] || 0)
      }
      if (b[0] === latestRisk.value) return 1
      if (a[0] === latestRisk.value) return -1
      return 0
    })[0]?.[0] || latestRisk.value
})

const trendPoints = computed(() => {
  const list = sortedHistoryAsc.value
  if (!list.length) return []
  const daySet = new Set(list.map((item) => String(item.date || '').slice(0, 10)).filter(Boolean))
  const hasMultipleDays = daySet.size > 1
  return list.map((item, index) => {
    const score = riskScoreMap[item.risk] ?? 0
    return {
      ...item,
      score,
      shortDate: formatTrendTick(item, hasMultipleDays),
    }
  })
})

const riskTrendSeries = computed(() =>
  trendPoints.value.map((item) => ({
    value: item.score,
    rawDate: item.date,
    created_at: item.created_at,
    finished_at: item.finished_at,
    risk: item.risk,
    summary: item.summary,
    shortDate: item.shortDate,
    isLatest: item.id === latestRecord.value?.id,
    itemStyle: {
      color: riskColorMap[item.risk] || riskColorMap['待评估'],
      borderColor: '#ffffff',
      borderWidth: item.id === latestRecord.value?.id ? 4 : 3,
      shadowBlur: item.id === latestRecord.value?.id ? 14 : 0,
      shadowColor: item.id === latestRecord.value?.id ? 'rgba(15, 118, 110, 0.2)' : 'transparent',
    },
  })),
)

const riskDistribution = computed(() => {
  const total = historyList.value.length || 1
  const buckets = ['高风险', '中风险', '低风险', '待评估'].map((label) => {
    const count = historyList.value.filter((item) => item.risk === label).length
    return {
      label,
      count,
      percent: total ? Math.round((count / total) * 100) : 0,
      color: riskColorMap[label],
    }
  })
  return buckets
})

function buildPieOption() {
  const legendItems = riskDistribution.value
  const data = riskDistribution.value
    .filter((item) => item.count > 0)
    .map((item) => ({
    name: item.label,
    value: item.count,
    itemStyle: { color: item.color },
    percent: item.percent,
    }))
  return {
    animationDuration: 900,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 620,
    animationEasingUpdate: 'quarticOut',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: 'rgba(15,118,110,0.12)',
      borderWidth: 1,
      textStyle: { color: '#163549' },
      transitionDuration: 0.18,
      extraCssText: 'box-shadow: 0 18px 36px rgba(15,35,52,0.14); border-radius: 16px; padding: 12px 14px;',
      formatter: (params) => {
        return [
          `<div style="font-weight:700;margin-bottom:4px;">${params.name}</div>`,
          `<div>占比：${params.percent}%</div>`,
          `<div>次数：${params.value} 次</div>`,
        ].join('')
      },
    },
    legend: {
      data: legendItems.map((item) => item.label),
      orient: 'vertical',
      right: '4%',
      top: 'middle',
      itemWidth: 12,
      itemHeight: 12,
      icon: 'circle',
      textStyle: {
        color: '#4d6479',
        fontSize: 15,
        fontWeight: 600,
      },
      formatter: (name) => {
        const target = riskDistribution.value.find((item) => item.label === name)
        if (!target) return name
        return `${name}   ${target.percent}%`
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['0%', '66%'],
        center: ['35%', '54%'],
        startAngle: 110,
        minAngle: 0,
        avoidLabelOverlap: true,
        selectedMode: false,
        animationType: 'expansion',
        animationDurationUpdate: 560,
        animationEasingUpdate: 'quarticOut',
        animationDelay: (index) => index * 85,
        label: {
          show: true,
          color: '#163549',
          fontSize: 14,
          fontWeight: 700,
          formatter: ({ percent, name, value }) => (value > 0 && percent >= 12 ? `${name}\n${percent}%` : ''),
          width: 84,
          overflow: 'break',
          lineHeight: 20,
        },
        labelLine: {
          show: true,
          length: 12,
          length2: 8,
          lineStyle: {
            color: 'rgba(22,53,73,0.22)',
            width: 1.2,
          },
          minTurnAngle: 120,
        },
        emphasis: {
          focus: 'self',
          scale: true,
          scaleSize: 12,
          itemStyle: {
            shadowBlur: 32,
            shadowColor: 'rgba(15,35,52,0.2)',
          },
        },
        itemStyle: {
          borderColor: 'rgba(255,255,255,0.96)',
          borderWidth: 3,
        },
        data,
      },
    ],
  }
}

function buildTrendOption() {
  const rows = riskTrendSeries.value
  return {
    animationDuration: 900,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 680,
    animationEasingUpdate: 'quarticOut',
    grid: {
      left: 58,
      right: 24,
      top: 24,
      bottom: 32,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: {
          color: 'rgba(15, 118, 110, 0.2)',
          type: 'dashed',
        },
      },
      backgroundColor: 'rgba(255,255,255,0.97)',
      borderColor: 'rgba(15,118,110,0.12)',
      borderWidth: 1,
      textStyle: { color: '#163549' },
      transitionDuration: 0.18,
      extraCssText: 'box-shadow: 0 18px 36px rgba(15,35,52,0.14); border-radius: 16px; padding: 12px 14px; max-width: 280px; white-space: normal;',
      formatter: (params) => {
        const point = params?.[0]?.data
        if (!point) return ''
        return [
          `<div style="font-weight:700;margin-bottom:4px;">${point.created_at || point.finished_at || point.rawDate}</div>`,
          `<div style="font-weight:700;color:${riskColorMap[point.risk] || '#64748b'};margin-bottom:6px;">${point.risk}</div>`,
          `<div style="color:#66788a;line-height:1.6;">${point.summary || '暂无概述'}</div>`,
        ].join('')
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((item) => item.shortDate),
      axisLine: {
        lineStyle: { color: 'rgba(15, 118, 110, 0.12)' },
      },
      axisTick: { show: false },
      axisLabel: {
        color: '#718399',
        fontSize: 12,
        fontWeight: 600,
        interval: rows.length > 7 ? Math.ceil(rows.length / 6) - 1 : 0,
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 3,
      interval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: {
        lineStyle: {
          color: 'rgba(15, 118, 110, 0.08)',
          type: 'dashed',
        },
      },
      axisLabel: {
        color: '#718399',
        fontSize: 12,
        fontWeight: 600,
        formatter: (value) => ['待评估', '低风险', '中风险', '高风险'][value] || '',
      },
    },
    series: [
      {
        type: 'line',
        smooth: 0.38,
        showAllSymbol: rows.length <= 12,
        symbol: 'circle',
        symbolSize: (value, params) => (params?.data?.isLatest ? 15 : 12),
        animationDelay: (index) => index * 90,
        animationDelayUpdate: (index) => index * 36,
        animationDurationUpdate: 620,
        lineStyle: {
          width: 4.5,
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#0f766e' },
            { offset: 1, color: '#22c55e' },
          ]),
          shadowBlur: 18,
          shadowColor: 'rgba(15, 118, 110, 0.16)',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(15, 118, 110, 0.24)' },
            { offset: 1, color: 'rgba(15, 118, 110, 0.02)' },
          ]),
        },
        emphasis: {
          focus: 'series',
          scale: true,
          itemStyle: {
            borderWidth: 5,
            shadowBlur: 24,
            shadowColor: 'rgba(15, 35, 52, 0.2)',
          },
        },
        data: rows,
      },
    ],
  }
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value, null, { renderer: 'svg' })
  }
  trendChart.setOption(buildTrendOption(), true)
}

function renderPieChart() {
  if (!pieChartRef.value) return
  if (!pieChart) {
    pieChart = echarts.init(pieChartRef.value, null, { renderer: 'svg' })
  }
  pieChart.setOption(buildPieOption(), true)
}

function handleResize() {
  trendChart?.resize()
  pieChart?.resize()
}

async function loadData() {
  loading.value = true
  try {
    const [patients, history] = await Promise.all([
      api.getPatients(),
      api.getPatientHistory(route.params.id),
    ])
    patient.value = patients.find((item) => item.id === route.params.id) || null
    historyList.value = history || []
  } finally {
    loading.value = false
  }
}

watch([riskDistribution, riskTrendSeries], async () => {
  await nextTick()
  renderTrendChart()
  renderPieChart()
}, { deep: true })

onMounted(async () => {
  await loadData()
  await nextTick()
  renderTrendChart()
  renderPieChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
  trendChart = null
  pieChart = null
})
</script>

<style scoped>
.patient-detail-page {
  display: grid;
  gap: 18px;
}
.detail-topbar {
  display: flex;
  justify-content: flex-start;
}
.back-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 18px;
  border-radius: 999px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  background: rgba(255, 255, 255, 0.78);
  color: #164e63;
  text-decoration: none;
}
.back-link.strong {
  margin-top: 10px;
}
.loading-shell,
.empty-shell {
  min-height: 280px;
  display: grid;
  place-items: center;
  text-align: center;
  border-radius: 28px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.78);
}
.loading-shell h3,
.loading-shell p,
.empty-shell h3,
.empty-shell p {
  margin: 0;
}
.loading-shell p,
.empty-shell p {
  color: #607286;
  margin-top: 8px;
}
.spinner-ring {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 3px solid rgba(15, 118, 110, 0.12);
  border-top-color: #0f766e;
  animation: spin 0.9s linear infinite;
  margin: 0 auto 14px;
}
.spinner-ring.large {
  width: 40px;
  height: 40px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.white-card {
  background: rgba(255, 255, 255, 0.86);
}
.patient-summary-layout {
  display: grid;
  grid-template-columns: 1.15fr 0.95fr;
  gap: 24px;
  align-items: center;
}
.mini-eyebrow {
  display: inline-block;
  font-size: 0.88rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #0f766e;
  margin-bottom: 8px;
}
.patient-identity h2,
.patient-identity p,
.patient-identity span {
  margin: 0;
}
.patient-identity h2 {
  font-size: clamp(1.8rem, 2.4vw, 2.3rem);
}
.patient-identity p {
  margin-top: 4px;
  color: #607286;
}
.patient-basic-row {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 16px;
  color: #607286;
}
.patient-highlight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.highlight-card {
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(15, 118, 110, 0.1);
}
.highlight-card.soft {
  background: linear-gradient(180deg, rgba(244, 250, 249, 0.92), rgba(239, 246, 255, 0.72));
}
.highlight-card span,
.highlight-card strong {
  display: block;
}
.highlight-card span {
  color: #66788a;
  margin-bottom: 10px;
}
.highlight-card strong {
  font-size: 1.45rem;
  color: #163549;
}
.detail-grid.two-up {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 22px;
}
.chart-panel {
  min-height: 420px;
}
.trend-stage {
  display: grid;
  gap: 18px;
}
.trend-head-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.meta-chip {
  padding: 12px 16px;
  border-radius: 18px;
  background: rgba(245, 250, 249, 0.9);
  border: 1px solid rgba(15, 118, 110, 0.1);
}
.meta-chip span,
.meta-chip strong {
  display: block;
}
.meta-chip span {
  color: #6b7c8d;
  margin-bottom: 6px;
}
.trend-chart-shell {
  position: relative;
  padding: 8px 10px 0;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(246, 251, 250, 0.96), rgba(240, 249, 255, 0.72));
  border: 1px solid rgba(15, 118, 110, 0.08);
}

.risk-trend-chart {
  width: 100%;
  height: 288px;
}
.distribution-head {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.distribution-stat-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(247, 251, 250, 0.96), rgba(240, 249, 255, 0.78));
  border: 1px solid rgba(15, 118, 110, 0.08);
}
.distribution-stat-card.subtle {
  background: linear-gradient(180deg, rgba(250, 252, 253, 0.96), rgba(244, 250, 249, 0.78));
}
.distribution-stat-card span {
  color: #6b7c8d;
}
.distribution-stat-card strong {
  font-size: 1.45rem;
  color: #163549;
}
.distribution-chart-shell {
  min-height: 340px;
  padding: 8px 0 0;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(246, 251, 250, 0.96), rgba(240, 249, 255, 0.72));
  border: 1px solid rgba(15, 118, 110, 0.08);
}
.risk-pie-chart {
  width: 100%;
  height: 340px;
}
.history-list-panel {
  display: grid;
  gap: 16px;
}
.history-list {
  display: grid;
  gap: 14px;
}
.history-item {
  display: grid;
  gap: 10px;
  padding: 18px 20px;
  border-radius: 24px;
  border: 1px solid rgba(15, 118, 110, 0.1);
  background: linear-gradient(180deg, rgba(250, 252, 253, 0.95), rgba(244, 250, 249, 0.82));
  text-decoration: none;
  color: inherit;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.history-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 30px rgba(15, 35, 52, 0.08);
}
.history-top {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}
.history-date,
.history-conclusion,
.history-summary {
  margin: 0;
}
.history-date {
  font-size: 1.05rem;
  color: #18374d;
}
.history-conclusion,
.history-summary {
  color: #66788a;
}
.history-conclusion {
  font-size: 1.02rem;
  line-height: 1.65;
}
.history-side {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  flex-shrink: 0;
}
.focus-tag {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
  font-weight: 700;
}
.risk-text.low { color: #0f766e; }
.risk-text.mid { color: #b45309; }
.risk-text.high { color: #be123c; }
.risk-text.neutral { color: #64748b; }
.risk-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 14px;
  border-radius: 999px;
  font-weight: 700;
  border: 1px solid transparent;
}
.risk-pill.low {
  background: rgba(15, 118, 110, 0.08);
  color: #0f766e;
  border-color: rgba(15, 118, 110, 0.14);
}
.risk-pill.mid {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  border-color: rgba(245, 158, 11, 0.2);
}
.risk-pill.high {
  background: rgba(244, 63, 94, 0.1);
  color: #be123c;
  border-color: rgba(244, 63, 94, 0.18);
}
.risk-pill.neutral {
  background: rgba(100, 116, 139, 0.1);
  color: #475569;
  border-color: rgba(100, 116, 139, 0.16);
}

@media (max-width: 1100px) {
  .patient-summary-layout,
  .detail-grid.two-up {
    grid-template-columns: 1fr;
  }
  .patient-highlight-grid {
    grid-template-columns: 1fr;
  }
  .distribution-head {
    grid-template-columns: 1fr;
  }
  .history-top {
    flex-direction: column;
  }
  .history-side {
    justify-content: flex-start;
  }
}
</style>
