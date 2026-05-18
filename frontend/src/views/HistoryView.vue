<template>
  <div class="page-view">
    <SectionTitle eyebrow="History Review" title="历史记录" />

    <Transition name="notice-slide">
      <div v-if="feedback.message" class="feedback-banner" :class="feedback.type">
        <div>
          <strong>{{ feedback.type === 'success' ? '操作成功' : '操作失败' }}</strong>
          <p>{{ feedback.message }}</p>
        </div>
        <button type="button" class="feedback-close" @click="clearFeedback">×</button>
      </div>
    </Transition>

    <section class="two-col history-main-grid">
      <GlassPanel class="fixed-panel">
        <SectionTitle title="历史诊断时间轴" />
        <div class="history-list scroll-area">
          <div
            v-for="item in historyRecords"
            :key="item.id"
            class="history-item"
            :class="{ active: item.id === selectedId }"
            @click="selectRecord(item.id)"
          >
            <div class="history-main">
              <span>{{ item.date }}</span>
              <strong>{{ item.title }}</strong>
              <div class="history-risk-line">
                <label>风险等级</label>
                <em :class="riskClass(item.risk)">{{ item.risk || '待评估' }}</em>
              </div>
            </div>
            <div class="history-actions" @click.stop>
              <RouterLink class="detail-btn" :to="`/history/${item.id}`">查看详情</RouterLink>
              <button type="button" class="delete-btn" @click="askRemoveHistory(item)">删除</button>
            </div>
          </div>
          <div v-if="!historyRecords.length" class="empty-state">
            <h3>暂无历史记录</h3>
            <p>完成诊断后，这里会显示可回看的历史结果。</p>
          </div>
        </div>
      </GlassPanel>

      <GlassPanel tone="deep" class="fixed-panel">
        <SectionTitle title="诊断概述" />
        <div v-if="selectedRecord" class="overview-panel scroll-area">
          <div class="overview-callout">
            <span class="overview-label">当前诊断</span>
            <h2>{{ selectedRecord.title }}</h2>
            <p>{{ normalizeMedicalText(selectedRecord.conclusion) }}</p>
          </div>

          <div class="overview-grid">
            <div class="overview-card">
              <span>诊断日期</span>
              <strong>{{ selectedRecord.date }}</strong>
            </div>
            <div class="overview-card">
              <span>诊断状态</span>
              <strong>{{ formatDiagnosisStatus(selectedRecord.status) }}</strong>
            </div>
            <div class="overview-card">
              <span>风险等级</span>
              <strong>{{ selectedRecord.risk }}</strong>
            </div>
            <div class="overview-card">
              <span>重点阶段</span>
              <strong>{{ formatFocusStage(selectedRecord.focusClass || selectedRecord.dominantStage) }}</strong>
            </div>
          </div>

          <div class="overview-note">
            <span>诊断建议</span>
            <p>{{ normalizeMedicalText(selectedRecord.advice) }}</p>
          </div>
        </div>
        <div v-else class="empty-overview">
          <h3>暂无可展示记录</h3>
          <p>左侧列表为空，或者当前记录已被删除。</p>
        </div>
      </GlassPanel>
    </section>

    <Teleport to="body">
      <Transition name="history-modal">
        <div v-if="showDeleteDialog" class="history-modal-overlay" @click.self="closeDeleteDialog">
          <div class="delete-dialog-card">
            <div class="delete-icon-wrap">
              <div class="delete-icon">!</div>
            </div>
            <h3>确认删除这条历史记录吗？</h3>
            <p>
              即将删除
              <strong>{{ historyPendingDelete?.title }}</strong>
              <span v-if="historyPendingDelete">（{{ historyPendingDelete.id }}）</span>
              ，对应诊断结果、规则激活和上传文件会一并移除。
            </p>
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
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import { api } from '@/api'

const historyRecords = ref([])
const selectedId = ref('')
const selectedRecord = ref(null)
const showDeleteDialog = ref(false)
const historyPendingDelete = ref(null)
const feedback = ref({ type: 'success', message: '' })
let feedbackTimer = null

const STAGE_LABEL_MAP = {
  W: 'W阶段',
  N1: 'N1阶段',
  N2: 'N2阶段',
  N3: 'N3阶段',
  R: 'REM阶段',
}

function formatDiagnosisStatus(status = '') {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'done') return '已完成'
  if (normalized === 'processing') return '进行中'
  if (normalized === 'queued') return '排队中'
  if (normalized === 'failed') return '失败'
  return status || '--'
}

function formatFocusStage(label = '') {
  return STAGE_LABEL_MAP[label] || label || '--'
}

function normalizeMedicalText(text = '') {
  return String(text || '')
    .replace(/\s+(?=(W阶段|N1阶段|N2阶段|N3阶段|REM阶段))/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function riskClass(risk = '') {
  if (risk === '高风险') return 'risk-high'
  if (risk === '中风险') return 'risk-medium'
  if (risk === '低风险') return 'risk-low'
  return 'risk-pending'
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

const selectRecord = async (id) => {
  selectedId.value = id
  try {
    selectedRecord.value = await api.getHistoryOverview(id)
  } catch (error) {
    console.error('加载历史概述失败:', error)
    showFeedback(error.message || '加载历史概述失败。', 'error')
  }
}

const askRemoveHistory = (item) => {
  historyPendingDelete.value = item
  showDeleteDialog.value = true
}

const closeDeleteDialog = () => {
  showDeleteDialog.value = false
  historyPendingDelete.value = null
}

const confirmRemoveHistory = async () => {
  if (!historyPendingDelete.value) return
  const removedId = historyPendingDelete.value.id
  try {
    await api.deleteHistory(removedId)
    historyRecords.value = historyRecords.value.filter((item) => item.id !== removedId)
    if (selectedId.value === removedId) {
      const next = historyRecords.value[0] || null
      if (next) {
        await selectRecord(next.id)
      } else {
        selectedId.value = ''
        selectedRecord.value = null
      }
    }
    closeDeleteDialog()
    showFeedback('历史记录已删除。')
  } catch (error) {
    showFeedback(error.message || '删除历史记录失败。', 'error')
  }
}

onMounted(async () => {
  try {
    historyRecords.value = await api.getHistoryList()
    if (historyRecords.value.length) {
      await selectRecord(historyRecords.value[0].id)
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
    showFeedback(error.message || '加载历史记录失败。', 'error')
  }
})

onBeforeUnmount(() => {
  if (feedbackTimer) clearTimeout(feedbackTimer)
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
.history-list,
.overview-grid {
  display: grid;
  gap: 24px;
}

.two-col {
  grid-template-columns: 1.1fr 0.95fr;
}

.history-main-grid {
  align-items: stretch;
}

.fixed-panel {
  height: min(72vh, 760px);
  display: flex;
  flex-direction: column;
}

.scroll-area {
  min-height: 0;
  overflow-y: auto;
  padding-right: 8px;
}

.scroll-area::-webkit-scrollbar {
  width: 8px;
}

.scroll-area::-webkit-scrollbar-track {
  background: transparent;
}

.scroll-area::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.18);
}

.history-list {
  margin-top: 18px;
  gap: 14px;
  align-content: start;
}

.history-item {
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(15, 118, 110, 0.12);
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  cursor: pointer;
  transition: 0.22s ease;
}

.history-main {
  flex: 1;
  min-width: 0;
}

.history-item.active {
  border-color: rgba(15, 118, 110, 0.24);
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.08), rgba(22, 78, 99, 0.04));
}

.history-item:hover {
  transform: translateY(-1px);
}

.history-main span,
.history-main strong {
  display: block;
  margin: 0;
}

.history-main span {
  color: #5c6d7e;
}

.history-main strong {
  margin: 6px 0 10px;
}

.history-risk-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.history-risk-line label {
  color: #6a7b8d;
  font-size: 0.94rem;
}

.history-risk-line em {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 78px;
  padding: 6px 14px;
  border-radius: 999px;
  font-style: normal;
  font-weight: 700;
  font-size: 0.96rem;
  border: 1px solid transparent;
}

.risk-high {
  color: #d91c5c;
  background: rgba(249, 168, 212, 0.16);
  border-color: rgba(244, 114, 182, 0.26);
}

.risk-medium {
  color: #c45b00;
  background: rgba(253, 230, 138, 0.18);
  border-color: rgba(251, 191, 36, 0.28);
}

.risk-low {
  color: #0f766e;
  background: rgba(153, 246, 228, 0.18);
  border-color: rgba(45, 212, 191, 0.22);
}

.risk-pending {
  color: #5c6d7e;
  background: rgba(226, 232, 240, 0.7);
  border-color: rgba(148, 163, 184, 0.24);
}

.history-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
}

.detail-btn,
.delete-btn,
.secondary-btn,
.danger-btn {
  padding: 10px 16px;
  border-radius: 999px;
  border: 0;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.detail-btn {
  color: #fff;
  background: linear-gradient(135deg, #0f766e, #164e63);
  min-width: 120px;
}

.delete-btn,
.danger-btn {
  color: #b42318;
  background: rgba(220, 38, 38, 0.1);
  min-width: 92px;
}

.secondary-btn {
  color: #164e63;
  background: rgba(15, 118, 110, 0.08);
}

.overview-panel {
  margin-top: 18px;
  display: grid;
  gap: 16px;
  align-content: start;
}

.overview-callout {
  padding: 22px 24px;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.overview-callout h2,
.overview-callout p {
  margin: 0;
}

.overview-callout h2 {
  margin-top: 10px;
  font-size: 1.92rem;
  line-height: 1.2;
}

.overview-callout p {
  margin-top: 12px;
  color: rgba(255, 255, 255, 0.74);
  line-height: 1.72;
}

.overview-label,
.overview-card span,
.overview-note span {
  color: rgba(255, 255, 255, 0.72);
}

.overview-grid {
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.overview-card {
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.overview-card span,
.overview-card strong {
  display: block;
}

.overview-card span {
  margin-bottom: 8px;
}

.overview-note {
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.overview-note p {
  margin: 10px 0 0;
  color: rgba(255, 255, 255, 0.76);
  line-height: 1.72;
}

.empty-state,
.empty-overview {
  margin-top: 18px;
  border-radius: 24px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px dashed rgba(15, 118, 110, 0.16);
}

.empty-state h3,
.empty-state p,
.empty-overview h3,
.empty-overview p {
  margin: 0;
}

.empty-state p,
.empty-overview p {
  margin-top: 10px;
  color: #5c6d7e;
  line-height: 1.7;
}

.empty-overview {
  color: rgba(255, 255, 255, 0.92);
  border-color: rgba(255, 255, 255, 0.18);
}

.empty-overview p {
  color: rgba(255, 255, 255, 0.7);
}

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

@media (max-width: 1180px) {
  .two-col,
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .fixed-panel {
    height: auto;
  }

  .scroll-area {
    overflow: visible;
    padding-right: 0;
  }

  .history-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>

