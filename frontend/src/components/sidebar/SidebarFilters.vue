<template>
  <div class="sidebar-filters">
    <div class="sidebar-section-label">{{ $t('filter_label') }}</div>
    <PlatformFilter />
    <TimeControlFilter />
    <ColorFilter />
    <MinGamesFilter />
    <DateFilter />
  </div>
</template>

<script setup>
import PlatformFilter from './PlatformFilter.vue'
import TimeControlFilter from './TimeControlFilter.vue'
import ColorFilter from './ColorFilter.vue'
import MinGamesFilter from './MinGamesFilter.vue'
import DateFilter from './DateFilter.vue'
</script>

<style scoped>
.sidebar-section-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 600;
  padding: 12px 20px 6px;
}
</style>
