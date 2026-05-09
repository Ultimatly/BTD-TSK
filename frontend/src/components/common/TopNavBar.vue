<template>
  <header class="top-nav">
    <div class="brand">
      <div class="brand-mark">
        <img src="/somnolight-icon.svg" alt="SomnoLight 图标" />
      </div>
      <div class="brand-copy">
        <strong>SomnoLight</strong>
        <p>多源数据睡眠障碍病症轻量化辅助诊断系统</p>
      </div>
    </div>
    <nav class="nav-links">
      <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-link">{{ item.label }}</RouterLink>
    </nav>
    <RouterLink to="/analysis" class="cta">开始诊断</RouterLink>
  </header>
</template>

<script setup>
import { RouterLink } from 'vue-router'

const navItems = [
  { label: '总览', path: '/' },
  { label: '患者', path: '/patients' },
  { label: '诊断', path: '/analysis' },
  { label: '规则', path: '/rules' },
  { label: '历史', path: '/history' },
  { label: '模型', path: '/model' },
]
</script>

<style scoped>
.top-nav {
  position: sticky;
  top: 16px;
  z-index: 20;
  margin: 16px auto 28px;
  padding: 16px 20px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 20px;
  align-items: center;
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.68);
  backdrop-filter: blur(16px);
  box-shadow: 0 18px 50px rgba(15, 35, 52, 0.08);
}

.brand {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.1), rgba(22, 78, 99, 0.12));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.6),
    0 12px 28px rgba(15, 118, 110, 0.14);
  overflow: hidden;
  isolation: isolate;
  animation: brandFloat 6s ease-in-out infinite;
}

.brand-mark::before {
  content: '';
  position: absolute;
  inset: -18%;
  background: radial-gradient(circle, rgba(94, 210, 198, 0.32), rgba(94, 210, 198, 0));
  opacity: 0.5;
  filter: blur(10px);
  z-index: -1;
  animation: markGlow 5.5s ease-in-out infinite;
}

.brand-mark::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 8px;
  right: 6px;
  top: 8px;
  border-radius: 999px;
  background: #f7b955;
  box-shadow: 0 0 0 5px rgba(247, 185, 85, 0.14);
  animation: orbitDot 4.8s ease-in-out infinite;
}

.brand-mark img {
  width: 44px;
  height: 44px;
  display: block;
  transform-origin: center;
  animation: logoBreath 6s ease-in-out infinite;
}

.brand p,
.brand strong {
  margin: 0;
}

.brand-copy {
  position: relative;
}

.brand strong {
  display: inline-block;
  font-size: 1.02rem;
  letter-spacing: -0.015em;
  animation: brandReveal 0.55s ease-out both;
}

.brand p {
  color: #5c6d7e;
  font-size: 12px;
  animation: brandReveal 0.65s ease-out both;
}

.brand:hover .brand-mark {
  animation-duration: 3.2s;
}

.brand:hover .brand-mark img {
  transform: scale(1.04);
}

@keyframes brandFloat {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-2px);
  }
}

@keyframes logoBreath {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.025);
  }
}

@keyframes markGlow {
  0%,
  100% {
    opacity: 0.28;
    transform: scale(0.96);
  }
  50% {
    opacity: 0.56;
    transform: scale(1.08);
  }
}

@keyframes orbitDot {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  30% {
    transform: translate3d(1px, -2px, 0);
  }
  65% {
    transform: translate3d(-2px, 2px, 0);
  }
}

@keyframes brandReveal {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.nav-links {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}

.nav-link {
  padding: 10px 14px;
  border-radius: 999px;
  color: #5c6d7e;
}

.nav-link.router-link-active,
.nav-link:hover {
  color: #164e63;
  background: rgba(15, 118, 110, 0.1);
}

.cta {
  padding: 12px 18px;
  border-radius: 999px;
  color: #fff;
  background: linear-gradient(135deg, #0f766e, #164e63);
}

@media (max-width: 1200px) {
  .top-nav {
    grid-template-columns: 1fr;
  }

  .nav-links {
    justify-content: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .brand-mark,
  .brand-mark::before,
  .brand-mark::after,
  .brand-mark img,
  .brand-copy::after,
  .brand strong,
  .brand p {
    animation: none;
  }
}
</style>
