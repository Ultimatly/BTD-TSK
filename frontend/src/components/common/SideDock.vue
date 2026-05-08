<template>
  <aside class="side-dock">
    <RouterLink v-for="item in items" :key="item.path" :to="item.path" class="dock-link">
      <span class="icon" aria-hidden="true">
        <svg v-if="item.key === 'home'" viewBox="0 0 24 24" fill="none">
          <path d="M4 10.5L12 4l8 6.5" />
          <path d="M6.5 9.5V19h11V9.5" />
        </svg>
        <svg v-else-if="item.key === 'patient'" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="8.5" r="3.2" />
          <path d="M6.8 18.2c1.2-2.6 3-3.9 5.2-3.9s4 1.3 5.2 3.9" />
        </svg>
        <svg v-else-if="item.key === 'analysis'" viewBox="0 0 24 24" fill="none">
          <path d="M5 15.5l3.2-3.2 3 2.3 4.3-5.1 3.5 2.8" />
          <path d="M5 19h14" />
        </svg>
        <svg v-else-if="item.key === 'rules'" viewBox="0 0 24 24" fill="none">
          <path d="M7 7.5h10" />
          <path d="M7 12h7" />
          <path d="M7 16.5h10" />
          <path d="M5.5 5.5h13v13h-13z" />
        </svg>
        <svg v-else-if="item.key === 'history'" viewBox="0 0 24 24" fill="none">
          <path d="M12 6v6l4 2.2" />
          <circle cx="12" cy="12" r="7" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none">
          <path d="M7 17.5h10" />
          <path d="M9 14.5l3-8 3 8" />
        </svg>
      </span>
      <span>{{ item.label }}</span>
    </RouterLink>
  </aside>
</template>

<script setup>
import { RouterLink } from 'vue-router'

const items = [
  { key: 'home', label: '首页', path: '/' },
  { key: 'patient', label: '患者', path: '/patients' },
  { key: 'analysis', label: '诊断', path: '/analysis' },
  { key: 'rules', label: '规则', path: '/rules' },
  { key: 'history', label: '历史', path: '/history' },
  { key: 'model', label: '模型', path: '/model' },
]
</script>

<style scoped>
.side-dock {
  position: sticky;
  top: 120px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dock-link {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.64);
  border: 1px solid rgba(15, 118, 110, 0.1);
  color: #5c6d7e;
  transition: 0.22s ease;
}

.dock-link.router-link-active,
.dock-link:hover {
  color: #164e63;
  background: rgba(255, 255, 255, 0.94);
  transform: translateX(4px);
}

.icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(239, 247, 247, 0.95), rgba(229, 241, 241, 0.92));
  border: 1px solid rgba(15, 118, 110, 0.08);
  flex: 0 0 auto;
}

.icon svg {
  width: 20px;
  height: 20px;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

@media (max-width: 980px) {
  .side-dock {
    display: none;
  }
}
</style>
