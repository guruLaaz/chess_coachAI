<template>
  <div class="base-input">
    <label v-if="label" :for="id" class="base-input__label">{{ label }}</label>
    <div class="base-input__wrapper" :class="{ 'base-input__wrapper--has-prefix': $slots.prefix, 'base-input__wrapper--error': error }">
      <span v-if="$slots.prefix" class="base-input__prefix">
        <slot name="prefix" />
      </span>
      <input
        :id="id"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        class="base-input__field"
        @input="$emit('update:modelValue', $event.target.value)"
      />
    </div>
    <span v-if="error" class="base-input__error">{{ error }}</span>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  error: { type: String, default: '' },
  type: { type: String, default: 'text' },
  id: { type: String, default: '' },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.base-input__label {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 600;
  margin-bottom: 8px;
}
.base-input__wrapper {
  position: relative;
}
.base-input__prefix {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  color: var(--text-muted);
}
.base-input__field {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--input-bg);
  color: var(--text-label);
  font-size: 0.85rem;
  font-family: inherit;
  transition: border-color 0.15s;
}
.base-input__wrapper--has-prefix .base-input__field {
  padding-left: 40px;
}
.base-input__field:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px var(--blue-focus, rgba(37, 99, 235, 0.1));
}
.base-input__wrapper--error .base-input__field {
  border-color: var(--error, #dc2626);
}
.base-input__error {
  display: block;
  margin-top: 4px;
  font-size: 0.85rem;
  color: var(--error, #dc2626);
}
</style>
