<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fb-overlay"
      @mousedown="onOverlayMousedown"
      @click="onOverlayClick"
    >
      <div class="fb-card" @mousedown.stop>
        <button class="fb-close" @click="close">&times;</button>

        <!-- Form -->
        <div v-if="!success">
          <div class="fb-title">{{ t('feedback_title') }}</div>

          <div class="fb-field">
            <label>{{ t('feedback_type_label') }}</label>
            <select v-model="feedbackType">
              <option value="bug">{{ t('feedback_bug_report') }}</option>
              <option value="contact">{{ t('feedback_contact') }}</option>
            </select>
          </div>

          <!-- Screenshot section (bug only) -->
          <div v-if="feedbackType === 'bug'" class="fb-screenshot-section">
            <button
              v-if="!screenshotUrl"
              class="fb-capture-btn"
              :disabled="capturing"
              @click="captureScreenshot"
            >
              {{ capturing ? t('feedback_screenshot_loading') : t('feedback_screenshot_btn') }}
            </button>
            <div v-if="capturing && !screenshotUrl" class="fb-screenshot-loading">
              {{ t('feedback_screenshot_loading') }}
            </div>
            <div v-if="screenshotUrl" class="fb-screenshot-preview">
              <img :src="screenshotUrl" alt="Screenshot" />
            </div>
          </div>

          <div class="fb-field">
            <label>{{ t('feedback_email') }}</label>
            <input v-model="email" type="email" placeholder="you@example.com" />
          </div>

          <div class="fb-field">
            <label>{{ t('feedback_details') }}</label>
            <textarea v-model="details" />
          </div>

          <p v-if="error" class="fb-error">{{ error }}</p>

          <button class="fb-submit" :disabled="submitting" @click="submit">
            {{ t('feedback_submit') }}
          </button>
        </div>

        <!-- Success state -->
        <div v-else class="fb-success">
          <div class="fb-success-icon">&#10003;</div>
          <div class="fb-success-msg">{{ t('feedback_success') }}</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { submitFeedback } from '@/api'
import { getConsoleLogs } from '@/plugins/consoleCapture'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const feedbackType = ref('bug')
const email = ref('')
const details = ref('')
const error = ref('')
const success = ref(false)
const submitting = ref(false)
const capturing = ref(false)
const screenshotUrl = ref('')
let mouseDownOnOverlay = false

// Reset form when opened
watch(() => props.modelValue, (open) => {
  if (open) {
    feedbackType.value = 'bug'
    email.value = localStorage.getItem('feedback_email') || ''
    details.value = ''
    error.value = ''
    success.value = false
    submitting.value = false
    capturing.value = false
    screenshotUrl.value = ''
  }
})

function close() {
  emit('update:modelValue', false)
}

function onOverlayMousedown(e) {
  mouseDownOnOverlay = e.target === e.currentTarget
}

function onOverlayClick(e) {
  if (e.target === e.currentTarget && mouseDownOnOverlay) close()
  mouseDownOnOverlay = false
}

// Escape key
function onKeydown(e) {
  if (e.key === 'Escape' && props.modelValue) close()
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))

// Screenshot capture
let html2canvasModule = null

async function captureScreenshot() {
  capturing.value = true
  try {
    if (!html2canvasModule) {
      const script = document.createElement('script')
      script.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js'
      await new Promise((resolve, reject) => {
        script.onload = resolve
        script.onerror = reject
        document.head.appendChild(script)
      })
    }
    if (typeof window.html2canvas !== 'function') {
      capturing.value = false
      return
    }
    const canvas = await window.html2canvas(document.documentElement, {
      ignoreElements: (el) =>
        el.classList && el.classList.contains('fb-overlay'),
      scale: 0.5,
      logging: false,
      useCORS: true,
      x: window.scrollX,
      y: window.scrollY,
      width: window.innerWidth,
      height: window.innerHeight,
      windowWidth: window.innerWidth,
      windowHeight: window.innerHeight,
    })
    screenshotUrl.value = canvas.toDataURL('image/png')
  } catch {
    // silently fail
  }
  capturing.value = false
}

// Submit
async function submit() {
  error.value = ''
  const emailVal = email.value.trim()
  const detailsVal = details.value.trim()

  if (!emailVal || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal)) {
    error.value = t('feedback_error_email')
    return
  }
  if (!detailsVal) {
    error.value = t('feedback_error_details')
    return
  }

  submitting.value = true
  localStorage.setItem('feedback_email', emailVal)

  try {
    await submitFeedback({
      type: feedbackType.value,
      email: emailVal,
      details: detailsVal,
      screenshot: feedbackType.value === 'bug' ? screenshotUrl.value : '',
      page_url: window.location.href,
      console_logs: feedbackType.value === 'bug' ? JSON.stringify(getConsoleLogs()) : '',
    })
    success.value = true
    setTimeout(close, 2000)
  } catch {
    error.value = t('feedback_error_generic')
    submitting.value = false
  }
}
</script>

<style scoped>
.fb-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.fb-card {
  background: var(--card-bg, #fff);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
  max-width: 480px;
  width: 100%;
  padding: 32px;
  position: relative;
  max-height: 90vh;
  overflow-y: auto;
}
.fb-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-muted, #94a3b8);
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s;
}
.fb-close:hover {
  color: var(--text-primary, #1e293b);
  background: var(--ctrl-active-bg, #f1f5f9);
}
.fb-title {
  font-size: 1.2rem;
  font-weight: 700;
  margin-bottom: 20px;
  color: var(--text-primary, #1e293b);
}
.fb-field {
  margin-bottom: 16px;
}
.fb-field label {
  display: block;
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 6px;
  color: var(--text-label, #374151);
}
.fb-field select,
.fb-field input,
.fb-field textarea {
  width: 100%;
  border: 1px solid var(--border-input, #d1d5db);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 0.95rem;
  font-family: inherit;
  color: var(--input-text, var(--text-primary, #111));
  background: var(--input-bg, #fff);
  outline: none;
  transition: border-color 0.2s;
}
.fb-field select:focus,
.fb-field input:focus,
.fb-field textarea:focus {
  border-color: var(--blue, #2563eb);
  box-shadow: 0 0 0 3px var(--blue-focus, rgba(37, 99, 235, 0.1));
}
.fb-field textarea {
  resize: vertical;
  min-height: 100px;
}
.fb-screenshot-section {
  margin-bottom: 16px;
}
.fb-capture-btn {
  width: 100%;
  padding: 10px;
  border: 1px dashed var(--border, #e2e8f0);
  border-radius: 8px;
  background: transparent;
  color: var(--blue, #2563eb);
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 8px;
}
.fb-capture-btn:hover {
  background: var(--blue-focus, rgba(37, 99, 235, 0.1));
  border-color: var(--blue, #2563eb);
}
.fb-capture-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.fb-screenshot-preview {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
  max-height: 200px;
}
.fb-screenshot-preview img {
  width: 100%;
  display: block;
  object-fit: contain;
}
.fb-screenshot-loading {
  text-align: center;
  padding: 16px;
  color: var(--text-muted, #94a3b8);
  font-size: 0.85rem;
}
.fb-error {
  color: var(--error, #dc2626);
  font-size: 0.85rem;
  margin-bottom: 12px;
}
.fb-submit {
  width: 100%;
  background: var(--blue, #2563eb);
  color: #fff;
  border: none;
  padding: 12px;
  border-radius: 8px;
  font-family: inherit;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s;
}
.fb-submit:hover {
  background: var(--blue-hover, #1d4ed8);
}
.fb-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.fb-success {
  text-align: center;
  padding: 24px 0;
}
.fb-success-icon {
  font-size: 2.5rem;
  margin-bottom: 12px;
  color: var(--success, #16a34a);
}
.fb-success-msg {
  font-size: 1rem;
  font-weight: 500;
  color: var(--text-primary, #1e293b);
}
</style>
