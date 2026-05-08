<template>
  <div class="page-view">
    <GlassPanel tone="hero">
      <div class="hero-grid">
        <div class="hero-copy">
          <div class="brand-ribbon">
            <span class="brand-dot"></span>
            <span class="brand-name">SomnoLight</span>
            <span class="brand-divider"></span>
            <span class="brand-desc">轻量可解释诊断工作台</span>
          </div>
          <div class="hero-title-wrap">
            <h1>多模态睡眠障碍病症轻量化辅助诊断系统</h1>
            <span class="title-glow"></span>
          </div>
          <p>支持多模态睡眠诊断、规则解释、模型管理与历史结果回看。</p>
          <div class="hero-actions">
            <RouterLink to="/analysis" class="hero-button primary">开始诊断</RouterLink>
            <RouterLink to="/rules" class="hero-button secondary">查看规则中心</RouterLink>
          </div>
        </div>
        <div class="wave-panel">
          <div class="wave-mesh"></div>
          <div class="signal-beam beam-one"></div>
          <div class="signal-beam beam-two"></div>
          <div class="metric-orbit">
            <div>
              <span>当前模型</span>
              <strong class="current-model-name">{{ currentModelName }}</strong>
            </div>
            <div>
              <span>模型亮点</span>
              <strong class="orbit-subtitle">{{ currentRuleHighlight }}</strong>
            </div>
            <div class="metric-tags">
              <span v-for="tag in currentModelTags" :key="tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>
    </GlassPanel>

    <section class="page-view">
      <SectionTitle
        eyebrow="System Snapshot"
        title="系统当前概况"
      />
      <div class="overview-grid">
          <GlassPanel
            v-for="(item, index) in systemOverview"
            :key="`${item.label}-${item.value}`"
            class="overview-card overview-card-animated"
            :style="{ '--overview-delay': `${index * 90}ms` }"
          >
          <div class="overview-icon" v-html="item.icon"></div>
          <div class="overview-copy">
            <span>{{ item.label }}</span>
            <strong>{{ displayOverviewValue(item) }}</strong>
          </div>
        </GlassPanel>
      </div>
    </section>

    <section class="two-col">
      <GlassPanel>
        <SectionTitle eyebrow="System Trend" title="诊断次数趋势" />
        <div class="trend-chart">
          <div class="trend-summary">
            <div>
              <span>近 7 日诊断总数</span>
              <strong>{{ trendTotal }}</strong>
            </div>
            <div>
              <span>峰值日期</span>
              <strong>{{ peakTrend.label }}</strong>
            </div>
          </div>

          <div
            class="trend-figure"
            @mouseleave="clearTrendHover"
          >
            <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#0f766e" />
                  <stop offset="100%" stop-color="#5ed2c6" />
                </linearGradient>
                <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stop-color="#5ed2c6" stop-opacity="0.28" />
                  <stop offset="100%" stop-color="#5ed2c6" stop-opacity="0.02" />
                </linearGradient>
                <linearGradient id="accentGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="rgba(15, 118, 110, 0.16)" />
                  <stop offset="100%" stop-color="rgba(94, 210, 198, 0)" />
                </linearGradient>
              </defs>
              <g class="trend-grid">
                <line
                  v-for="tick in yTicks"
                  :key="tick.value"
                  :x1="chartPadding.left"
                  :y1="tick.y"
                  :x2="chartWidth - chartPadding.right"
                  :y2="tick.y"
                />
                <text
                  v-for="tick in yTicks"
                  :key="`label-${tick.value}`"
                  :x="chartPadding.left - 12"
                  :y="tick.y + 4"
                  class="trend-y-label"
                >
                  {{ tick.value }}
                </text>
              </g>
              <rect
                v-for="zone in hoverZones"
                :key="zone.label"
                :x="zone.x"
                :y="chartPadding.top"
                :width="zone.width"
                :height="chartInnerHeight"
                class="hover-zone"
                @mouseenter="setTrendHover(zone.index)"
              />
              <rect
                v-if="activeTrendPoint"
                :x="activeTrendPoint.x - 34"
                :y="chartPadding.top"
                width="68"
                :height="chartInnerHeight"
                class="active-column"
              />
              <path :d="trendAreaPath" class="trend-area" />
              <path :d="trendSmoothPath" class="trend-line" />
              <line
                v-if="activeTrendPoint"
                :x1="activeTrendPoint.x"
                :x2="activeTrendPoint.x"
                :y1="chartPadding.top"
                :y2="chartHeight - chartPadding.bottom"
                class="trend-guide-line"
              />
              <g v-for="point in trendPoints" :key="point.label">
                <circle
                  :cx="point.x"
                  :cy="point.y"
                  :r="activeTrendPoint && activeTrendPoint.index === point.index ? 15 : 11"
                  class="trend-point-halo"
                  :class="{ active: activeTrendPoint && activeTrendPoint.index === point.index }"
                />
                <circle
                  :cx="point.x"
                  :cy="point.y"
                  :r="activeTrendPoint && activeTrendPoint.index === point.index ? 7.5 : 5.5"
                  class="trend-point"
                  :class="{ active: activeTrendPoint && activeTrendPoint.index === point.index }"
                />
                <text
                  :x="point.x"
                  :y="chartHeight - 20"
                  class="trend-x-label"
                >
                  {{ point.label }}
                </text>
              </g>
            </svg>
            <div
              v-if="activeTrendPoint"
              class="trend-tooltip"
              :style="{
                left: `${activeTooltipPosition.x}px`,
                top: `${activeTooltipPosition.y}px`,
              }"
            >
              <span>{{ activeTrendPoint.label }}</span>
              <strong>{{ activeTrendPoint.value }} 次诊断</strong>
            </div>
          </div>
        </div>
      </GlassPanel>
      <GlassPanel>
        <SectionTitle eyebrow="Recent Cases" title="近期分析记录" />
        <div class="recent-list">
          <RouterLink
            v-for="item in recentCases"
            :key="item.historyId"
            :to="`/history/${item.historyId}`"
            class="recent-item"
          >
            <div>
              <strong>{{ item.name }}</strong>
              <p>{{ item.summary }}</p>
            </div>
            <div class="recent-meta">
              <span>{{ item.date }}</span>
              <strong :class="riskClass(item.risk)">{{ item.risk }}</strong>
            </div>
          </RouterLink>
        </div>
      </GlassPanel>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import { api } from '@/api'

const iconMap = {
  patients: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 12a3.75 3.75 0 1 0 0-7.5A3.75 3.75 0 0 0 12 12Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M5 19.25c1.4-2.45 3.78-3.75 7-3.75s5.6 1.3 7 3.75" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    `,
  models: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="5" width="16" height="12" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/>
        <path d="M8 19h8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        <path d="M10 9h4M8.5 12h7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
      </svg>
    `,
  history: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 7v5l3 2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" stroke-width="1.8"/>
      </svg>
    `,
  risk: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3.8 19 6.9v5.1c0 4.2-2.7 7.2-7 8.9-4.3-1.7-7-4.7-7-8.9V6.9l7-3.1Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <path d="M12 8.2v4.7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        <circle cx="12" cy="16.2" r="1" fill="currentColor"/>
      </svg>
    `,
  signals: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3.5 12h3.2l1.7-3.1 2.4 6.2 2.1-4.1 1.7 2.6h5.9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M18.5 7.2a2.8 2.8 0 1 1 0 5.6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
      </svg>
    `,
}

const systemOverview = ref([])
const diagnosisTrend = ref([])
const recentCases = ref([])
const currentModelName = ref('BTD-TSK')
const currentRuleHighlight = ref('教师引导前件 + CE/KL蒸馏')
const currentModelTags = ref(['EEG+ECG', 'BiLSTM教师', '规则可解释'])
const activeTrendIndex = ref(null)
const animatedOverviewValues = ref({})
const overviewRafIds = new Set()
const overviewTimerIds = new Set()

const chartWidth = 640
const chartHeight = 320
const chartPadding = {
  top: 28,
  right: 24,
  bottom: 50,
  left: 48,
}

const defaultOverview = [
  {
    label: '患者总数',
    value: '0',
    note: '当前系统已建档患者数量',
    icon: iconMap.patients,
  },
  {
    label: '高风险患者数',
    value: '0',
    note: '按每位患者最新一次诊断结果统计高风险人数',
    icon: iconMap.risk,
  },
  {
    label: '模型数量',
    value: '0',
    note: '系统内可用于诊断的已存模型',
    icon: iconMap.models,
  },
  {
    label: '历史记录数',
    value: '0',
    note: '可回看的历史诊断记录',
    icon: iconMap.history,
  },
]

systemOverview.value = defaultOverview
diagnosisTrend.value = [
  { label: '03-24', value: 1 },
  { label: '03-25', value: 2 },
  { label: '03-26', value: 1 },
  { label: '03-27', value: 3 },
  { label: '03-28', value: 2 },
  { label: '03-29', value: 4 },
  { label: '03-30', value: 3 },
]

const trendBounds = computed(() => {
  const values = diagnosisTrend.value.map((item) => Number(item.value) || 0)
  if (!values.length) return { min: 0, max: 5 }
  let min = Math.min(...values)
  let max = Math.max(...values)
  if (max === min) {
    min = Math.max(0, min - 1)
    max = max + 1
  } else {
    const padding = Math.max(1, Math.ceil((max - min) * 0.2))
    min = Math.max(0, min - padding)
    max = max + padding
  }
  return { min, max }
})
const chartInnerWidth = chartWidth - chartPadding.left - chartPadding.right
const chartInnerHeight = chartHeight - chartPadding.top - chartPadding.bottom

const trendPoints = computed(() => {
  const startX = chartPadding.left
  const endX = chartWidth - chartPadding.right
  const baseY = chartHeight - chartPadding.bottom
  const topY = chartPadding.top
  const stepX = diagnosisTrend.value.length > 1 ? (endX - startX) / (diagnosisTrend.value.length - 1) : 0
  const range = Math.max(1, trendBounds.value.max - trendBounds.value.min)

  return diagnosisTrend.value.map((item, index) => {
    const ratio = (item.value - trendBounds.value.min) / range
    const y = baseY - ratio * (baseY - topY)
    return {
      ...item,
      index,
      x: startX + stepX * index,
      y,
    }
  })
})

function buildSmoothPath(points) {
  if (!points.length) return ''
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`
  let path = `M ${points[0].x} ${points[0].y}`
  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index]
    const next = points[index + 1]
    const previous = points[index - 1] || current
    const afterNext = points[index + 2] || next

    const cp1x = current.x + (next.x - previous.x) / 6
    const cp1y = current.y + (next.y - previous.y) / 6
    const cp2x = next.x - (afterNext.x - current.x) / 6
    const cp2y = next.y - (afterNext.y - current.y) / 6

    path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${next.x} ${next.y}`
  }
  return path
}

const trendSmoothPath = computed(() => buildSmoothPath(trendPoints.value))

const trendAreaPath = computed(() => {
  const points = trendPoints.value
  if (!points.length) return ''
  const first = points[0]
  const last = points[points.length - 1]
  const bottom = chartHeight - chartPadding.bottom
  return `${buildSmoothPath(points)} L ${last.x} ${bottom} L ${first.x} ${bottom} Z`
})

const trendTotal = computed(() => diagnosisTrend.value.reduce((sum, item) => sum + item.value, 0))

const peakTrend = computed(() =>
  diagnosisTrend.value.length
    ? diagnosisTrend.value.reduce((peak, item) => (item.value > peak.value ? item : peak), diagnosisTrend.value[0])
    : { label: '--', value: 0 }
)

function sanitizeModelName(name = '') {
  return String(name)
    .replace(/\bplus\b/gi, '')
    .replace(/\s*Data-\d+\b/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function riskClass(risk = '') {
  if (risk.includes('高')) return 'risk-high'
  if (risk.includes('中')) return 'risk-mid'
  if (risk.includes('低')) return 'risk-low'
  return ''
}

function buildModelProfile(model) {
  const source = `${model?.name || ''} ${model?.notes || ''} ${model?.type || ''}`.toLowerCase()
  const tags = []
  if (source.includes('eeg') || source.includes('ecg') || source.includes('multimodal')) tags.push('EEG+ECG')
  if (source.includes('bilstm') || source.includes('teacher')) tags.push('BiLSTM教师')
  if (source.includes('tsk') || source.includes('fuzzy')) tags.push('规则可解释')

  const unique = [...new Set(tags)]
  const highlight = source.includes('tsk')
    ? '教师引导前件 + CE/KL蒸馏'
    : '教师引导前件 + CE/KL蒸馏'

  const preferredOrder = ['EEG+ECG', 'BiLSTM教师', '规则可解释']
  const orderedTags = preferredOrder.filter((tag) => unique.includes(tag))

  return {
    highlight,
    tags: orderedTags.slice(0, 3).length ? orderedTags.slice(0, 3) : ['EEG+ECG', 'BiLSTM教师', '规则可解释'],
  }
}

const hoverZones = computed(() => {
  const points = trendPoints.value
  if (!points.length) return []
  return points.map((point, index) => {
    const previous = points[index - 1]
    const next = points[index + 1]
    const left = previous ? (previous.x + point.x) / 2 : chartPadding.left
    const right = next ? (point.x + next.x) / 2 : chartWidth - chartPadding.right
    return {
      ...point,
      x: left,
      width: Math.max(32, right - left),
    }
  })
})

const activeTrendPoint = computed(() => {
  if (!trendPoints.value.length) return null
  if (activeTrendIndex.value == null) return null
  return trendPoints.value[activeTrendIndex.value] || trendPoints.value[trendPoints.value.length - 1]
})

const activeTooltipPosition = computed(() => {
  if (!activeTrendPoint.value) return { x: 0, y: 0 }
  const tooltipWidth = 138
  const x = Math.min(
    chartWidth - chartPadding.right - tooltipWidth,
    Math.max(chartPadding.left, activeTrendPoint.value.x - tooltipWidth / 2),
  )
  const y = Math.max(chartPadding.top + 4, activeTrendPoint.value.y - 62)
  return { x, y }
})

const yTicks = computed(() => {
  const tickCount = 5
  const range = trendBounds.value.max - trendBounds.value.min
  return Array.from({ length: tickCount }, (_, index) => {
    const ratio = index / (tickCount - 1)
    const value = Math.round(trendBounds.value.max - ratio * range)
    const y = chartPadding.top + ratio * chartInnerHeight
    return { value, y }
  })
})

function setTrendHover(index) {
  activeTrendIndex.value = index
}

function clearTrendHover() {
  activeTrendIndex.value = null
}

function clearOverviewAnimations() {
  overviewTimerIds.forEach((timerId) => window.clearTimeout(timerId))
  overviewTimerIds.clear()
  overviewRafIds.forEach((rafId) => window.cancelAnimationFrame(rafId))
  overviewRafIds.clear()
}

function displayOverviewValue(item) {
  return animatedOverviewValues.value[item.label] ?? item.value
}

function animateOverviewValues(items) {
  clearOverviewAnimations()
  const nextValues = {}
  items.forEach((item, index) => {
    const rawValue = String(item.value ?? '').trim()
    const target = Number(rawValue)
    if (!Number.isFinite(target) || !/^-?\d+(\.\d+)?$/.test(rawValue)) {
      nextValues[item.label] = item.value
      return
    }

    nextValues[item.label] = '0'
    const timerId = window.setTimeout(() => {
      overviewTimerIds.delete(timerId)
      const duration = 720
      const startAt = performance.now()

      const tick = (timestamp) => {
        const progress = Math.min((timestamp - startAt) / duration, 1)
        const eased = 1 - Math.pow(1 - progress, 3)
        animatedOverviewValues.value = {
          ...animatedOverviewValues.value,
          [item.label]: String(Math.round(target * eased)),
        }

        if (progress < 1) {
          const rafId = window.requestAnimationFrame(tick)
          overviewRafIds.add(rafId)
          return
        }

        animatedOverviewValues.value = {
          ...animatedOverviewValues.value,
          [item.label]: item.value,
        }
      }

      const rafId = window.requestAnimationFrame((timestamp) => {
        overviewRafIds.delete(rafId)
        tick(timestamp)
      })
      overviewRafIds.add(rafId)
    }, index * 90)
    overviewTimerIds.add(timerId)
  })
  animatedOverviewValues.value = nextValues
}

watch(
  diagnosisTrend,
  (series) => {
    activeTrendIndex.value = null
  },
  { immediate: true },
)

watch(
  systemOverview,
  (items) => {
    animateOverviewValues(items)
  },
  { immediate: true },
)

onMounted(async () => {
  try {
    const [overview, trend, recentRuns, models] = await Promise.all([
      api.getHomeOverview(),
      api.getHomeTrend(7),
      api.getRecentRuns(4),
      api.getModels(),
    ])
    systemOverview.value = overview.map((item) => ({
      ...item,
      icon: iconMap[item.icon] || iconMap.signals,
    }))
    diagnosisTrend.value = trend.series.map((item) => ({
      label: item.label,
      value: Number(item.value),
    }))
    recentCases.value = recentRuns
    if (models.length) {
      currentModelName.value = sanitizeModelName(models[0].name)
      const profile = buildModelProfile(models[0])
      currentRuleHighlight.value = profile.highlight
      currentModelTags.value = profile.tags
    }
  } catch (error) {
    console.error('首页数据加载失败:', error)
    systemOverview.value = defaultOverview
    diagnosisTrend.value = [
      { label: '03-24', value: 1 },
      { label: '03-25', value: 2 },
      { label: '03-26', value: 1 },
      { label: '03-27', value: 3 },
      { label: '03-28', value: 2 },
      { label: '03-29', value: 4 },
      { label: '03-30', value: 3 },
    ]
    currentModelName.value = 'BTD-TSK'
    currentRuleHighlight.value = '教师引导前件 + CE/KL蒸馏'
    currentModelTags.value = ['EEG+ECG', 'BiLSTM教师', '规则可解释']
  }
})

onBeforeUnmount(() => {
  clearOverviewAnimations()
})
</script>

<style scoped>
.hero-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.95fr;
  gap: 26px;
  align-items: center;
}

.hero-copy {
  display: grid;
  gap: 20px;
  position: relative;
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(1.55rem, 2.55vw, 2.35rem);
  line-height: 1.08;
  letter-spacing: -0.02em;
  white-space: nowrap;
  text-wrap: nowrap;
}

.hero-copy p {
  margin: 0;
  max-width: 680px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.88);
}

.brand-ribbon {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  width: fit-content;
  max-width: 100%;
  padding: 10px 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.18);
  overflow: hidden;
  backdrop-filter: blur(10px);
}

.brand-ribbon::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, transparent 15%, rgba(255, 255, 255, 0.18) 35%, transparent 55%);
  transform: translateX(-120%);
  animation: ribbonShine 6s ease-in-out infinite;
}

.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #f7b955;
  box-shadow: 0 0 0 6px rgba(247, 185, 85, 0.16);
}

.brand-name {
  font-weight: 700;
  letter-spacing: 0.01em;
}

.brand-divider {
  width: 1px;
  height: 16px;
  background: rgba(255, 255, 255, 0.2);
}

.brand-desc {
  color: rgba(255, 255, 255, 0.82);
}

.hero-title-wrap {
  position: relative;
  width: fit-content;
  max-width: 100%;
}

.title-glow {
  position: absolute;
  left: 2%;
  right: 14%;
  bottom: -10px;
  height: 18px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.2), rgba(113, 255, 230, 0.18), rgba(255, 255, 255, 0));
  filter: blur(12px);
  pointer-events: none;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 14px 18px;
  border-radius: 999px;
}

.hero-button.primary {
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.hero-button.secondary {
  color: #fff;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.28);
}

.wave-panel {
  min-height: 320px;
  border-radius: 28px;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.9), rgba(22, 78, 99, 0.92));
  display: grid;
  place-items: center;
}

.wave-panel::before,
.wave-panel::after {
  content: '';
  position: absolute;
  inset: auto -10% 12% -10%;
  height: 120px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.18);
}

.wave-panel::after {
  inset: auto -5% 22% -5%;
  height: 80px;
  border-color: rgba(255, 255, 255, 0.28);
}

.wave-mesh {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 22% 24%, rgba(118, 255, 223, 0.18), transparent 28%),
    radial-gradient(circle at 78% 68%, rgba(255, 205, 122, 0.12), transparent 26%),
    linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: auto, auto, 28px 28px, 28px 28px;
  background-position: center, center, 0 0, 0 0;
  opacity: 0.42;
  mask-image: radial-gradient(circle at center, black 40%, transparent 100%);
  animation: meshDrift 16s linear infinite;
}

.signal-beam {
  position: absolute;
  width: 220px;
  height: 220px;
  border-radius: 999px;
  filter: blur(10px);
  opacity: 0.32;
  pointer-events: none;
}

.beam-one {
  top: 10%;
  right: 8%;
  background: radial-gradient(circle, rgba(96, 255, 224, 0.34), rgba(96, 255, 224, 0));
  animation: beaconFloat 9s ease-in-out infinite;
}

.beam-two {
  bottom: 6%;
  left: 10%;
  background: radial-gradient(circle, rgba(255, 214, 120, 0.18), rgba(255, 214, 120, 0));
  animation: beaconFloat 11s ease-in-out infinite reverse;
}

.metric-orbit {
  width: min(100%, 320px);
  min-height: 220px;
  padding: 26px;
  border-radius: 34px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.16);
  margin: 0 auto;
  display: grid;
  gap: 18px;
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(16px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 28px 44px rgba(5, 28, 40, 0.16);
}

.metric-orbit::before {
  content: '';
  position: absolute;
  inset: auto -12% -22% auto;
  width: 220px;
  height: 220px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0));
  pointer-events: none;
  animation: badgePulse 8s ease-in-out infinite;
}

.metric-orbit::after {
  content: '';
  position: absolute;
  inset: 18px;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  opacity: 0.85;
  pointer-events: none;
}

.metric-orbit span {
  color: rgba(255, 255, 255, 0.72);
  display: block;
}

.metric-orbit strong {
  display: block;
  margin-top: 6px;
  font-size: 20px;
  line-height: 1.35;
  position: relative;
  z-index: 1;
}

.current-model-name {
  position: relative;
  display: inline-block;
  margin-top: 10px;
  padding-bottom: 8px;
  color: #ffffff;
  background: transparent;
  border: 0;
  box-shadow: none;
  letter-spacing: 0.01em;
  font-size: 2rem;
  font-weight: 800;
  text-shadow: 0 8px 24px rgba(3, 25, 33, 0.18);
}

.current-model-name::before {
  content: '';
  position: absolute;
  left: 0;
  right: 32%;
  bottom: 0;
  height: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(136, 244, 228, 0.95), rgba(136, 244, 228, 0.16));
  box-shadow: 0 0 18px rgba(136, 244, 228, 0.24);
}

.current-model-name::after {
  content: '';
  position: absolute;
  inset: -8px -12px auto auto;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #8cf4e4;
  box-shadow:
    0 0 0 6px rgba(140, 244, 228, 0.1),
    0 0 16px rgba(140, 244, 228, 0.26);
  pointer-events: none;
  animation: modelMarkerPulse 4.8s ease-in-out infinite;
}

.orbit-subtitle {
  font-size: 1.12rem;
  color: rgba(255, 255, 255, 0.96);
}

.metric-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  position: relative;
  z-index: 1;
}

.metric-tags span {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.86);
  font-size: 0.86rem;
  line-height: 1;
  animation: chipFloat 6s ease-in-out infinite;
}

.metric-tags span:nth-child(2) {
  animation-delay: 0.9s;
}

.metric-tags span:nth-child(3) {
  animation-delay: 1.8s;
}

.two-col,
.overview-grid {
  display: grid;
  gap: 18px;
}

.two-col {
  grid-template-columns: 1.2fr 1fr;
}

.overview-grid {
  grid-template-columns: repeat(4, 1fr);
}

.overview-card {
  min-height: 148px;
  padding: 18px 20px !important;
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 14px;
  align-items: center;
  position: relative;
  overflow: hidden;
  transform-origin: center bottom;
  transition:
    transform 0.26s ease,
    box-shadow 0.26s ease,
    border-color 0.26s ease;
}

.overview-card-animated {
  opacity: 0;
  transform: translateY(18px) scale(0.985);
  animation: overview-card-in 0.72s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  animation-delay: var(--overview-delay, 0ms);
}

.overview-card::before {
  content: '';
  position: absolute;
  inset: -18% auto auto -12%;
  width: 42%;
  height: 78%;
  background: radial-gradient(circle, rgba(94, 210, 198, 0.18), rgba(94, 210, 198, 0));
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.28s ease;
}

.overview-card:hover {
  transform: translateY(-4px);
  border-color: rgba(15, 118, 110, 0.18);
  box-shadow: 0 18px 38px rgba(15, 35, 52, 0.08);
}

.overview-card:hover::before {
  opacity: 1;
}

.overview-icon {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  color: #0f766e;
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.14), rgba(22, 78, 99, 0.08));
  border: 1px solid rgba(15, 118, 110, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
  transition:
    transform 0.28s ease,
    box-shadow 0.28s ease,
    background 0.28s ease;
}

.overview-icon :deep(svg) {
  width: 28px;
  height: 28px;
}

.overview-card:hover .overview-icon {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.12);
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.18), rgba(22, 78, 99, 0.1));
}

.overview-copy span,
.overview-copy strong,
.overview-copy p {
  display: block;
  margin: 0;
}

.overview-copy span {
  color: #5c6d7e;
  margin-bottom: 6px;
  line-height: 1.2;
}

.overview-copy strong {
  font-size: 1.75rem;
  line-height: 1.1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.overview-copy p {
  margin-top: 10px;
  color: #5c6d7e;
  line-height: 1.6;
}

.trend-chart {
  margin-top: 18px;
  display: grid;
  gap: 18px;
}

@keyframes overview-card-in {
  0% {
    opacity: 0;
    transform: translateY(18px) scale(0.985);
  }

  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.trend-summary {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

.trend-summary > div {
  min-width: 180px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(15, 118, 110, 0.12);
}

.trend-summary span,
.trend-summary strong {
  display: block;
}

.trend-summary span {
  color: #5c6d7e;
  margin-bottom: 8px;
}

.trend-figure {
  position: relative;
  min-height: 340px;
  padding: 18px 18px 12px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(243, 250, 249, 0.96));
  border: 1px solid rgba(15, 118, 110, 0.12);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.56),
    0 20px 50px rgba(15, 35, 52, 0.05);
}

.trend-figure svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

.trend-grid line {
  stroke: rgba(15, 118, 110, 0.1);
  stroke-width: 1;
  stroke-dasharray: 5 8;
}

.trend-y-label,
.trend-x-label {
  fill: #74879b;
  font-size: 12px;
  font-weight: 600;
}

.trend-y-label {
  text-anchor: end;
}

.trend-x-label {
  text-anchor: middle;
}

.hover-zone {
  fill: transparent;
  cursor: pointer;
}

.active-column {
  fill: url(#accentGradient);
  rx: 26;
}

.trend-area {
  fill: url(#areaGradient);
}

.trend-line {
  fill: none;
  stroke: url(#lineGradient);
  stroke-width: 4.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 10px 14px rgba(15, 118, 110, 0.18));
  animation: drawTrend 1.1s ease;
}

.trend-guide-line {
  stroke: rgba(15, 118, 110, 0.18);
  stroke-width: 2;
  stroke-dasharray: 4 6;
}

.trend-point {
  fill: #fff;
  stroke: #0f766e;
  stroke-width: 3;
  transition: 0.2s ease;
}

.trend-point.active {
  fill: #0f766e;
  stroke: #fff;
  stroke-width: 3.5;
}

.trend-point-halo {
  fill: rgba(94, 210, 198, 0.12);
  transition: 0.2s ease;
}

.trend-point-halo.active {
  fill: rgba(94, 210, 198, 0.22);
}

.trend-tooltip {
  position: absolute;
  pointer-events: none;
  min-width: 128px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(14, 91, 86, 0.92);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow: 0 18px 32px rgba(10, 62, 73, 0.22);
  backdrop-filter: blur(12px);
}

.trend-tooltip span,
.trend-tooltip strong {
  display: block;
}

.trend-tooltip span {
  color: rgba(255, 255, 255, 0.74);
  font-size: 0.78rem;
  margin-bottom: 4px;
}

.trend-tooltip strong {
  font-size: 1rem;
  font-weight: 700;
}

.recent-list {
  margin-top: 18px;
  display: grid;
  gap: 14px;
}

.recent-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.12);
  text-decoration: none;
  transition: 0.22s ease;
}

.recent-item > div:first-child {
  min-width: 0;
  flex: 1 1 auto;
  display: grid;
  align-content: center;
}

.recent-item:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.22);
  box-shadow: 0 14px 32px rgba(15, 35, 52, 0.08);
}

.recent-item p,
.recent-item strong {
  margin: 0;
}

.recent-item p {
  margin-top: 6px;
  color: #5c6d7e;
  line-height: 1.6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  flex: 0 0 auto;
  text-align: right;
}

.recent-meta span,
.recent-meta strong {
  display: block;
}

.recent-meta span {
  color: #5c6d7e;
  white-space: nowrap;
}

.recent-meta strong {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 82px;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 0.95rem;
  border: 1px solid transparent;
}

.recent-meta strong.risk-low {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.1);
  border-color: rgba(15, 118, 110, 0.16);
}

.recent-meta strong.risk-mid {
  color: #b45309;
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.18);
}

.recent-meta strong.risk-high {
  color: #be123c;
  background: rgba(244, 63, 94, 0.1);
  border-color: rgba(244, 63, 94, 0.16);
}

@keyframes ribbonShine {
  0%,
  100% {
    transform: translateX(-120%);
  }
  45%,
  60% {
    transform: translateX(120%);
  }
}

@keyframes beaconFloat {
  0%,
  100% {
    transform: translateY(0px) scale(1);
  }
  50% {
    transform: translateY(12px) scale(1.06);
  }
}

@keyframes drawTrend {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes badgePulse {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.42;
  }
  50% {
    transform: translate(-10px, -10px) scale(1.06);
    opacity: 0.72;
  }
}

@keyframes meshDrift {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(10px, -8px, 0);
  }
}

@keyframes chipFloat {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

@keyframes modelMarkerPulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.9;
  }
  50% {
    transform: scale(1.18);
    opacity: 0.55;
  }
}

@media (max-width: 1180px) {
  .hero-grid,
  .two-col,
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .hero-copy h1 {
    white-space: normal;
    text-wrap: balance;
  }

  .trend-axis {
    grid-template-columns: 1fr;
  }
}
</style>
