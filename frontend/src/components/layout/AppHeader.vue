<template>
  <header class="site-header">
    <router-link :to="logoTo" class="logo">
      <span class="logo__icon">&hearts;</span>
      <span>Chess Coach<span class="logo__ai">AI</span></span>
    </router-link>
    <div class="site-header__controls">
      <slot name="controls" />
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const logoTo = computed(() => {
  const userPath = route.params.userPath
  return userPath ? `/u/${userPath}` : '/'
})
</script>

<style scoped>
.site-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  height: 60px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.25rem;
  font-weight: 500;
  text-decoration: none;
  color: var(--text-primary);
}
.logo__icon {
  font-size: 1.5rem;
}
.logo__ai {
  color: var(--blue, #2563eb);
  font-weight: 700;
}
.site-header__controls {
  display: flex;
  align-items: center;
  gap: 8px;
}
@media (max-width: 768px) {
  .site-header {
    padding: 0 16px;
  }
}
</style>
