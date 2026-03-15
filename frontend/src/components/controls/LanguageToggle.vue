<template>
  <div class="lang-toggle">
    <button
      class="lang-btn"
      :class="{ active: locale === 'en' }"
      @click="setLang('en')"
    >EN</button>
    <button
      class="lang-btn"
      :class="{ active: locale === 'fr' }"
      @click="setLang('fr')"
    >FR</button>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

function setLang(lang) {
  locale.value = lang
  localStorage.setItem('lang', lang)
  document.documentElement.lang = lang
}
</script>

<style scoped>
.lang-toggle {
  display: flex;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 6px;
  overflow: hidden;
  height: 28px;
}
.lang-btn {
  padding: 0 8px;
  border: none;
  background: transparent;
  color: var(--text-muted, #94a3b8);
  font-size: 0.75rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: 0.3px;
}
.lang-btn:first-child {
  border-right: 1px solid var(--border, #e2e8f0);
}
.lang-btn:hover {
  color: var(--text-primary, #1e293b);
}
.lang-btn.active {
  background: var(--ctrl-active-bg, #f1f5f9);
  color: var(--text-primary, #1e293b);
}
</style>
