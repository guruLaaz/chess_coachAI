<template>
  <div class="empty-state">
    <div class="empty-state__icon">{{ icon }}</div>
    <h2 class="empty-state__title">{{ title }}</h2>
    <p class="empty-state__desc">{{ description }}</p>
    <router-link v-if="actionLabel && actionTo" :to="actionTo" custom v-slot="{ navigate }">
      <BaseButton variant="primary" @click="navigate">{{ actionLabel }}</BaseButton>
    </router-link>
  </div>
</template>

<script setup>
import BaseButton from './BaseButton.vue'

defineProps({
  icon: { type: String, default: '\u2658' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
  actionTo: { type: String, default: '' },
})
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}
.empty-state__icon {
  font-size: 3rem;
  margin-bottom: 16px;
}
.empty-state__title {
  font-size: 1.5rem;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.empty-state__desc {
  color: var(--text-secondary);
  margin-bottom: 20px;
}
</style>
