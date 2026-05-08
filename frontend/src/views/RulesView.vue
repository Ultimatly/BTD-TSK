<template>
  <div class="page-view">
    <SectionTitle
      eyebrow="Explainability Hub"
      title="规则中心"
    />

    <GlassPanel>
      <SectionTitle title="规则筛选区" />
      <div class="filter-bar">
        <div class="filter-group">
          <label>选择模型</label>
          <select v-model="selectedModelId">
            <option v-for="model in storedModels" :key="model.id" :value="model.id">
              {{ model.name }} · {{ model.status }}
            </option>
          </select>
        </div>
        <div class="filter-group">
          <label>目标类别</label>
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
          <label>搜索规则</label>
          <input v-model="keyword" placeholder="输入规则编号或关键词" />
        </div>
        <div class="filter-group">
          <label>排序方式</label>
          <select v-model="sortMode">
            <option>按规则编号</option>
            <option>按层级</option>
            <option>按目标类别</option>
          </select>
        </div>
      </div>
    </GlassPanel>

    <GlassPanel>
      <SectionTitle title="BTD-TSK 规则卡片展示区" />
      <div v-if="filteredRuleCards.length" class="rule-grid">
        <RuleCard v-for="rule in filteredRuleCards" :key="rule.id" :rule="rule" detailed :show-activation="false" />
      </div>
      <div v-else class="empty-state">
        <div class="empty-icon">R</div>
        <h3>当前模型暂无规则卡片</h3>
        <p>{{ selectedModelName }} 当前没有可展示的规则信息。</p>
      </div>
    </GlassPanel>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import GlassPanel from '@/components/common/GlassPanel.vue'
import SectionTitle from '@/components/common/SectionTitle.vue'
import RuleCard from '@/components/rules/RuleCard.vue'
import { api, mapRule } from '@/api'

function normalizeModelStatus(status = '') {
  return status === '当前启用' ? '主模型' : status
}

function normalizeModelName(name = '') {
  return String(name).replace(/BTD_TSK/g, 'BTD-TSK')
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

function isBtdModel(model) {
  const name = String(model?.name || '')
  const id = String(model?.id || '')
  return (
    name.includes('BTD-TSK') ||
    name.includes('BTD_TSK') ||
    id.includes('btd_tsk_student') ||
    id.includes('uploaded-btd-tsk')
  )
}

const storedModels = ref([])
const allRules = ref([])
const selectedModelId = ref('')
const targetFilter = ref('全部类别')
const keyword = ref('')
const sortMode = ref('按规则编号')

const selectedModelName = computed(() => {
  const model = storedModels.value.find((item) => item.id === selectedModelId.value)
  return model ? model.name : '当前模型'
})

const filteredRuleCards = computed(() => {
  let list = allRules.value.filter((rule) => rule.modelId === selectedModelId.value)
  if (targetFilter.value !== '全部类别') {
    list = list.filter((rule) => rule.target === targetFilter.value)
  }
  if (keyword.value.trim()) {
    const q = keyword.value.trim()
    list = list.filter((rule) => String(rule.id).includes(q) || rule.description.includes(q) || rule.tags.some((tag) => tag.includes(q)))
  }
  if (sortMode.value === '按层级') {
    list.sort((a, b) => a.id - b.id)
  } else if (sortMode.value === '按目标类别') {
    list.sort((a, b) => a.target.localeCompare(b.target, 'zh-CN'))
  } else {
    list.sort((a, b) => a.id - b.id)
  }
  return list
})

async function loadRules() {
  if (!selectedModelId.value) return
  try {
    const rules = await api.getRules(selectedModelId.value)
    allRules.value = rules.map(mapRule)
  } catch (error) {
    console.error('加载规则失败:', error)
    allRules.value = []
  }
}

watch(selectedModelId, loadRules)

onMounted(async () => {
  try {
    storedModels.value = sortModels(
      (await api.getModels())
        .map((model) => ({
          ...model,
          name: normalizeModelName(model.name),
          status: normalizeModelStatus(model.status),
        }))
        .filter(isBtdModel),
    )
    selectedModelId.value = storedModels.value[0]?.id || ''
    await loadRules()
  } catch (error) {
    console.error('加载模型失败:', error)
  }
})
</script>

<style scoped>
.rule-grid,
.filter-bar {
  display: grid;
  gap: 24px;
}

.rule-grid {
  grid-template-columns: repeat(3, 1fr);
  align-items: stretch;
  grid-auto-rows: 360px;
}

.rule-grid > * {
  height: 100%;
}

.filter-bar {
  grid-template-columns: repeat(4, 1fr);
  margin-top: 18px;
}

.filter-group {
  display: grid;
  gap: 8px;
}

.filter-group label {
  font-size: 0.85rem;
  color: #5c6d7e;
}

.filter-group input,
.filter-group select {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.76);
}

.empty-state {
  margin-top: 18px;
  min-height: 260px;
  border-radius: 28px;
  display: grid;
  place-items: center;
  text-align: center;
  padding: 28px 32px;
  gap: 12px;
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.06), rgba(22, 78, 99, 0.02)), rgba(255, 255, 255, 0.78);
  border: 1px dashed rgba(15, 118, 110, 0.18);
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: grid;
  place-items: center;
  font-size: 1.5rem;
  letter-spacing: 0.08em;
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
}

.empty-state h3,
.empty-state p {
  margin: 0;
}

.empty-state h3 {
  font-size: 1.28rem;
}

.empty-state p {
  max-width: 42ch;
  line-height: 1.72;
  color: #5c6d7e;
}

@media (max-width: 1180px) {
  .rule-grid,
  .filter-bar {
    grid-template-columns: 1fr;
  }
}
</style>
