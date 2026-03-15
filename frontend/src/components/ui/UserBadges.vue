<template>
  <span class="user-badges">
    <a
      v-if="chesscomUser"
      class="user-badge"
      :href="`https://www.chess.com/member/${chesscomUser}`"
      target="_blank"
      rel="noopener"
    >
      <svg viewBox="0 0 96.4 144"><path fill="#81b64c" d="M48.2 0C35.4-.1 25 10.3 24.9 23.1c0 7.5 3.6 14.6 9.7 18.9L17.9 53c0 3.5.9 6.9 2.6 9.9h14.8c-.3 6.6 2.4 22.6-21.8 41.1C5 110.4 0 121.3 0 134.6c0 .6 1.3 9.4 48.2 9.4s48.2-8.8 48.2-9.4c0-13.3-5-24.3-13.4-30.7-24.2-18.5-21.5-34.5-21.8-41.1H76c1.7-3 2.6-6.4 2.6-9.8L61.8 42c10.4-7.5 12.8-21.9 5.3-32.3C62.8 3.6 55.7 0 48.2 0z"/></svg>
      {{ chesscomUser }}
    </a>
    <a
      v-if="lichessUser"
      class="user-badge"
      :href="`https://lichess.org/@/${lichessUser}`"
      target="_blank"
      rel="noopener"
    >
      <svg viewBox="0 0 50 50"><path fill="currentColor" stroke="currentColor" stroke-linejoin="round" d="M38.956.5c-3.53.418-6.452.902-9.286 2.984C5.534 1.786-.692 18.533.68 29.364 3.493 50.214 31.918 55.785 41.329 41.7c-7.444 7.696-19.276 8.752-28.323 3.084C3.959 39.116-.506 27.392 4.683 17.567 9.873 7.742 18.996 4.535 29.03 6.405c2.43-1.418 5.225-3.22 7.655-3.187l-1.694 4.86 12.752 21.37c-.439 5.654-5.459 6.112-5.459 6.112-.574-1.47-1.634-2.942-4.842-6.036-3.207-3.094-17.465-10.177-15.788-16.207-2.001 6.967 10.311 14.152 14.04 17.663 3.73 3.51 5.426 6.04 5.795 6.756 0 0 9.392-2.504 7.838-8.927L37.4 7.171z"/></svg>
      {{ lichessUser }}
    </a>
  </span>
</template>

<script setup>
defineProps({
  chesscomUser: { type: String, default: null },
  lichessUser: { type: String, default: null },
})
</script>

<style scoped>
.user-badges {
  display: inline;
}
.user-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--badge-bg);
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 500;
  vertical-align: middle;
  color: var(--text-primary);
  text-decoration: none;
  transition: background 0.15s;
}
.user-badge + .user-badge {
  margin-left: 8px;
}
.user-badge:hover {
  background: var(--toggle-active-bg);
}
.user-badge svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}
</style>
