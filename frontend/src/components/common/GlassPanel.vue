<template>
  <component :is="tag" class="glass-panel" :class="[tone, { padded }]">
    <slot />
  </component>
</template>

<script setup>
defineProps({
  tag: { type: String, default: 'section' },
  tone: { type: String, default: 'default' },
  padded: { type: Boolean, default: true },
})
</script>

<style scoped>
.glass-panel {
  border-radius: 28px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  box-shadow: 0 18px 50px rgba(15, 35, 52, 0.08);
  overflow: hidden;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(16px);
}
.glass-panel.padded { padding: 24px; }
.glass-panel.deep {
  color: white;
  background: linear-gradient(135deg, rgba(22, 78, 99, 0.95), rgba(15, 118, 110, 0.88));
  border-color: rgba(255,255,255,0.12);
}
.glass-panel.hero {
  color: white;
  background: radial-gradient(circle at top left, rgba(255,255,255,.18), transparent 26%), linear-gradient(135deg, #0f766e 0%, #164e63 62%, #0b2f3f 100%);
  border-color: rgba(255,255,255,0.12);
}
</style>
