<template>
  <div>
    <AppHeader>
      <template #controls>
        <SiteControls @open-feedback="uiStore.openFeedback()" />
      </template>
    </AppHeader>
    <div class="layout">
      <aside class="layout__sidebar">
        <slot name="sidebar" />
      </aside>
      <main class="layout__main">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import AppHeader from './AppHeader.vue'
import SiteControls from '../controls/SiteControls.vue'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()
</script>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
  padding-top: 60px;
}
.layout__sidebar {
  width: 260px;
  background: var(--bg-primary);
  border-right: 1px solid var(--border);
  position: sticky;
  top: 60px;
  height: calc(100vh - 60px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.layout__main {
  flex: 1;
  padding: 32px;
  max-width: 960px;
}
@media (max-width: 768px) {
  .layout {
    flex-direction: column;
  }
  .layout__sidebar {
    width: 100%;
    height: auto;
    position: static;
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}
</style>
