import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const darkMode = ref(false)

  function applyTheme() {
    if (darkMode.value) {
      document.documentElement.setAttribute('data-theme', 'dark')
    } else {
      document.documentElement.removeAttribute('data-theme')
    }
  }

  function toggle() {
    darkMode.value = !darkMode.value
    localStorage.setItem('theme', darkMode.value ? 'dark' : 'light')
    applyTheme()
  }

  function init() {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark') {
      darkMode.value = true
    } else if (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      darkMode.value = true
    }
    applyTheme()
  }

  return { darkMode, toggle, init }
})
