import { installConsoleCapture } from './plugins/consoleCapture'
installConsoleCapture()

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import './assets/theme.css'

const pinia = createPinia()
const app = createApp(App)
app.config.devtools = true

app.use(pinia)
app.use(router)
app.use(i18n)
app.mount('#app')
