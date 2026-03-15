<template>
  <div class="toggle-group" :style="{ '--columns': columns }">
    <button
      v-for="(opt, idx) in options"
      :key="opt.value"
      type="button"
      class="toggle-group__btn"
      :class="{
        'toggle-group__btn--active': modelValue.includes(opt.value),
        [`toggle-group__btn--pos-${positionClass(idx)}`]: true,
      }"
      @click="toggle(opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Array, required: true },
  options: { type: Array, required: true },
  minSelected: { type: Number, default: 0 },
  columns: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue'])

const cols = props.columns || props.options.length

function positionClass(idx) {
  const total = props.options.length
  const rows = Math.ceil(total / cols)
  const row = Math.floor(idx / cols)
  const col = idx % cols
  const lastCol = col === cols - 1 || idx === total - 1
  const firstCol = col === 0
  const firstRow = row === 0
  const lastRow = row === rows - 1

  const classes = []
  if (firstRow && firstCol) classes.push('tl')
  if (firstRow && lastCol) classes.push('tr')
  if (lastRow && firstCol) classes.push('bl')
  if (lastRow && lastCol) classes.push('br')
  return classes.join('-') || 'none'
}

function toggle(value) {
  const current = [...props.modelValue]
  const idx = current.indexOf(value)
  if (idx >= 0) {
    if (current.length <= props.minSelected) return
    current.splice(idx, 1)
  } else {
    current.push(value)
  }
  emit('update:modelValue', current)
}
</script>

<style scoped>
.toggle-group {
  display: flex;
  flex-wrap: wrap;
  border: 1px solid var(--border-input);
  border-radius: 6px;
  overflow: hidden;
}
.toggle-group__btn {
  flex: 1 1 calc(100% / var(--columns, 2));
  padding: 7px 8px;
  border: none;
  border-right: 1px solid rgba(128, 128, 128, 0.3);
  border-bottom: 1px solid rgba(128, 128, 128, 0.3);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}
.toggle-group__btn:hover {
  background: var(--bg-body);
  color: var(--text-primary);
}
.toggle-group__btn--active {
  background: var(--toggle-active-bg);
  color: var(--text-primary);
}
/* Remove right border on last column items */
.toggle-group[style*="--columns: 2"] .toggle-group__btn:nth-child(2n) { border-right: none; }
.toggle-group[style*="--columns: 2"] .toggle-group__btn:nth-child(n+3) { border-bottom: none; }
.toggle-group[style*="--columns: 3"] .toggle-group__btn:nth-child(3n) { border-right: none; }
.toggle-group[style*="--columns: 4"] .toggle-group__btn:nth-child(4n) { border-right: none; }
/* Remove bottom border on last row */
.toggle-group[style*="--columns: 3"] .toggle-group__btn:nth-last-child(-n+3) { border-bottom: none; }
.toggle-group[style*="--columns: 4"] .toggle-group__btn:nth-last-child(-n+4) { border-bottom: none; }
</style>
