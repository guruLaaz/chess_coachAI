<template>
  <svg :width="size" :height="size" :viewBox="`0 0 ${viewBox} ${viewBox}`" class="donut-chart">
    <circle
      :cx="center"
      :cy="center"
      :r="radius"
      fill="none"
      stroke="var(--border)"
      :stroke-width="strokeWidth * 2.4"
    />
    <circle
      :cx="center"
      :cy="center"
      :r="radius"
      fill="none"
      :stroke="color"
      :stroke-width="strokeWidth * 2.4"
      :stroke-dasharray="`${dashFill} ${circumference}`"
      :transform="`rotate(-90 ${center} ${center})`"
      stroke-linecap="round"
    />
    <text
      :x="center"
      :y="center"
      text-anchor="middle"
      dominant-baseline="central"
      :font-size="fontSize"
      font-weight="700"
      fill="var(--donut-text, var(--text-primary))"
    >{{ percentage }}%</text>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  percentage: { type: Number, default: 0 },
  size: { type: Number, default: 48 },
  strokeWidth: { type: Number, default: 4 },
  color: { type: String, default: 'var(--blue)' },
})

const viewBox = 120
const center = 60
const radius = 50
const circumference = 2 * Math.PI * radius
const dashFill = computed(() => ((props.percentage / 100) * circumference).toFixed(1))
const fontSize = computed(() => props.size < 60 ? 20 : 20)
</script>

<style scoped>
.donut-chart {
  display: block;
}
</style>
