<template>
  <div class="admin-layout">
    <header class="admin-header">
      <div>
        <slot name="header" />
      </div>
      <div class="admin-header__actions">
        <slot name="actions" />
      </div>
    </header>
    <main class="admin-main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.admin-layout {
  background: #0f172a;
  min-height: 100vh;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  padding: 24px;
}
.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.admin-header__actions {
  display: flex;
  gap: 8px;
}
@media (max-width: 768px) {
  .admin-layout {
    padding: 12px;
  }
}
</style>
