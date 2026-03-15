<template>
  <nav class="the-sidebar">
    <SidebarNav :user-path="userPath" :page="page" />
    <div class="sidebar-divider" />
    <SidebarFilters v-if="showFilters" />
    <SidebarSyncButton :chesscom-user="chesscomUser" :lichess-user="lichessUser" />
  </nav>
</template>

<script setup>
import SidebarNav from './SidebarNav.vue'
import SidebarFilters from './SidebarFilters.vue'
import SidebarSyncButton from './SidebarSyncButton.vue'

defineProps({
  userPath: { type: String, required: true },
  chesscomUser: { type: String, default: '' },
  lichessUser: { type: String, default: '' },
  page: { type: String, default: 'openings', validator: v => ['openings', 'endgames', 'endgames_all'].includes(v) },
  showFilters: { type: Boolean, default: true },
})
</script>

<style scoped>
.the-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.sidebar-divider {
  height: 1px;
  background: var(--border);
  margin: 8px 0;
}
</style>
