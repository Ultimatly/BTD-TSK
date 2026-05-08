<template>
  <div class="rule-card-root" :class="{ compact }">
    <GlassPanel class="rule-card" :class="{ compact }">
      <div class="rule-header">
        <div>
          <h3>规则 #{{ rule.id }}</h3>
        </div>
        <div class="target"><span>{{ rule.target }}</span></div>
      </div>

      <div v-if="showActivation" class="activation-block">
        <span class="meta-label">平均激活度</span>
        <strong>{{ rule.strength.toFixed(3) }}</strong>
        <div class="bar-track">
          <div class="bar-fill" :style="activationFillStyle"></div>
        </div>
      </div>

      <p class="description">{{ rule.description }}</p>

      <div class="rule-tags">
        <span v-for="tag in rule.tags" :key="tag">{{ tag }}</span>
      </div>

      <div class="rule-footer">
        <button type="button" class="rule-btn" @click="openDetail">查看规则详情</button>
      </div>
    </GlassPanel>

    <Teleport to="body">
      <Transition name="rule-modal">
        <div v-if="showModal" class="rule-modal-overlay" @click.self="closeDetail">
          <div class="rule-modal-card">
            <div class="rule-modal-head">
              <div>
                <p class="eyebrow">规则完整说明</p>
                <h2>{{ rule.detailTitle || `规则 #${rule.id} 的语言解释` }}</h2>
              </div>
              <button type="button" class="modal-close" @click="closeDetail">×</button>
            </div>

            <div class="rule-meta-grid">
              <div class="meta-tile">
                <span>规则类型</span>
                <strong>{{ rule.type }}</strong>
              </div>
              <div class="meta-tile">
                <span>目标类别</span>
                <strong>{{ rule.target }}</strong>
              </div>
              <div v-if="showActivation" class="meta-tile">
                <span>平均激活度</span>
                <strong>{{ rule.strength.toFixed(3) }}</strong>
              </div>
            </div>

            <div class="detail-panel">
              <h3>如果</h3>
              <ul class="antecedent-list">
                <li v-for="item in rule.antecedents || []" :key="`${rule.id}-${item.feature}`">
                  <div class="antecedent-main">
                    <strong>{{ item.label }}</strong>
                    <span>为 {{ item.level }}</span>
                  </div>
                  <div class="antecedent-params">
                    <span>a={{ formatNumber(item.a) }}</span>
                    <span>sigma={{ formatNumber(item.sigma) }}</span>
                  </div>
                </li>
              </ul>
            </div>

            <div class="detail-panel consequence-panel">
              <h3>那么</h3>
              <p>输出倾向于 {{ rule.consequence?.label || rule.target }}（后件权重 P={{ formatNumber(rule.consequence?.p) }}）</p>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import GlassPanel from '@/components/common/GlassPanel.vue'

const props = defineProps({
  rule: { type: Object, required: true },
  detailed: { type: Boolean, default: false },
  showActivation: { type: Boolean, default: true },
  compact: { type: Boolean, default: false },
})

const showModal = ref(false)

const openDetail = () => {
  showModal.value = true
}

const closeDetail = () => {
  showModal.value = false
}

const formatNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(4) : '--'
}

const clamp01 = (value) => Math.min(1, Math.max(0, Number(value) || 0))

const activationFillStyle = computed(() => {
  const strength = clamp01(props.rule?.strength)
  const saturation = 0.88 + strength * 0.28
  const brightness = 0.92 + strength * 0.14
  const glow = 0.12 + strength * 0.16
  return {
    width: `${strength * 100}%`,
    background: 'linear-gradient(90deg, #0f766e 0%, #1f958d 48%, #5ecdbf 72%, #f59e0b 100%)',
    filter: `saturate(${saturation}) brightness(${brightness})`,
    boxShadow: `0 0 14px rgba(15, 118, 110, ${glow})`,
  }
})
</script>

<style scoped>
.rule-card-root {
  display: block;
  height: 100%;
  min-height: 360px;
}

.rule-card-root.compact {
  min-height: 292px;
}

.rule-card {
  display: grid;
  grid-template-rows: auto auto minmax(72px, auto) auto auto;
  gap: 16px;
  height: 100%;
  min-height: 360px;
}

.rule-card.compact {
  grid-template-rows: auto auto minmax(54px, auto) auto auto;
  gap: 12px;
  min-height: 292px;
}

.rule-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.rule-header h3,
.rule-header p {
  margin: 0;
}

.eyebrow {
  color: #0f766e;
  font-size: 0.82rem;
}

.target {
  min-width: 52px;
  height: 52px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  background: linear-gradient(135deg, #0f766e, #164e63);
  flex: 0 0 auto;
  align-self: flex-start;
  text-align: center;
}

.rule-card.compact .target {
  min-width: 46px;
  height: 46px;
  border-radius: 16px;
}

.target span {
  display: block;
  color: #fff;
  font-size: 1rem;
  line-height: 1;
  transform: translateY(-1px);
}

.activation-block {
  display: grid;
  gap: 8px;
}

.rule-card.compact .activation-block {
  gap: 6px;
}

.meta-label {
  display: block;
  color: #5c6d7e;
}

.bar-track {
  height: 12px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.1);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #0f766e, #f59e0b);
}

.description {
  margin: 0;
  line-height: 1.7;
}

.rule-card.compact .description {
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.rule-tags {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: flex-start;
  align-content: flex-start;
}

.rule-card.compact .rule-tags {
  gap: 8px;
}

.rule-tags span {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
  color: #164e63;
  font-size: 0.85rem;
}

.rule-card.compact .rule-tags span {
  padding: 6px 10px;
  font-size: 0.8rem;
}

.rule-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
}

.rule-btn {
  padding: 10px 14px;
  border-radius: 14px;
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, #164e63, #0f766e);
}

.rule-card.compact .rule-btn {
  padding: 8px 12px;
  border-radius: 12px;
}

.rule-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(12, 24, 34, 0.28);
  backdrop-filter: blur(14px);
}

.rule-modal-card {
  width: min(980px, calc(100vw - 48px));
  max-height: calc(100vh - 56px);
  overflow: auto;
  padding: 28px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(15, 118, 110, 0.14);
  box-shadow: 0 32px 90px rgba(15, 35, 52, 0.24);
}

.rule-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.rule-modal-head h2,
.rule-modal-head p {
  margin: 0;
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

.rule-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 22px 0;
}

.meta-tile {
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 118, 110, 0.05);
  border: 1px solid rgba(15, 118, 110, 0.1);
}

.meta-tile span,
.meta-tile strong {
  display: block;
}

.meta-tile span {
  color: #5c6d7e;
  margin-bottom: 8px;
}

.detail-panel {
  padding: 20px 22px;
  border-radius: 24px;
  background: rgba(244, 248, 247, 0.92);
  border: 1px solid rgba(15, 118, 110, 0.1);
}

.detail-panel + .detail-panel {
  margin-top: 18px;
}

.detail-panel h3,
.detail-panel p {
  margin: 0;
}

.antecedent-list {
  list-style: none;
  padding: 0;
  margin: 16px 0 0;
  display: grid;
  gap: 12px;
}

.antecedent-list li {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 18px;
  background: #fff;
  border: 1px solid rgba(15, 118, 110, 0.08);
}

.antecedent-main,
.antecedent-params {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.antecedent-main span,
.antecedent-params span {
  color: #5c6d7e;
}

.consequence-panel p {
  margin-top: 14px;
  font-size: 1.05rem;
  line-height: 1.75;
}

.rule-modal-enter-active,
.rule-modal-leave-active {
  transition: opacity 0.28s ease;
}

.rule-modal-enter-active .rule-modal-card,
.rule-modal-leave-active .rule-modal-card {
  transition: transform 0.28s ease, opacity 0.28s ease;
}

.rule-modal-enter-from,
.rule-modal-leave-to {
  opacity: 0;
}

.rule-modal-enter-from .rule-modal-card,
.rule-modal-leave-to .rule-modal-card {
  opacity: 0;
  transform: scale(0.92) translateY(18px);
}

@media (max-width: 900px) {
  .rule-meta-grid {
    grid-template-columns: 1fr 1fr;
  }

  .antecedent-list li {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 640px) {
  .rule-modal-overlay {
    padding: 16px;
  }

  .rule-modal-card {
    width: calc(100vw - 24px);
    padding: 22px 18px;
  }

  .rule-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>


