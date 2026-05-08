<template>
  <Transition name="back-top-fade">
    <button
      v-if="visible"
      type="button"
      class="back-top-button"
      aria-label="返回顶部"
      @click="scrollToTop"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 18V7" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" />
        <path d="M7.5 11.5 12 7l4.5 4.5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span>顶部</span>
    </button>
  </Transition>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const visible = ref(false)
const threshold = 320

function updateVisibility() {
  visible.value = window.scrollY > threshold
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  updateVisibility()
  window.addEventListener('scroll', updateVisibility, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', updateVisibility)
})
</script>

<style scoped>
.back-top-button {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 70;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid rgba(15, 118, 110, 0.16);
  border-radius: 999px;
  color: #164e63;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(18px);
  box-shadow: 0 18px 40px rgba(15, 35, 52, 0.12);
  transition: transform 0.22s ease, box-shadow 0.22s ease, opacity 0.22s ease;
}

.back-top-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 42px rgba(15, 35, 52, 0.16);
}

.back-top-button svg {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
}

.back-top-button span {
  line-height: 1;
  font-weight: 700;
}

.back-top-fade-enter-active,
.back-top-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.back-top-fade-enter-from,
.back-top-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 720px) {
  .back-top-button {
    right: 16px;
    bottom: 18px;
    padding: 11px 14px;
  }

  .back-top-button span {
    display: none;
  }
}
</style>
