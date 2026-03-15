<template>
  <span class="eval-badge" :class="`eval-badge--${type}`">{{ value }}</span>
</template>

<script setup>
defineProps({
  value: { type: String, required: true },
  type: { type: String, default: 'neutral', validator: v => ['good', 'bad', 'neutral'].includes(v) },
})
</script>

<style scoped>
.eval-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
}
.eval-badge--good {
  background: #f0fdf4;
  color: #16a34a;
}
.eval-badge--bad {
  background: #fef2f2;
  color: #dc2626;
}
.eval-badge--neutral {
  background: var(--badge-bg);
  color: var(--text-secondary);
}
[data-theme="dark"] .eval-badge--good {
  background: rgba(22, 163, 74, 0.15);
}
[data-theme="dark"] .eval-badge--bad {
  background: rgba(220, 38, 38, 0.15);
}
</style>
