<template>
  <div class="stat-card" :class="{ 'stat-card--donut': donut }">
    <template v-if="donut">
      <DonutChart :percentage="donutPct" :size="100" :stroke-width="5" />
      <div class="stat-card__label">{{ label }}</div>
    </template>
    <template v-else>
      <div class="stat-card__value">{{ value }}</div>
      <div class="stat-card__label">{{ label }}</div>
    </template>
  </div>
</template>

<script setup>
import DonutChart from './DonutChart.vue'

defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: '' },
  donut: { type: Boolean, default: false },
  donutPct: { type: Number, default: 0 },
})
</script>

<style scoped>
.stat-card {
  flex: 1;
  min-width: 120px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 20px;
  text-align: center;
}
.stat-card--donut {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.stat-card__value {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
}
.stat-card__label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 4px;
}
</style>
