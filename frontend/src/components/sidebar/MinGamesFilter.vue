<template>
  <div class="sidebar-filter-group">
    <label class="sidebar-filter-label">
      <span>{{ $t('filter_min_games') }}</span> <span class="min-games-value">{{ filters.minGames }}</span>
    </label>
    <div class="sidebar-range-wrap">
      <input
        type="range"
        class="sidebar-range"
        min="1"
        max="20"
        :value="filters.minGames"
        @input="onInput"
      />
    </div>
  </div>
</template>

<script setup>
import { useFiltersStore } from '../../stores/filters'

const filters = useFiltersStore()

function onInput(e) {
  filters.minGames = parseInt(e.target.value, 10)
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
.min-games-value {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}
.sidebar-range-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sidebar-range {
  flex: 1;
  -webkit-appearance: none;
  height: 4px;
  border-radius: 2px;
  background: var(--border);
  outline: none;
}
.sidebar-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #f97316;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}
.sidebar-range::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #f97316;
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}
</style>
