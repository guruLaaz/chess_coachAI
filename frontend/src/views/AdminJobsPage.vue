<template>
  <AdminLayout>
    <template #header>
      <h1>Analysis Jobs</h1>
      <p class="subtitle">Chess CoachAI — Analysis Pipeline Monitor</p>
    </template>
    <template #actions>
      <router-link to="/admin/feedback" class="admin-btn">Feedback</router-link>
      <button class="admin-btn" :class="{ 'admin-btn--active': showFlaskLogs }" @click="toggleFlaskLogs">Flask Logs</button>
      <button class="admin-btn" @click="loadJobs">Refresh</button>
    </template>

    <!-- Flask Logs Panel -->
    <div v-if="showFlaskLogs" class="flask-logs-panel">
      <div class="flask-logs-panel__header">
        <div class="flask-logs-panel__controls">
          <span class="flask-logs-panel__label">Flask Server Logs</span>
          <select v-model="flaskLogLevel" class="admin-select" @change="loadFlaskLogs">
            <option value="">All levels</option>
            <option value="ERROR">Errors only</option>
            <option value="WARNING">Warning+</option>
            <option value="INFO">Info+</option>
          </select>
        </div>
        <button class="admin-btn admin-btn--sm" @click="loadFlaskLogs">Reload</button>
      </div>
      <pre class="log-content" ref="flaskLogsEl">{{ flaskLogsLoading ? 'Loading...' : '' }}</pre>
    </div>

    <!-- Summary Cards -->
    <div class="summary">
      <StatCard :value="activeCnt" label="Active" class="stat--active" />
      <StatCard :value="queuedCnt" label="Queued" class="stat--queued" />
      <StatCard :value="completeCnt" label="Complete" class="stat--complete" />
      <StatCard :value="failedCnt" label="Failed" class="stat--failed" />
      <StatCard :value="jobs.length" label="Total" class="stat--total" />
    </div>

    <!-- Filter Tabs -->
    <div class="filters">
      <button
        v-for="f in filterTabs"
        :key="f.key"
        class="filter-btn"
        :class="{ 'filter-btn--active': activeFilter === f.key }"
        @click="activeFilter = f.key"
      >{{ f.label }}</button>
    </div>

    <!-- Jobs Table -->
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>User</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Games</th>
            <th>Duration</th>
            <th>Created</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="job in filteredJobs" :key="job.id">
            <tr>
              <td>
                <span class="job-id-btn" @click="toggleJobLogs(job.id)">{{ job.id }}</span>
              </td>
              <td>
                <template v-if="job.chesscom_user">
                  <router-link class="user-link" :to="userPath(job)">{{ job.chesscom_user }}</router-link>
                </template>
                <template v-if="job.chesscom_user && job.lichess_user"> / </template>
                <template v-if="job.lichess_user">
                  <router-link class="user-link" :to="userPath(job)">{{ job.lichess_user }}</router-link>
                </template>
              </td>
              <td>
                <span class="badge" :class="'badge--' + job.status">{{ job.status }}</span>
              </td>
              <td>
                <div class="mini-progress">
                  <div class="mini-progress__fill" :style="{ width: (job.progress_pct || 0) + '%' }"></div>
                </div>
                {{ job.progress_pct || 0 }}%
              </td>
              <td>{{ job.total_games || '-' }}</td>
              <td>{{ formatDuration(job.duration_seconds) }}</td>
              <td>{{ formatDate(job.created_at) }}</td>
              <td>
                <span v-if="job.error_message" class="error-msg">{{ truncate(job.error_message, 120) }}</span>
                <span v-else-if="job.message" class="msg">{{ truncate(job.message, 120) }}</span>
              </td>
            </tr>
            <!-- Log detail row -->
            <tr v-if="expandedJobs.has(job.id)" class="log-row">
              <td colspan="8">
                <pre class="log-content" v-html="jobLogsHtml[job.id] || 'Loading logs...'"></pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Service Logs -->
    <div class="service-logs">
      <span class="service-logs__label">Service Logs (run from host):</span>
      <button v-for="svc in services" :key="svc" class="admin-btn admin-btn--sm" @click="copyCmd(svc)">{{ svc }}</button>
      <span v-if="copyMsg" class="copy-msg">{{ copyMsg }}</span>
    </div>
  </AdminLayout>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import AdminLayout from '../components/layout/AdminLayout.vue'
import StatCard from '../components/ui/StatCard.vue'
import { fetchAdminJobs, fetchJobLogs, fetchFlaskLogs } from '../api'

const jobs = ref([])
const activeFilter = ref('all')
const showFlaskLogs = ref(false)
const flaskLogLevel = ref('')
const flaskLogsLoading = ref(false)
const flaskLogsEl = ref(null)
const expandedJobs = ref(new Set())
const jobLogsHtml = ref({})
const jobLogsLoaded = ref(new Set())
const copyMsg = ref('')
let refreshTimer = null

const services = ['Worker', 'Web', 'Postgres', 'Redis', 'Flower']

const filterTabs = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'pending', label: 'Queued' },
  { key: 'complete', label: 'Complete' },
  { key: 'failed', label: 'Failed' },
]

function jobFilterStatus(job) {
  if (job.status === 'fetching' || job.status === 'analyzing') return 'active'
  return job.status
}

const activeCnt = computed(() => jobs.value.filter(j => j.status === 'fetching' || j.status === 'analyzing').length)
const queuedCnt = computed(() => jobs.value.filter(j => j.status === 'pending').length)
const completeCnt = computed(() => jobs.value.filter(j => j.status === 'complete').length)
const failedCnt = computed(() => jobs.value.filter(j => j.status === 'failed').length)

const filteredJobs = computed(() => {
  if (activeFilter.value === 'all') return jobs.value
  return jobs.value.filter(j => jobFilterStatus(j) === activeFilter.value)
})

function userPath(job) {
  const parts = []
  parts.push(job.chesscom_user || '-')
  if (job.lichess_user) parts.push(job.lichess_user)
  return '/u/' + parts.join('/')
}

function formatDuration(seconds) {
  if (seconds == null) return '-'
  if (seconds >= 3600) return Math.floor(seconds / 3600) + 'h ' + Math.floor((seconds % 3600) / 60) + 'm'
  if (seconds >= 60) return Math.floor(seconds / 60) + 'm ' + (seconds % 60) + 's'
  return seconds + 's'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return months[d.getMonth()] + ' ' + String(d.getDate()).padStart(2, '0') + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0')
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function escapeHtml(str) {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

function colorLogLines(logs) {
  if (!logs.length) return '(no logs recorded for this job)'
  return logs.map(l => {
    const cls = 'log-level-' + l.level
    const ts = l.logged_at || ''
    return `<span class="${cls}">${escapeHtml(ts)} [${escapeHtml(l.level)}] ${escapeHtml(l.message)}</span>`
  }).join('\n')
}

async function toggleJobLogs(jobId) {
  const expanded = new Set(expandedJobs.value)
  if (expanded.has(jobId)) {
    expanded.delete(jobId)
    expandedJobs.value = expanded
    return
  }
  expanded.add(jobId)
  expandedJobs.value = expanded

  if (!jobLogsLoaded.value.has(jobId)) {
    try {
      const logs = await fetchJobLogs(jobId)
      jobLogsHtml.value = { ...jobLogsHtml.value, [jobId]: colorLogLines(logs) }
      jobLogsLoaded.value.add(jobId)
    } catch (err) {
      jobLogsHtml.value = { ...jobLogsHtml.value, [jobId]: 'Failed to load logs: ' + escapeHtml(String(err)) }
    }
  }
}

async function loadJobs() {
  try {
    const data = await fetchAdminJobs()
    jobs.value = data.jobs || []
  } catch (err) {
    console.error('Failed to load jobs:', err)
  }
  scheduleRefresh()
}

function scheduleRefresh() {
  clearTimeout(refreshTimer)
  const hasActive = jobs.value.some(j => ['pending', 'fetching', 'analyzing'].includes(j.status))
  if (hasActive) {
    refreshTimer = setTimeout(loadJobs, 30000)
  }
}

function toggleFlaskLogs() {
  showFlaskLogs.value = !showFlaskLogs.value
  if (showFlaskLogs.value) {
    loadFlaskLogs()
  }
}

async function loadFlaskLogs() {
  flaskLogsLoading.value = true
  try {
    const params = { limit: 300 }
    if (flaskLogLevel.value) params.level = flaskLogLevel.value
    const logs = await fetchFlaskLogs(params)
    await nextTick()
    if (flaskLogsEl.value) {
      if (!logs.length) {
        flaskLogsEl.value.textContent = '(no logs)'
      } else {
        flaskLogsEl.value.innerHTML = logs.map(l => {
          const cls = 'log-level-' + l.level
          return `<span class="${cls}">${escapeHtml(l.timestamp)} [${escapeHtml(l.level)}] ${escapeHtml(l.message)}</span>`
        }).join('\n')
        flaskLogsEl.value.scrollTop = flaskLogsEl.value.scrollHeight
      }
    }
  } catch (err) {
    if (flaskLogsEl.value) flaskLogsEl.value.textContent = 'Failed: ' + err
  }
  flaskLogsLoading.value = false
}

function copyCmd(service) {
  const cmd = 'docker compose logs --tail 500 -f ' + service.toLowerCase()
  navigator.clipboard.writeText(cmd).then(() => {
    copyMsg.value = 'Copied: ' + cmd
    setTimeout(() => { copyMsg.value = '' }, 2500)
  })
}

onMounted(loadJobs)
onUnmounted(() => clearTimeout(refreshTimer))
</script>

<style scoped>
.subtitle {
  color: #94a3b8;
  font-size: 0.9rem;
  margin-bottom: 24px;
}

/* Admin buttons */
.admin-btn {
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 0.85rem;
  text-decoration: none;
  display: inline-block;
}
.admin-btn:hover,
.admin-btn--active {
  border-color: #818cf8;
  color: #818cf8;
}
.admin-btn--sm {
  padding: 4px 12px;
  font-size: 0.8rem;
}

.admin-select {
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 0.8rem;
}

/* Flask Logs Panel */
.flask-logs-panel {
  margin-bottom: 24px;
}
.flask-logs-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.flask-logs-panel__controls {
  display: flex;
  gap: 8px;
  align-items: center;
}
.flask-logs-panel__label {
  color: #94a3b8;
  font-size: 0.85rem;
  font-weight: 600;
}

/* Log content (shared between flask logs and job logs) */
.log-content {
  background: #0c0f1a;
  color: #a5b4c8;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  padding: 12px 16px;
  margin: 0;
  max-height: 500px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  border-left: 3px solid #818cf8;
  border-radius: 0;
}
.log-content :deep(.log-level-ERROR) { color: #f87171; }
.log-content :deep(.log-level-WARNING) { color: #fbbf24; }
.log-content :deep(.log-level-INFO) { color: #4ade80; }
.log-content :deep(.log-level-DEBUG) { color: #94a3b8; }

/* Summary cards */
.summary {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.summary :deep(.stat-card) {
  background: #1e293b;
  border-color: #334155;
}
.summary :deep(.stat-card__label) {
  color: #94a3b8;
}
.stat--active :deep(.stat-card__value) { color: #34d399; }
.stat--queued :deep(.stat-card__value) { color: #fbbf24; }
.stat--complete :deep(.stat-card__value) { color: #60a5fa; }
.stat--failed :deep(.stat-card__value) { color: #f87171; }
.stat--total :deep(.stat-card__value) { color: #94a3b8; }

/* Filter tabs */
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.filter-btn {
  background: #1e293b;
  color: #94a3b8;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.85rem;
}
.filter-btn:hover {
  border-color: #818cf8;
  color: #e2e8f0;
}
.filter-btn--active {
  background: #818cf8;
  color: #fff;
  border-color: #818cf8;
}

/* Table */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th {
  text-align: left;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  padding: 10px 12px;
  border-bottom: 2px solid #334155;
}
td {
  padding: 10px 12px;
  border-bottom: 1px solid #334155;
  vertical-align: top;
}
tr:hover td { background: rgba(255,255,255,0.03); }

/* Status badges */
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}
.badge--pending { background: #422006; color: #fbbf24; }
.badge--fetching { background: #172554; color: #60a5fa; }
.badge--analyzing { background: #1e1b4b; color: #a78bfa; }
.badge--complete { background: #052e16; color: #34d399; }
.badge--failed { background: #450a0a; color: #f87171; }

.user-link {
  color: #818cf8;
  text-decoration: none;
}
.user-link:hover { text-decoration: underline; }

.job-id-btn {
  color: #818cf8;
  cursor: pointer;
  font-weight: 600;
}
.job-id-btn:hover { text-decoration: underline; }

.error-msg {
  color: #f87171;
  font-size: 0.8rem;
  max-width: 250px;
  word-break: break-word;
}
.msg {
  color: #94a3b8;
  font-size: 0.8rem;
  max-width: 250px;
}

/* Mini progress bar */
.mini-progress {
  background: #334155;
  border-radius: 3px;
  height: 6px;
  width: 80px;
  display: inline-block;
  vertical-align: middle;
}
.mini-progress__fill {
  background: #818cf8;
  height: 100%;
  border-radius: 3px;
}

/* Log detail row */
.log-row td {
  padding: 0;
}

/* Service logs */
.service-logs {
  margin-top: 24px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.service-logs__label {
  color: #94a3b8;
  font-size: 0.85rem;
  margin-right: 8px;
}
.copy-msg {
  color: #34d399;
  font-size: 0.8rem;
  margin-left: 8px;
}

@media (max-width: 768px) {
  .summary { flex-direction: column; }
}
</style>
