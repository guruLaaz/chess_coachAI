<template>
  <div>
    <AppHeader>
      <template #controls>
        <SiteControls @open-feedback="uiStore.openFeedback()" />
      </template>
    </AppHeader>
    <main class="simple-layout">
      <slot />
    </main>
  </div>
</template>

<script setup>
import AppHeader from './AppHeader.vue'
import SiteControls from '../controls/SiteControls.vue'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()
</script>

<style scoped>
.simple-layout {
  padding-top: 60px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>
