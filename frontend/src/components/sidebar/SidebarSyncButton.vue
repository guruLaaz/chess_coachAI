<template>
  <div class="sidebar-bottom">
    <form action="/analyze" method="POST">
      <input type="hidden" name="chesscom_username" :value="chesscomUser || ''" />
      <input type="hidden" name="lichess_username" :value="lichessUser || ''" />
      <button type="submit" class="sync-btn">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        <span>{{ $t('sync_btn') }}</span>
      </button>
    </form>
  </div>
</template>

<script setup>
defineProps({
  chesscomUser: { type: String, default: '' },
  lichessUser: { type: String, default: '' },
})
</script>

<style scoped>
.sidebar-bottom {
  margin-top: auto;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}
.sync-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  background: #0d9488;
  color: #ffffff;
  border: none;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s;
}
.sync-btn:hover {
  background: #0f766e;
}
.sync-btn svg {
  width: 16px;
  height: 16px;
}
</style>
