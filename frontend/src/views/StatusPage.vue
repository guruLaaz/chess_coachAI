<template>
  <SimpleLayout>
    <template #header-controls>
      <router-link to="/" class="back-link">{{ t('back_home') }}</router-link>
    </template>

    <div class="status-container">
      <div :class="['status-card', { pulsing: status === 'pending' }]">
        <!-- Spinner -->
        <div v-if="showSpinner" class="spinner" />

        <!-- Success / Error icons -->
        <div v-if="status === 'complete'" class="status-icon success">✓</div>
        <div v-if="status === 'failed' || status === 'not_found'" class="status-icon error">✗</div>

        <h2 class="status-title">{{ statusTitle }}</h2>
        <p class="status-message">{{ statusMessage }}</p>

        <!-- Queue position -->
        <p v-if="status === 'pending' && queuePosition" class="queue-position">
          {{ t('status_queue_position', { 0: queuePosition, 1: queueTotal }) }}
        </p>

        <!-- Progress bar -->
        <div v-if="showProgress" class="progress-container">
          <div class="progress-fill" :style="{ width: progressPct + '%' }" />
        </div>
        <p v-if="showProgress" class="progress-text">
          {{ progressMsg }} ({{ progressPct }}%)
        </p>

        <!-- Elapsed time -->
        <p v-if="elapsedSeconds != null && showProgress" class="elapsed-time">
          {{ t('status_elapsed') }} {{ formatElapsed(elapsedSeconds) }}
        </p>

        <!-- Error detail -->
        <div v-if="status === 'failed' && errorMessage" class="error-detail">
          {{ errorMessage }}
        </div>

        <!-- View report link -->
        <router-link
          v-if="status === 'complete'"
          :to="'/u/' + userPath"
          class="action-link"
        >
          View Report →
        </router-link>

        <!-- Retry form -->
        <div v-if="status === 'failed' || status === 'not_found'" class="retry-section">
          <AnalyzeForm
            compact
            :chesscom-user="chesscomUser"
            :lichess-user="lichessUser"
            :error-keys="retryErrors"
            @submit="onRetry"
          />
        </div>
      </div>
    </div>
  </SimpleLayout>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import SimpleLayout from '@/components/layout/SimpleLayout.vue'
import AnalyzeForm from '@/components/forms/AnalyzeForm.vue'
import { fetchStatusJson, submitAnalysis } from '@/api'
import { translateMessage } from '@/utils/translateMessage'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const userPath = computed(() => route.params.userPath)

const status = ref('pending')
const queuePosition = ref(null)
const queueTotal = ref(null)
const progressPct = ref(0)
const progressMsg = ref('')
const elapsedSeconds = ref(null)
const errorMessage = ref('')
const chesscomUser = ref('')
const lichessUser = ref('')
const retryErrors = ref([])

let pollTimer = null
let isComplete = false
let navigatingAway = false

const showSpinner = computed(() =>
  ['pending', 'fetching', 'analyzing'].includes(status.value),
)

const showProgress = computed(() =>
  ['fetching', 'analyzing'].includes(status.value),
)

const statusTitle = computed(() => {
  switch (status.value) {
    case 'pending':
      return t('status_queued_title')
    case 'fetching':
      return t('status_fetching_title')
    case 'analyzing':
      return t('status_analyzing_title')
    case 'complete':
      return t('status_complete_title')
    case 'failed':
      return t('status_failed_title')
    case 'not_found':
      return t('status_not_found_title')
    default:
      return t('status_checking_title')
  }
})

const statusMessage = computed(() => {
  switch (status.value) {
    case 'pending':
      return t('status_queued_msg')
    case 'fetching':
      return progressMsg.value || t('status_fetching_msg')
    case 'analyzing':
      return progressMsg.value || t('status_analyzing_msg')
    case 'complete': {
      let msg = t('status_complete_msg')
      if (elapsedSeconds.value != null) {
        msg += ' (' + formatElapsed(elapsedSeconds.value) + ')'
      }
      return msg
    }
    case 'failed':
      return t('status_failed_msg')
    case 'not_found':
      return t('status_not_found_msg')
    default:
      return t('status_checking_msg')
  }
})

function formatElapsed(seconds) {
  if (seconds < 60) return seconds + 's'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return m + ':' + String(s).padStart(2, '0')
  const h = Math.floor(m / 60)
  const rm = m % 60
  return h + ':' + String(rm).padStart(2, '0') + ':' + String(s).padStart(2, '0')
}

function updateFromData(data) {
  status.value = data.status
  if (data.status === 'complete') isComplete = true

  queuePosition.value = data.queue_position || null
  queueTotal.value = data.queue_total || null
  elapsedSeconds.value = data.elapsed_seconds ?? null
  errorMessage.value = data.error_message || ''

  if (data.chesscom_user) chesscomUser.value = data.chesscom_user
  if (data.lichess_user) lichessUser.value = data.lichess_user

  // Translate progress message
  if (data.message) {
    progressMsg.value = translateMessage(data.message, t)
  } else {
    progressMsg.value = ''
  }

  // Progress percentage
  if (data.status === 'fetching') {
    progressPct.value = Math.min(data.progress_pct || 0, 30)
  } else {
    progressPct.value = data.progress_pct || 0
  }
}

async function poll() {
  try {
    const data = await fetchStatusJson(userPath.value)
    updateFromData(data)

    if (data.status === 'complete') {
      navigatingAway = true
      setTimeout(() => {
        router.push('/u/' + userPath.value)
      }, 1000)
    } else if (data.status !== 'failed' && data.status !== 'not_found') {
      pollTimer = setTimeout(poll, 3000)
    }
  } catch {
    // Retry on network error
    pollTimer = setTimeout(poll, 5000)
  }
}

async function onRetry({ chesscomUser: cc, lichessUser: li }) {
  retryErrors.value = []
  try {
    const data = await submitAnalysis({
      chesscom_username: cc,
      lichess_username: li,
    })
    if (data.redirect) {
      router.push(data.redirect)
    }
  } catch (err) {
    try {
      const body = JSON.parse(err.message.replace(/^\d+:\s*/, ''))
      if (body.error_keys) {
        retryErrors.value = body.error_keys
      }
    } catch {
      retryErrors.value = [{ key: 'error_msg' }]
    }
  }
}

onMounted(() => {
  poll()
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
  if (!navigatingAway && status.value === 'pending' && !isComplete) {
    navigator.sendBeacon(`/u/${userPath.value}/status/cancel`)
  }
})
</script>

<style scoped>
.back-link {
  color: var(--text-secondary);
  font-size: 0.95rem;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.2s;
}
.back-link:hover {
  color: var(--text-primary);
}

.status-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 60px);
  padding: 40px 24px;
}

.status-card {
  background: var(--card-bg);
  border-radius: 16px;
  box-shadow: var(--card-shadow, 0 4px 24px rgba(0, 0, 0, 0.08));
  max-width: 480px;
  width: 100%;
  padding: 40px 32px;
  text-align: center;
}

.status-card.pulsing {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    box-shadow: var(--card-shadow, 0 4px 24px rgba(0, 0, 0, 0.08));
  }
  50% {
    box-shadow: var(--pulse-glow, 0 4px 32px rgba(37, 99, 235, 0.25));
  }
}

/* Spinner */
.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--progress-bg, #e5e7eb);
  border-top-color: var(--blue, #2563eb);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 24px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Status icons */
.status-icon {
  font-size: 3rem;
  margin-bottom: 16px;
  line-height: 1;
}
.status-icon.success {
  color: var(--success, #16a34a);
}
.status-icon.error {
  color: var(--error, #dc2626);
}

/* Text */
.status-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text-primary);
}
.status-message {
  color: var(--text-secondary);
  font-size: 0.95rem;
  margin-bottom: 24px;
  line-height: 1.5;
}

.queue-position {
  font-size: 0.9rem;
  color: var(--text-secondary);
  font-weight: 500;
  margin-bottom: 16px;
}

/* Progress */
.progress-container {
  width: 100%;
  height: 8px;
  background: var(--progress-bg, #e5e7eb);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 12px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #3b82f6);
  border-radius: 4px;
  transition: width 0.5s ease;
}
.progress-text {
  font-size: 0.85rem;
  color: var(--progress-text, #9ca3af);
}
.elapsed-time {
  font-size: 0.8rem;
  color: var(--progress-text, #9ca3af);
  opacity: 0.7;
  margin-top: 4px;
}

/* Error detail */
.error-detail {
  background: var(--error-bg, #fef2f2);
  border: 1px solid var(--error-border, #fecaca);
  border-radius: 8px;
  padding: 12px 16px;
  margin-top: 16px;
  color: var(--error-text, #991b1b);
  font-size: 0.9rem;
  text-align: left;
  word-break: break-word;
}

/* Action link */
.action-link {
  display: inline-block;
  margin-top: 16px;
  color: var(--blue, #2563eb);
  font-weight: 500;
  text-decoration: none;
  font-size: 1rem;
  transition: color 0.2s;
}
.action-link:hover {
  color: var(--blue-hover, #1d4ed8);
}

/* Retry */
.retry-section {
  margin-top: 24px;
}

@media (max-width: 768px) {
  .status-card {
    padding: 32px 24px;
  }
}
</style>
