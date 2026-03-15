<template>
  <AdminLayout>
    <template #header>
      <h1>Feedback</h1>
      <p class="subtitle">Chess CoachAI — Bug Reports &amp; Contact Submissions</p>
    </template>
    <template #actions>
      <router-link to="/admin/jobs" class="admin-btn">Jobs Dashboard</router-link>
      <button class="admin-btn" @click="loadEntries">Refresh</button>
    </template>

    <!-- Summary Cards -->
    <div class="summary">
      <StatCard :value="entries.length" label="Total" class="stat--total" />
      <StatCard :value="bugCnt" label="Bug Reports" class="stat--bug" />
      <StatCard :value="contactCnt" label="Contact" class="stat--contact" />
    </div>

    <!-- Feedback Table -->
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Email</th>
            <th>Details</th>
            <th>Page</th>
            <th>Date</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="e in entries" :key="e.id">
            <tr>
              <td>{{ e.id }}</td>
              <td><span class="badge" :class="'badge--' + e.type">{{ e.type }}</span></td>
              <td>{{ e.email }}</td>
              <td class="details-cell">{{ truncate(e.details, 200) }}</td>
              <td class="url-cell">{{ e.page_url }}</td>
              <td>{{ formatDate(e.created_at) }}</td>
              <td class="actions-cell">
                <span
                  v-if="e.screenshot"
                  class="toggle-link"
                  @click="toggleScreenshot(e.id)"
                >Screenshot</span>
                <span
                  v-if="hasLogs(e)"
                  class="toggle-link"
                  @click="toggleLogs(e.id, e.console_logs)"
                >Logs</span>
              </td>
            </tr>
            <!-- Screenshot row -->
            <tr v-if="expandedScreenshots.has(e.id)" class="expand-row">
              <td colspan="7">
                <div class="screenshot-content">
                  <img :src="e.screenshot" :alt="'Screenshot for feedback #' + e.id">
                </div>
              </td>
            </tr>
            <!-- Logs row -->
            <tr v-if="expandedLogs.has(e.id)" class="expand-row">
              <td colspan="7">
                <pre class="log-content" v-html="parsedLogs[e.id] || '(no console logs)'"></pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </AdminLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AdminLayout from '../components/layout/AdminLayout.vue'
import StatCard from '../components/ui/StatCard.vue'
import { fetchAdminFeedback } from '../api'

const entries = ref([])
const expandedScreenshots = ref(new Set())
const expandedLogs = ref(new Set())
const parsedLogs = ref({})
const logsLoaded = ref(new Set())

const bugCnt = computed(() => entries.value.filter(e => e.type === 'bug').length)
const contactCnt = computed(() => entries.value.filter(e => e.type === 'contact').length)

function hasLogs(entry) {
  return entry.console_logs && entry.console_logs !== '[]'
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return months[d.getMonth()] + ' ' + String(d.getDate()).padStart(2, '0') + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0')
}

function escapeHtml(str) {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

function toggleScreenshot(id) {
  const expanded = new Set(expandedScreenshots.value)
  if (expanded.has(id)) {
    expanded.delete(id)
  } else {
    expanded.add(id)
  }
  expandedScreenshots.value = expanded
}

function toggleLogs(id, consoleLogs) {
  const expanded = new Set(expandedLogs.value)
  if (expanded.has(id)) {
    expanded.delete(id)
    expandedLogs.value = expanded
    return
  }
  expanded.add(id)
  expandedLogs.value = expanded

  if (!logsLoaded.value.has(id)) {
    try {
      const logs = JSON.parse(consoleLogs)
      if (!logs.length) {
        parsedLogs.value = { ...parsedLogs.value, [id]: '(no console logs)' }
      } else {
        const html = logs.map(l => {
          const cls = l.level === 'error' ? 'log-error' : l.level === 'warn' ? 'log-warn' : ''
          return `<span class="${cls}">${escapeHtml(l.ts)} [${escapeHtml(l.level.toUpperCase())}] ${escapeHtml(l.msg)}</span>`
        }).join('\n')
        parsedLogs.value = { ...parsedLogs.value, [id]: html }
      }
    } catch {
      parsedLogs.value = { ...parsedLogs.value, [id]: '(could not parse logs)' }
    }
    logsLoaded.value.add(id)
  }
}

async function loadEntries() {
  try {
    const data = await fetchAdminFeedback()
    entries.value = data.entries || []
  } catch (err) {
    console.error('Failed to load feedback:', err)
  }
}

onMounted(loadEntries)
</script>

<style scoped>
.subtitle {
  color: #94a3b8;
  font-size: 0.9rem;
  margin-bottom: 24px;
}

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
.admin-btn:hover {
  border-color: #818cf8;
  color: #818cf8;
}

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
.stat--total :deep(.stat-card__value) { color: #e2e8f0; }
.stat--bug :deep(.stat-card__value) { color: #f87171; }
.stat--contact :deep(.stat-card__value) { color: #60a5fa; }

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

/* Badges */
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}
.badge--bug { background: #450a0a; color: #f87171; }
.badge--contact { background: #172554; color: #60a5fa; }

.details-cell { max-width: 350px; word-break: break-word; }
.url-cell { max-width: 200px; word-break: break-all; color: #94a3b8; font-size: 0.8rem; }

.actions-cell {
  display: flex;
  gap: 8px;
}
.toggle-link {
  color: #818cf8;
  cursor: pointer;
  font-size: 0.8rem;
}
.toggle-link:hover { text-decoration: underline; }

/* Expandable rows */
.expand-row td { padding: 0; }
.screenshot-content {
  padding: 12px 16px;
  border-left: 3px solid #818cf8;
}
.screenshot-content img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  border: 1px solid #334155;
}

.log-content {
  background: #0c0f1a;
  color: #a5b4c8;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  padding: 12px 16px;
  margin: 0;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  border-left: 3px solid #818cf8;
}
.log-content :deep(.log-warn) { color: #fbbf24; }
.log-content :deep(.log-error) { color: #f87171; }

@media (max-width: 768px) {
  .summary { flex-direction: column; }
}
</style>
