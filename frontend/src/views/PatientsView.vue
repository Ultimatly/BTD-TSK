<template>
  <div class="page-view">
    <SectionTitle eyebrow="Patient Profiles" title="患者管理" />

    <Transition name="notice-slide">
      <div v-if="feedback.message" class="feedback-banner" :class="feedback.type">
        <div>
          <strong>{{ feedback.type === 'success' ? '操作成功' : '操作失败' }}</strong>
          <p>{{ feedback.message }}</p>
        </div>
        <button type="button" class="feedback-close" @click="clearFeedback">×</button>
      </div>
    </Transition>

    <GlassPanel>
      <div class="filter-bar">
        <input v-model="keyword" placeholder="搜索患者姓名或编号" />
        <select v-model="genderFilter">
          <option value="全部性别">全部性别</option>
          <option value="男">男</option>
          <option value="女">女</option>
        </select>
        <select v-model="statusFilter">
          <option value="全部状态">全部状态</option>
          <option value="已分析">已分析</option>
          <option value="待分析">待分析</option>
        </select>
        <select v-model="sortMode">
          <option value="按最新记录排序">按最新记录排序</option>
          <option value="按风险排序">按风险排序</option>
          <option value="按编号排序">按编号排序</option>
        </select>
        <button class="action-button primary add-btn" @click="openPatientForm()">新增患者</button>
      </div>
    </GlassPanel>

    <section class="patient-grid">
      <GlassPanel
        v-for="patient in filteredPatients"
        :key="patient.id"
        class="patient-card"
        @click="openPatientDetail(patient)"
      >
        <div class="patient-top">
          <div class="identity-block">
            <h3>{{ patient.name }}</h3>
            <p>{{ patient.id }}</p>
          </div>
          <span class="risk-pill" :class="riskClass(patient.risk)">{{ patient.risk }}</span>
        </div>

        <div class="patient-meta">
          <span>{{ patient.gender }} · {{ patient.age }} 岁</span>
        </div>

        <div class="patient-actions" @click.stop>
          <button class="mini-btn" @click="openPatientForm(patient)">编辑</button>
          <button class="mini-btn danger" @click="askRemovePatient(patient)">删除</button>
          <RouterLink class="start-btn" :to="`/analysis?patient=${patient.id}`">开始诊断</RouterLink>
        </div>
      </GlassPanel>
    </section>

    <Teleport to="body">
      <Transition name="patient-modal">
        <div v-if="showFormDialog" class="patient-modal-overlay" @click.self="closePatientForm">
          <div class="patient-modal-card form-card light-card">
            <div class="patient-modal-head dark-head">
              <div>
                <p class="modal-eyebrow dark-eyebrow">患者档案编辑</p>
                <h2>{{ editingPatientId ? '编辑患者信息' : '新增患者' }}</h2>
              </div>
              <button type="button" class="modal-close dark-close" @click="closePatientForm">×</button>
            </div>

            <div class="patient-form-grid slim-grid compact-grid">
              <label class="form-field">
                <span>患者姓名</span>
                <input v-model="patientForm.name" placeholder="请输入患者姓名" />
              </label>
              <label class="form-field">
                <span>性别</span>
                <select v-model="patientForm.gender">
                  <option value="男">男</option>
                  <option value="女">女</option>
                </select>
              </label>
              <label class="form-field full-row">
                <span>年龄</span>
                <input v-model.number="patientForm.age" type="number" min="1" max="120" />
              </label>
            </div>

            <div class="form-tip">
              <span>编号将自动生成，新建患者默认状态为“待分析”，风险等级为“待评估”。</span>
            </div>

            <div class="form-actions">
              <button class="action-button secondary" @click="closePatientForm">取消</button>
              <button class="action-button primary" @click="submitPatientForm">保存</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="patient-modal">
        <div v-if="showDeleteDialog" class="patient-modal-overlay" @click.self="closeDeleteDialog">
          <div class="delete-dialog-card">
            <div class="delete-icon-wrap">
              <div class="delete-icon">!</div>
            </div>
            <h3>确认删除这位患者吗？</h3>
            <p>
              即将删除
              <strong>{{ patientPendingDelete?.name }}</strong>
              <span v-if="patientPendingDelete">（{{ patientPendingDelete.id }}）</span>
              ，并同时删除该患者全部历史记录。
            </p>
            <div class="form-actions delete-actions">
              <button class="action-button secondary" @click="closeDeleteDialog">取消</button>
              <button class="action-button danger" @click="confirmRemovePatient">确认删除</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import { api } from '@/api'

const router = useRouter()
const showFormDialog = ref(false)
const showDeleteDialog = ref(false)
const patients = ref([])
const editingPatientId = ref('')
const patientPendingDelete = ref(null)
const keyword = ref('')
const genderFilter = ref('全部性别')
const statusFilter = ref('全部状态')
const sortMode = ref('按最新记录排序')
const patientForm = ref(createEmptyPatientForm())
const feedback = ref({ type: 'success', message: '' })
let feedbackTimer = null

const riskOrder = { 高风险: 3, 中风险: 2, 低风险: 1, 待评估: 0 }

function createEmptyPatientForm() {
  return {
    name: '',
    gender: '男',
    age: 30,
  }
}

function riskClass(risk = '') {
  if (String(risk).includes('高')) return 'high'
  if (String(risk).includes('中')) return 'mid'
  if (String(risk).includes('低')) return 'low'
  return 'neutral'
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

const filteredPatients = computed(() => {
  let list = [...patients.value]
  if (keyword.value.trim()) {
    const q = keyword.value.trim()
    list = list.filter((item) => item.name.includes(q) || item.id.includes(q))
  }
  if (genderFilter.value !== '全部性别') {
    list = list.filter((item) => item.gender === genderFilter.value)
  }
  if (statusFilter.value !== '全部状态') {
    list = list.filter((item) => item.status === statusFilter.value)
  }
  if (sortMode.value === '按风险排序') {
    list.sort((a, b) => (riskOrder[b.risk] || 0) - (riskOrder[a.risk] || 0))
  } else if (sortMode.value === '按编号排序') {
    list.sort((a, b) => a.id.localeCompare(b.id))
  } else {
    list.sort((a, b) => String(b.latestRunAt || b.createdAt || '').localeCompare(String(a.latestRunAt || a.createdAt || '')))
  }
  return list
})

async function loadPatients() {
  try {
    patients.value = await api.getPatients()
  } catch (error) {
    console.error('加载患者列表失败:', error)
    showFeedback(error.message || '加载患者列表失败。', 'error')
  }
}

function openPatientDetail(patient) {
  router.push(`/patients/${patient.id}`)
}

function openPatientForm(patient = null) {
  if (patient) {
    editingPatientId.value = patient.id
    patientForm.value = {
      name: patient.name,
      gender: patient.gender,
      age: patient.age,
    }
  } else {
    editingPatientId.value = ''
    patientForm.value = createEmptyPatientForm()
  }
  showFormDialog.value = true
}

function closePatientForm() {
  showFormDialog.value = false
}

async function submitPatientForm() {
  try {
    const payload = {
      name: patientForm.value.name,
      gender: patientForm.value.gender,
      age: patientForm.value.age,
    }
    if (editingPatientId.value) {
      await api.updatePatient(editingPatientId.value, payload)
      showFeedback('患者信息已更新。')
    } else {
      await api.createPatient(payload)
      showFeedback('患者档案已创建。')
    }
    closePatientForm()
    await loadPatients()
  } catch (error) {
    showFeedback(error.message || '保存患者信息失败。', 'error')
  }
}

function askRemovePatient(patient) {
  patientPendingDelete.value = patient
  showDeleteDialog.value = true
}

function closeDeleteDialog() {
  showDeleteDialog.value = false
  patientPendingDelete.value = null
}

async function confirmRemovePatient() {
  if (!patientPendingDelete.value) return
  try {
    await api.deletePatient(patientPendingDelete.value.id)
    showFeedback('患者档案已删除。')
    closeDeleteDialog()
    await loadPatients()
  } catch (error) {
    showFeedback(error.message || '删除患者失败。', 'error')
  }
}

onMounted(loadPatients)

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
.patient-modal-enter-active,
.patient-modal-leave-active {
  transition: all 0.22s ease;
}
.notice-slide-enter-from,
.notice-slide-leave-to,
.patient-modal-enter-from,
.patient-modal-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.patient-grid,
.filter-bar,
.patient-form-grid {
  display: grid;
  gap: 20px;
}
.patient-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.filter-bar {
  grid-template-columns: 2fr 1fr 1fr 1fr auto;
  align-items: center;
}
.filter-bar input,
.filter-bar select,
.form-field input,
.form-field select {
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.8);
}
.add-btn {
  white-space: nowrap;
}

.patient-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  cursor: pointer;
  transition: 0.22s ease;
  min-height: 228px;
}
.patient-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 32px rgba(15, 35, 52, 0.08);
}
.patient-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.identity-block h3,
.identity-block p {
  margin: 0;
}
.identity-block h3 {
  font-size: 1.18rem;
}
.identity-block p,
.patient-meta span,
.latest-run-text {
  color: #617286;
}
.patient-meta {
  display: grid;
  gap: 8px;
}
.risk-pill,
.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 14px;
  border-radius: 999px;
  font-weight: 700;
  border: 1px solid transparent;
  white-space: nowrap;
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
.patient-actions {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  align-items: center;
}
.mini-btn,
.start-btn {
  padding: 10px 18px;
  border-radius: 999px;
  border: 0;
  font-size: 1rem;
  text-decoration: none;
}
.mini-btn {
  background: rgba(15, 118, 110, 0.08);
  color: #155e75;
}
.mini-btn.danger {
  background: rgba(244, 63, 94, 0.12);
  color: #dc2626;
}
.start-btn {
  background: linear-gradient(135deg, #0f766e, #155e75);
  color: white;
}

.patient-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.36);
  backdrop-filter: blur(12px);
  display: grid;
  place-items: center;
  padding: 24px;
  z-index: 1400;
}
.patient-modal-card,
.delete-dialog-card {
  width: min(980px, calc(100vw - 40px));
  border-radius: 32px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.2);
}
.patient-modal-card {
  padding: 34px 36px 32px;
}
.patient-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 24px;
}
.patient-modal-head h2,
.modal-eyebrow {
  margin: 0;
}
.modal-eyebrow {
  color: #5c6d7e;
  margin-bottom: 6px;
}
.modal-close {
  width: 46px;
  height: 46px;
  border-radius: 16px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(240, 249, 255, 0.9);
  font-size: 1.65rem;
  color: #1f3c52;
}
.compact-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.form-field {
  display: grid;
  gap: 10px;
}
.form-field span {
  color: #5c6d7e;
  font-weight: 600;
}
.full-row {
  grid-column: 1 / -1;
}
.form-tip {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(15, 118, 110, 0.06);
  color: #486175;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 22px;
}
.action-button {
  padding: 12px 24px;
  border-radius: 999px;
  border: 0;
}
.action-button.primary {
  background: linear-gradient(135deg, #0f766e, #155e75);
  color: white;
}
.action-button.secondary {
  background: rgba(15, 118, 110, 0.08);
  color: #155e75;
}
.action-button.danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: white;
}
.delete-dialog-card {
  max-width: 440px;
  padding: 30px;
  text-align: center;
}
.delete-icon-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 14px;
}
.delete-icon {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(244, 63, 94, 0.12);
  color: #dc2626;
  font-size: 1.45rem;
  font-weight: 700;
}
.delete-dialog-card h3,
.delete-dialog-card p {
  margin: 0;
}
.delete-dialog-card p {
  margin-top: 10px;
  color: #5c6d7e;
  line-height: 1.7;
}
.delete-actions {
  justify-content: center;
}

@media (max-width: 1360px) {
  .patient-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .patient-grid,
  .filter-bar,
  .compact-grid {
    grid-template-columns: 1fr;
  }
  .patient-card {
    min-height: auto;
  }
  .patient-actions,
  .form-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
