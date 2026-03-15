<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="['base-btn', `base-btn--${variant}`, `base-btn--${size}`, { 'base-btn--loading': loading }]"
  >
    <span v-if="loading" class="base-btn__spinner" />
    <slot />
  </button>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'primary', validator: v => ['primary', 'secondary', 'ghost'].includes(v) },
  size: { type: String, default: 'md', validator: v => ['sm', 'md'].includes(v) },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  type: { type: String, default: 'button' },
})
</script>

<style scoped>
.base-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  border-radius: 8px;
  font-family: inherit;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.base-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.base-btn--md {
  padding: 10px 24px;
  font-size: 0.95rem;
}
.base-btn--sm {
  padding: 6px 16px;
  font-size: 0.85rem;
}
.base-btn--primary {
  background: #2563eb;
  color: #fff;
}
.base-btn--primary:hover:not(:disabled) {
  background: #1d4ed8;
}
.base-btn--secondary {
  background: var(--bg-secondary, #f0f4f8);
  color: var(--text-primary);
  border: 1px solid var(--border);
}
.base-btn--secondary:hover:not(:disabled) {
  opacity: 0.8;
}
.base-btn--ghost {
  background: transparent;
  color: var(--text-primary);
}
.base-btn--ghost:hover:not(:disabled) {
  background: var(--bg-secondary, #f0f4f8);
}
.base-btn__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: btn-spin 0.6s linear infinite;
}
@keyframes btn-spin {
  to { transform: rotate(360deg); }
}
</style>
