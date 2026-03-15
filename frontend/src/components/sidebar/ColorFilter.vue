<template>
  <div class="sidebar-filter-group">
    <label class="sidebar-filter-label">{{ $t('filter_playing_as') }}</label>
    <ToggleGroup
      :model-value="filters.colors"
      :options="colorOptions"
      :columns="2"
      :min-selected="1"
      @update:model-value="v => { filters.colors = v; filters.saveToSessionStorage() }"
    />
  </div>
</template>

<script setup>
import ToggleGroup from '../ui/ToggleGroup.vue'
import { useFiltersStore } from '../../stores/filters'

const filters = useFiltersStore()

const colorOptions = [
  { value: 'white', label: 'White' },
  { value: 'black', label: 'Black' },
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
