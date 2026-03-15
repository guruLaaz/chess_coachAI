<template>
  <div class="sidebar-nav">
    <router-link
      :to="`/u/${userPath}`"
      class="sidebar-nav__link"
      :class="{ 'sidebar-nav__link--active': page === 'openings' }"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
      <span>{{ $t('nav_openings') }}</span>
    </router-link>
    <router-link
      :to="`/u/${userPath}/endgames`"
      class="sidebar-nav__link"
      :class="{ 'sidebar-nav__link--active': page === 'endgames' || page === 'endgames_all' }"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
      <span>{{ $t('nav_endgames') }}</span>
    </router-link>
  </div>
</template>

<script setup>
defineProps({
  userPath: { type: String, required: true },
  page: { type: String, default: '' },
})
</script>

<style scoped>
.sidebar-nav {
  padding: 8px 0;
}
.sidebar-nav__link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}
.sidebar-nav__link:hover {
  background: var(--bg-body);
  color: var(--text-primary);
}
.sidebar-nav__link--active {
  color: #f97316;
  border-left-color: #f97316;
  background: #fff7ed;
}
[data-theme="dark"] .sidebar-nav__link--active {
  background: #431407;
}
.sidebar-nav__link svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  opacity: 0.7;
}
.sidebar-nav__link--active svg {
  opacity: 1;
}
</style>
