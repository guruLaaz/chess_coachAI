<template>
  <div class="sidebar-filter-group">
    <label class="sidebar-filter-label">{{ $t('filter_time_control') }}</label>
    <ToggleGroup
      :model-value="filters.timeControls"
      :options="tcOptions"
      :columns="2"
      :min-selected="0"
      @update:model-value="v => { filters.timeControls = v; filters.saveToSessionStorage() }"
    />
  </div>
</template>

<script setup>
import ToggleGroup from '../ui/ToggleGroup.vue'
import { useFiltersStore } from '../../stores/filters'

const filters = useFiltersStore()

const tcOptions = [
  { value: 'bullet', label: 'Bullet' },
  { value: 'blitz', label: 'Blitz' },
  { value: 'rapid', label: 'Rapid' },
  { value: 'daily', label: 'Daily' },
]
</script>

<style scoped>
.sidebar-filter-group {
  padding: 6px 20px;
}
.sidebar-filter-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 600;
  margin-bottom: 8px;
  display: block;
}
</style>
