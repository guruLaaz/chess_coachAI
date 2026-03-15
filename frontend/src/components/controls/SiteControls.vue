<template>
  <div class="site-controls">
    <LanguageToggle />
    <ThemeToggle />
    <button class="feedback-btn" title="Bug report / Contact us" @click="$emit('open-feedback')">
      <FeedbackIcon :width="14" :height="14" />
    </button>
  </div>
</template>

<script setup>
import LanguageToggle from './LanguageToggle.vue'
import ThemeToggle from './ThemeToggle.vue'
import FeedbackIcon from '../icons/FeedbackIcon.vue'

defineEmits(['open-feedback'])
</script>

<style scoped>
.site-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}
.feedback-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--text-muted, #94a3b8);
}
.feedback-btn:hover {
  color: var(--text-primary, #1e293b);
  background: var(--ctrl-active-bg, #f1f5f9);
}
.feedback-btn svg {
  width: 14px;
  height: 14px;
  opacity: 0.8;
}
</style>
