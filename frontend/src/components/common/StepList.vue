<template>
  <div class="step-list">
    <div v-for="step in steps" :key="step.title" class="step-item" :class="step.status">
      <div class="dot"></div>
      <div class="step-copy">
        <strong>{{ step.title }}</strong>
        <p>{{ statusMap[step.status] }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  steps: {
    type: Array,
    required: true,
  },
})

const statusMap = {
  done: '已完成',
  doing: '进行中',
  todo: '待执行',
}
</script>

<style scoped>
.step-list {
  display: grid;
  gap: 16px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 86px;
  padding: 14px 24px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(15, 118, 110, 0.12);
}

.step-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 56px;
}

.step-item strong,
.step-item p {
  margin: 0;
}

.step-item strong {
  line-height: 1.2;
}

.step-item p {
  margin-top: 4px;
  color: #5c6d7e;
  font-size: 0.85rem;
  line-height: 1.2;
}

.dot {
  position: relative;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #d7e4e0;
  flex: none;
}

.step-item.done .dot {
  background: #0f766e;
}

.step-item.doing .dot {
  background: #f59e0b;
  box-shadow: 0 0 0 8px rgba(245, 158, 11, 0.16);
}

.step-item.doing .dot::after {
  content: '';
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 2px solid rgba(245, 158, 11, 0.2);
  border-top-color: #f59e0b;
  animation: step-spin 0.9s linear infinite;
}

@keyframes step-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
