<template>
  <div class="section-title">
    <div>
      <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
    </div>
    <p v-if="description" class="description">{{ description }}</p>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  eyebrow: { type: String, default: '' },
  description: { type: String, default: '' },
})
</script>

<style scoped>
 .section-title { display:flex; justify-content:space-between; align-items:end; gap:16px; margin-bottom:14px; }
.section-title h2 { margin:4px 0 0; font-size:26px; }
.eyebrow { margin:0; color:#0f766e; font-size:12px; letter-spacing:.12em; text-transform:uppercase; }
.description { margin:0; max-width:420px; color:#5c6d7e; text-align:right; }
@media (max-width: 720px) {
  .section-title { flex-direction:column; align-items:flex-start; }
  .description { text-align:left; }
}
</style>
