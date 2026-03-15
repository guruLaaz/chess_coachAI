<template>
  <div class="base-select">
    <label v-if="label" :for="id" class="base-select__label">{{ label }}</label>
    <select
      :id="id"
      :value="modelValue"
      class="base-select__field"
      @change="$emit('update:modelValue', $event.target.value)"
    >
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  options: { type: Array, required: true },
  id: { type: String, default: '' },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.base-select__label {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 600;
  margin-bottom: 8px;
}
.base-select__field {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--input-bg);
  color: var(--text-label);
  font-size: 0.9rem;
  font-family: inherit;
  cursor: pointer;
}
.base-select__field:focus {
  outline: none;
  border-color: var(--text-muted);
}
</style>
