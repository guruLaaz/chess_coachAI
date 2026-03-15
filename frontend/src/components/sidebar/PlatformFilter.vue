<template>
  <div class="sidebar-filter-group">
    <BaseSelect
      :label="$t('filter_platform')"
      :model-value="filters.platform"
      :options="platformOptions"
      id="platform-select"
      @update:model-value="v => { filters.platform = v; filters.saveToSessionStorage() }"
    />
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseSelect from '../ui/BaseSelect.vue'
import { useFiltersStore } from '../../stores/filters'

const { t } = useI18n()
const filters = useFiltersStore()

const platformOptions = [
  { value: 'all', label: t('filter_all_platforms') },
  { value: 'chesscom', label: 'Chess.com' },
  { value: 'lichess', label: 'Lichess' },
]
</script>

<style scoped>
.sidebar-filter-group {
  padding: 6px 20px;
}
</style>
