<template>
  <div class="page-view">
    <SectionTitle
      eyebrow="Model Storage"
      title="模型管理"
    />

    <Teleport to="body">
      <Transition name="notice-slide">
        <div v-if="feedback.message" class="feedback-banner" :class="feedback.type">
          <div>
            <strong>{{ feedback.type === 'success' ? '操作成功' : '操作失败' }}</strong>
            <p>{{ feedback.message }}</p>
          </div>
          <button type="button" class="feedback-close" @click="clearFeedback">×</button>
        </div>
      </Transition>
    </Teleport>

    <section class="two-col">
      <GlassPanel>
        <SectionTitle title="已存储模型" />
        <div v-if="storedModels.length" class="model-list">
          <div
            v-for="model in storedModels"
            :key="model.id"
            class="model-card"
            :class="{ primary: isPrimaryModel(model) }"
          >
            <div class="model-head">
              <div class="model-heading">
                <p class="model-version">{{ model.version }}</p>
                <h3>{{ model.name }}</h3>
              </div>
              <span class="model-status">{{ model.status }}</span>
            </div>
            <div class="model-meta">
              <div class="meta-item">
                <span>模型类型</span>
                <strong>{{ model.type }}</strong>
              </div>
              <div class="meta-item">
                <span>更新时间</span>
                <strong>{{ model.updatedAt }}</strong>
              </div>
            </div>
            <p class="model-note">{{ model.notes || '暂无模型说明。' }}</p>
            <div class="model-actions">
              <button class="action-button secondary" @click="openModelInfo(model)">查看模型信息</button>
              <button class="action-button secondary soft-accent" @click="startEditModel(model)">编辑模型</button>
              <button class="action-button danger" @click="removeModel(model)">删除模型</button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <strong>当前还没有已注册模型</strong>
          <p>右侧填写模型信息并上传文件后，这里会自动出现新的模型卡片。</p>
        </div>
      </GlassPanel>

      <div class="side-panel-sticky">
        <GlassPanel>
          <SectionTitle title="上传新模型" />
          <div class="upload-panel">
            <div class="upload-dropzone" @click="fileInputRef?.click()">
              <span>拖拽或点击上传模型文件</span>
              <strong>{{ selectedFile ? selectedFile.name : '支持 .pkl / .joblib 模型文件' }}</strong>
              <small>先选文件，再补全模型信息。</small>
              <input ref="fileInputRef" class="hidden-file" type="file" accept=".joblib,.pkl" @change="handleFileChange" />
            </div>

            <div class="form-grid">
              <label class="form-field">
                <span>模型名称</span>
                <input v-model="uploadForm.name" type="text" />
              </label>
              <label class="form-field">
                <span>模型版本</span>
                <input v-model="uploadForm.version" type="text" />
              </label>
              <label class="form-field">
                <span>模型状态</span>
                <select v-model="uploadForm.status">
                  <option>主模型</option>
                  <option>备用模型</option>
                  <option>测试模型</option>
                </select>
              </label>
              <label class="form-field full">
                <span>模型类型</span>
                <input v-model="uploadForm.modelType" type="text" />
              </label>
              <label class="form-field full">
                <span>模型说明</span>
                <textarea v-model="uploadForm.notes" rows="4"></textarea>
              </label>
            </div>

            <div class="hero-actions">
              <button class="action-button primary" :disabled="isUploading" @click="submitUpload">
                <span v-if="isUploading" class="button-spinner" aria-hidden="true"></span>
                <span>{{ isUploading ? '上传中...' : '上传模型' }}</span>
              </button>
              <button class="action-button secondary" :disabled="isUploading" @click="fileInputRef?.click()">
                选择文件
              </button>
            </div>
          </div>
        </GlassPanel>
      </div>
    </section>

    <Teleport to="body">
      <Transition name="model-modal">
        <div v-if="showModelDialog" class="model-modal-overlay" @click.self="closeModelInfo">
          <div class="model-modal-card">
            <div class="model-modal-head">
              <div>
                <p class="modal-eyebrow">模型信息</p>
                <h2>{{ selectedModel.name }}</h2>
              </div>
              <button type="button" class="modal-close" @click="closeModelInfo">×</button>
            </div>

            <div class="modal-version-row">
              <span class="version-pill">{{ selectedModel.version }}</span>
              <span class="status-pill">{{ selectedModel.status }}</span>
            </div>

            <div class="modal-meta-grid">
              <div class="modal-meta-card">
                <span>模型类型</span>
                <strong>{{ selectedModel.type }}</strong>
              </div>
              <div class="modal-meta-card">
                <span>更新时间</span>
                <strong>{{ selectedModel.updatedAt }}</strong>
              </div>
              <div class="modal-meta-card">
                <span>模型编号</span>
                <strong>{{ selectedModel.id }}</strong>
              </div>
              <div class="modal-meta-card">
                <span>输入维度</span>
                <strong>{{ selectedModel.inputDim ?? '--' }}</strong>
              </div>
            </div>

            <div class="modal-note-card">
              <span>模型说明</span>
              <p>{{ selectedModel.notes }}</p>
            </div>

            <div class="modal-info-grid">
              <div class="modal-info-card">
                <span>支持类别数</span>
                <strong>{{ selectedModel.classCount ?? '--' }}</strong>
              </div>
              <div class="modal-info-card">
                <span>上传格式</span>
                <strong>{{ (selectedModel.uploadFormats || []).join(' / ') || '.joblib / .pkl' }}</strong>
              </div>
            </div>

            <div class="modal-actions">
              <button class="action-button secondary" @click="startEditModel(selectedModel); closeModelInfo()">编辑模型</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="model-modal">
        <div v-if="showEditDialog" class="model-modal-overlay" @click.self="closeEditDialog">
          <div class="model-modal-card edit-modal-card">
            <div class="model-modal-head">
              <div>
                <p class="modal-eyebrow">编辑模型</p>
                <h2>{{ editForm.name || editingModelCode || '模型信息编辑' }}</h2>
              </div>
              <button type="button" class="modal-close" @click="closeEditDialog">×</button>
            </div>

            <div class="form-grid modal-form-grid">
              <label class="form-field">
                <span>模型名称</span>
                <input v-model="editForm.name" type="text" />
              </label>
              <label class="form-field">
                <span>模型版本</span>
                <input v-model="editForm.version" type="text" />
              </label>
              <label class="form-field">
                <span>模型状态</span>
                <select v-model="editForm.status">
                  <option>主模型</option>
                  <option>备用模型</option>
                  <option>测试模型</option>
                </select>
              </label>
              <label class="form-field full">
                <span>模型类型</span>
                <input v-model="editForm.modelType" type="text" />
              </label>
              <label class="form-field full">
                <span>模型说明</span>
                <textarea v-model="editForm.notes" rows="5"></textarea>
              </label>
              <div class="form-field full edit-file-panel">
                <span>更新模型文件（可选）</span>
                <div class="edit-file-row">
                  <button type="button" class="action-button secondary" :disabled="isUpdatingModel" @click="editFileInputRef?.click()">
                    选择新文件
                  </button>
                  <span class="edit-file-name">{{ selectedEditFile ? selectedEditFile.name : '未选择新文件，默认仅更新模型信息。' }}</span>
                </div>
                <input
                  ref="editFileInputRef"
                  class="hidden-file"
                  type="file"
                  accept=".joblib,.pkl"
                  @change="handleEditFileChange"
                />
              </div>
            </div>

            <div class="hero-actions modal-actions">
              <button class="action-button primary" :disabled="isUpdatingModel" @click="submitEditModel">
                <span v-if="isUpdatingModel" class="button-spinner" aria-hidden="true"></span>
                <span>{{ isUpdatingModel ? '保存中...' : '保存修改' }}</span>
              </button>
              <button class="action-button secondary" :disabled="isUpdatingModel" @click="closeEditDialog">取消</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="model-modal">
        <div v-if="showDeleteDialog" class="model-modal-overlay" @click.self="closeDeleteDialog">
          <div class="delete-dialog-card">
            <div class="delete-icon-wrap">
              <div class="delete-icon">!</div>
            </div>
            <h3>确认删除这套模型吗？</h3>
            <p>
              即将删除
              <strong>{{ modelPendingDelete?.name }}</strong>
              <span v-if="modelPendingDelete">（{{ modelPendingDelete.id }}）</span>
              ，删除后将不能继续在诊断页中调用。
            </p>
            <div class="hero-actions delete-actions">
              <button class="action-button secondary" @click="closeDeleteDialog">取消</button>
              <button class="action-button danger" @click="confirmRemoveModel">确认删除</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import { api } from '@/api'

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

function createEmptyForm() {
  return {
    name: '',
    version: '',
    status: '测试模型',
    modelType: '',
    notes: '',
  }
}

const showModelDialog = ref(false)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const storedModels = ref([])
const selectedModel = ref({})
const modelPendingDelete = ref(null)
const fileInputRef = ref(null)
const editFileInputRef = ref(null)
const selectedFile = ref(null)
const selectedEditFile = ref(null)
const isUploading = ref(false)
const isUpdatingModel = ref(false)
const feedback = ref({ type: 'success', message: '' })
const editingModelCode = ref('')
const uploadForm = ref(createEmptyForm())
const editForm = ref(createEmptyForm())
let feedbackTimer = null

function isPrimaryModel(model) {
  return normalizeModelStatus(model?.status) === '主模型'
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

function syncModelIntoForm(model) {
  return {
    name: model?.name || '',
    version: model?.version || '',
    status: normalizeModelStatus(model?.status || '测试模型'),
    modelType: model?.type || model?.modelType || '',
    notes: model?.notes || '',
  }
}

function resetFileInput() {
  selectedFile.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function resetEditFileInput() {
  selectedEditFile.value = null
  if (editFileInputRef.value) editFileInputRef.value.value = ''
}

function resetForm() {
  uploadForm.value = createEmptyForm()
  resetFileInput()
}

function buildPayload(sourceForm) {
  const payload = {
    name: sourceForm.name.trim(),
    version: sourceForm.version.trim(),
    status: sourceForm.status.trim(),
    modelType: sourceForm.modelType.trim(),
    notes: sourceForm.notes.trim(),
  }
  if (!payload.name) {
    showFeedback('请填写模型名称。', 'error')
    return null
  }
  if (!payload.version) {
    showFeedback('请填写模型版本。', 'error')
    return null
  }
  if (!payload.status) {
    showFeedback('请填写模型状态。', 'error')
    return null
  }
  if (!payload.modelType) {
    showFeedback('请填写模型类型。', 'error')
    return null
  }
  if (!payload.notes) {
    showFeedback('请填写模型说明。', 'error')
    return null
  }
  return payload
}

async function loadModels() {
  try {
    storedModels.value = sortModels(
      (await api.getModels()).map((model) => ({
        ...model,
        status: normalizeModelStatus(model.status),
      })),
    )
    if (!selectedModel.value?.id && storedModels.value.length) {
      selectedModel.value = storedModels.value[0]
    }
  } catch (error) {
    console.error('加载模型列表失败:', error)
  }
}

async function refreshSelectedModelIfNeeded(modelCode) {
  if (selectedModel.value?.id !== modelCode) return
  try {
    const detail = await api.getModelDetail(modelCode)
    selectedModel.value = { ...detail, status: normalizeModelStatus(detail.status) }
  } catch (error) {
    console.error('刷新模型详情失败:', error)
  }
}

const openModelInfo = async (model) => {
  try {
    const detail = await api.getModelDetail(model.id)
    selectedModel.value = { ...detail, status: normalizeModelStatus(detail.status) }
    showModelDialog.value = true
  } catch (error) {
    console.error('加载模型详情失败:', error)
  }
}

const closeModelInfo = () => {
  showModelDialog.value = false
}

const startEditModel = async (model) => {
  try {
    const detail = model.inputDim ? model : await api.getModelDetail(model.id)
    editingModelCode.value = detail.id
    editForm.value = syncModelIntoForm(detail)
    resetEditFileInput()
    showEditDialog.value = true
  } catch (error) {
    showFeedback(error.message || '加载模型信息失败。', 'error')
  }
}

const closeEditDialog = () => {
  showEditDialog.value = false
  editingModelCode.value = ''
  editForm.value = createEmptyForm()
  resetEditFileInput()
}

const handleFileChange = (event) => {
  selectedFile.value = event.target.files?.[0] || null
  if (selectedFile.value && !uploadForm.value.name.trim()) {
    uploadForm.value.name = selectedFile.value.name.replace(/\.(joblib|pkl)$/i, '')
  }
}

const handleEditFileChange = (event) => {
  selectedEditFile.value = event.target.files?.[0] || null
}

const submitUpload = async () => {
  if (isUploading.value) return
  const payload = buildPayload(uploadForm.value)
  if (!payload) return
  if (!selectedFile.value) {
    showFeedback('请先选择模型文件。', 'error')
    return
  }

  try {
    isUploading.value = true
    await api.uploadModel({
      name: payload.name,
      version: payload.version,
      status: payload.status,
      modelType: payload.modelType,
      notes: payload.notes,
      file: selectedFile.value,
    })
    showFeedback('模型文件已上传并写入模型库。')
    await loadModels()
    resetForm()
  } catch (error) {
    showFeedback(error.message || '上传模型失败。', 'error')
  } finally {
    isUploading.value = false
  }
}

const submitEditModel = async () => {
  if (isUpdatingModel.value) return
  const payload = buildPayload(editForm.value)
  if (!payload) return

  try {
    isUpdatingModel.value = true
    await api.updateModel(editingModelCode.value, {
      name: payload.name,
      version: payload.version,
      status: payload.status,
      model_type: payload.modelType,
      notes: payload.notes,
      file: selectedEditFile.value,
    })
    showFeedback(selectedEditFile.value ? '模型信息和模型文件都已更新。' : '模型信息已更新。')
    await loadModels()
    await refreshSelectedModelIfNeeded(editingModelCode.value)
    closeEditDialog()
  } catch (error) {
    showFeedback(error.message || '更新模型失败。', 'error')
  } finally {
    isUpdatingModel.value = false
  }
}

const removeModel = (model) => {
  modelPendingDelete.value = model
  showDeleteDialog.value = true
}

const closeDeleteDialog = () => {
  showDeleteDialog.value = false
  modelPendingDelete.value = null
}

const confirmRemoveModel = async () => {
  if (!modelPendingDelete.value) return
  try {
    await api.deleteModel(modelPendingDelete.value.id)
    if (selectedModel.value?.id === modelPendingDelete.value.id) {
      showModelDialog.value = false
      selectedModel.value = {}
    }
    if (editingModelCode.value === modelPendingDelete.value.id) {
      closeEditDialog()
    }
    showFeedback('模型已删除。')
    closeDeleteDialog()
    await loadModels()
  } catch (error) {
    showFeedback(error.message || '删除模型失败', 'error')
  }
}

onMounted(loadModels)

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
.notice-slide-leave-active {
  transition: all 0.22s ease;
}

.notice-slide-enter-from,
.notice-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.two-col {
  display: grid;
  grid-template-columns: minmax(0, 1.28fr) minmax(340px, 0.92fr);
  gap: 24px;
  align-items: start;
}

.side-panel-sticky {
  position: sticky;
  top: 126px;
}

.model-list {
  margin-top: 18px;
  display: grid;
  gap: 18px;
}

.model-card {
  padding: 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(15, 118, 110, 0.12);
  display: grid;
  gap: 16px;
}

.model-card.primary {
  background:
    linear-gradient(180deg, rgba(15, 118, 110, 0.08), rgba(34, 211, 238, 0.03)),
    rgba(255, 255, 255, 0.9);
  border-color: rgba(15, 118, 110, 0.26);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.72),
    0 18px 38px rgba(15, 118, 110, 0.12);
}

.model-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.model-heading,
.model-head h3,
.model-head p,
.model-note {
  margin: 0;
}

.model-heading {
  min-width: 0;
}

.model-heading h3 {
  margin-top: 4px;
}

.model-version {
  color: #0f766e;
  font-size: 0.86rem;
}

.model-status {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.1);
  color: #164e63;
}

.model-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.meta-item,
.info-item,
.panel-intro,
.edit-lock-card {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(15, 118, 110, 0.1);
}

.meta-item span,
.meta-item strong,
.info-item span,
.info-item strong,
.panel-intro span,
.panel-intro strong,
.edit-lock-card span,
.edit-lock-card strong {
  display: block;
}

.meta-item span,
.info-item span,
.panel-intro span,
.edit-lock-card span {
  color: #5c6d7e;
  margin-bottom: 8px;
}

.panel-intro strong,
.edit-lock-card strong {
  color: #163042;
}

.panel-intro p,
.edit-lock-card p {
  margin: 8px 0 0;
  color: #5c6d7e;
  line-height: 1.65;
}

.model-note {
  color: #5c6d7e;
  line-height: 1.75;
}

.model-actions,
.hero-actions,
.modal-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.upload-panel {
  margin-top: 18px;
  display: grid;
  gap: 14px;
}

.upload-dropzone {
  min-height: 152px;
  padding: 22px;
  border-radius: 24px;
  display: grid;
  place-items: center;
  text-align: center;
  border: 2px dashed rgba(15, 118, 110, 0.24);
  background:
    linear-gradient(180deg, rgba(8, 145, 178, 0.05), rgba(5, 150, 105, 0.03)),
    rgba(255, 255, 255, 0.88);
  cursor: pointer;
}

.hidden-file {
  display: none;
}

.upload-dropzone span,
.upload-dropzone strong,
.upload-dropzone small {
  display: block;
}

.upload-dropzone span,
.upload-dropzone small {
  color: #5c6d7e;
}

.upload-dropzone strong {
  margin: 10px 0 8px;
  color: #164e63;
}

.form-grid {
  grid-template-columns: 1fr 1fr;
  display: grid;
  gap: 14px;
}

.form-field {
  display: grid;
  gap: 8px;
}

.form-field.full {
  grid-column: 1 / -1;
}

.form-field span {
  color: #5c6d7e;
}

.form-field input,
.form-field textarea,
.form-field select {
  width: 100%;
  padding: 13px 14px;
  border-radius: 16px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  background: rgba(255, 255, 255, 0.92);
  color: #163042;
  font: inherit;
  resize: vertical;
}

.info-strip {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.empty-state {
  margin-top: 18px;
  padding: 28px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px dashed rgba(15, 118, 110, 0.18);
  color: #5c6d7e;
}

.empty-state strong,
.empty-state p {
  margin: 0;
  display: block;
}

.empty-state p {
  margin-top: 8px;
  line-height: 1.7;
}

.action-button {
  padding: 12px 18px;
  border-radius: 999px;
  border: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.action-button.primary {
  color: #fff;
  background: linear-gradient(135deg, #0f766e, #164e63);
}

.action-button.secondary {
  background: rgba(15, 118, 110, 0.08);
  color: #164e63;
}

.action-button.secondary.soft-accent {
  background: rgba(8, 145, 178, 0.1);
  color: #0f5f75;
}

.action-button.danger {
  color: #9f1239;
  background: rgba(244, 63, 94, 0.1);
  border: 1px solid rgba(244, 63, 94, 0.16);
}

.action-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.button-spinner {
  width: 16px;
  height: 16px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #ffffff;
  animation: button-spin 0.8s linear infinite;
}

.form-field input:focus,
.form-field textarea:focus,
.form-field select:focus,
.action-button:focus,
.modal-close:focus,
.feedback-close:focus {
  outline: 3px solid rgba(34, 211, 238, 0.18);
  outline-offset: 2px;
}

@keyframes button-spin {
  to {
    transform: rotate(360deg);
  }
}

.model-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(12, 24, 34, 0.28);
  backdrop-filter: blur(14px);
}

.model-modal-card,
.delete-dialog-card {
  width: min(920px, calc(100vw - 48px));
  max-height: calc(100vh - 56px);
  overflow: auto;
  padding: 28px;
  border-radius: 32px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  box-shadow: 0 32px 90px rgba(15, 35, 52, 0.24);
}

.model-modal-card {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 250, 250, 0.98));
  color: #163042;
}

.delete-dialog-card {
  width: min(520px, calc(100vw - 48px));
  text-align: center;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 250, 250, 0.98));
  border: 1px solid rgba(15, 118, 110, 0.12);
  color: #163042;
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
  justify-content: center;
  margin-top: 20px;
}

.model-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.model-modal-head h2,
.model-modal-head p {
  margin: 0;
}

.modal-eyebrow {
  color: #5c6d7e;
  font-size: 0.85rem;
}

.modal-close {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(15, 118, 110, 0.06);
  color: #164e63;
  font-size: 1.5rem;
  line-height: 1;
}

.modal-version-row {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.version-pill,
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 9px 14px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  border: 1px solid rgba(15, 118, 110, 0.12);
  color: #164e63;
}

.modal-meta-grid,
.modal-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 20px;
}

.modal-meta-card,
.modal-info-card {
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(15, 118, 110, 0.1);
}

.modal-meta-card span,
.modal-meta-card strong,
.modal-info-card span,
.modal-info-card strong {
  display: block;
}

.modal-meta-card span,
.modal-info-card span {
  color: #5c6d7e;
  margin-bottom: 10px;
}

.modal-note-card {
  margin-top: 20px;
  padding: 20px 22px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(15, 118, 110, 0.1);
}

.modal-note-card span {
  color: #5c6d7e;
}

.modal-note-card p {
  margin: 10px 0 0;
  line-height: 1.78;
  color: #486174;
}

.modal-actions {
  margin-top: 20px;
}

.modal-form-grid {
  margin-top: 20px;
}

.edit-file-panel {
  gap: 10px;
}

.edit-file-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.edit-file-name {
  color: #5c6d7e;
  line-height: 1.6;
  word-break: break-all;
}

.model-modal-enter-active,
.model-modal-leave-active {
  transition: opacity 0.28s ease;
}

.model-modal-enter-active .model-modal-card,
.model-modal-leave-active .model-modal-card {
  transition: transform 0.28s ease, opacity 0.28s ease;
}

.model-modal-enter-from,
.model-modal-leave-to {
  opacity: 0;
}

.model-modal-enter-from .model-modal-card,
.model-modal-leave-to .model-modal-card {
  opacity: 0;
  transform: scale(0.92) translateY(18px);
}

@media (max-width: 1180px) {
  .two-col,
  .model-meta,
  .form-grid,
  .info-strip {
    grid-template-columns: 1fr;
  }

  .modal-meta-grid,
  .modal-info-grid {
    grid-template-columns: 1fr;
  }

  .side-panel-sticky {
    position: static;
  }
}
</style>

