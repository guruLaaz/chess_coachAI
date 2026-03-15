import { createI18n } from 'vue-i18n'
import en from './en.js'
import fr from './fr.js'

export default createI18n({
  legacy: false,
  locale: localStorage.getItem('lang') || 'en',
  fallbackLocale: 'en',
  messages: { en, fr },
})
