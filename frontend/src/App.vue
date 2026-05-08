<template>
  <div class="app-wrap">
    <div class="shell wrap">
      <TopNavBar />
      <div class="shell-body">
        <SideDock />
        <main class="content-area">
          <RouterView />
        </main>
      </div>
      <BackToTopButton />
    </div>
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router'
import BackToTopButton from '@/components/common/BackToTopButton.vue'
import TopNavBar from '@/components/common/TopNavBar.vue'
import SideDock from '@/components/common/SideDock.vue'
</script>

<style scoped>
.shell-body{display:grid;grid-template-columns:118px minmax(0,1fr);gap:26px;padding:0 0 36px}.content-area{min-width:0}
@media (max-width:980px){.shell-body{grid-template-columns:1fr}}
</style>
