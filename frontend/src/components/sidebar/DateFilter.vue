<template>
  <div class="sidebar-filter-group">
    <label class="sidebar-filter-label">{{ $t('filter_from') }}</label>
    <input
      type="date"
      class="sidebar-date"
      :value="filters.dateFrom"
      @change="onDateChange"
    />
    <div class="date-presets">
      <button
        v-for="preset in presets"
        :key="preset.days"
        type="button"
        class="date-preset"
        :class="{ 'date-preset--active': filters.dateDays === preset.days }"
        @click="onPresetClick(preset.days)"
      >
        {{ $t(preset.i18nKey) }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { useFiltersStore } from '../../stores/filters'

const filters = useFiltersStore()

const presets = [
  { days: '', i18nKey: 'filter_alltime' },
  { days: '7', i18nKey: 'filter_lastweek' },
  { days: '180', i18nKey: 'filter_6months' },
  { days: '365', i18nKey: 'filter_lastyear' },
]

function onPresetClick(days) {
  filters.dateDays = days
  if (days) {
    const d = new Date()
    d.setDate(d.getDate() - parseInt(days, 10))
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    filters.dateFrom = `${d.getFullYear()}-${mm}-${dd}`
  } else {
    filters.dateFrom = ''
  }
  filters.saveToSessionStorage()
}

function onDateChange(e) {
  filters.dateFrom = e.target.value
  filters.dateDays = ''
  if (!e.target.value) {
    filters.dateDays = ''
  }
  filters.saveToSessionStorage()
}
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
.sidebar-date {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--input-bg);
  color: var(--text-label);
  font-size: 0.85rem;
  font-family: inherit;
  cursor: pointer;
}
.sidebar-date:focus {
  outline: none;
  border-color: var(--text-muted);
}
.date-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.date-preset {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}
.date-preset:hover {
  border-color: var(--text-muted);
  color: var(--text-primary);
}
.date-preset--active {
  background: var(--badge-bg);
  color: var(--text-primary);
  border-color: var(--text-muted);
}
</style>
