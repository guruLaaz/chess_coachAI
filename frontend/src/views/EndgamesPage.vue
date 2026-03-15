<template>
  <AppLayout>
    <template #sidebar>
      <TheSidebar
        :user-path="userPath"
        :chesscom-user="chesscomUser"
        :lichess-user="lichessUser"
        page="endgames"
      />
    </template>

    <div v-if="loading" class="loading-state">{{ t('status_checking_msg') }}</div>

    <template v-else-if="data">
      <!-- Header -->
      <h1>
        Chess Coach:
        <UserBadges :chesscom-user="chesscomUser" :lichess-user="lichessUser" />
      </h1>
      <div class="subtitle">
        {{ t('eg_performance') }} &mdash; {{ t('eg_sorted_by') }}
        <BaseSelect
          v-model="egSort"
          :options="sortOptions"
          class="sort-select-inline"
        />
      </div>

      <!-- Stats bar -->
      <div class="stats-bar">
        <StatCard :label="t('eg_stat_games')" :value="formatNumber(data.eg_total_games)" />
        <StatCard :label="t('eg_stat_types')" :value="data.eg_types_count" />
        <StatCard :label="t('eg_stat_winrate')" :donut="true" :donut-pct="data.eg_win_pct" />
      </div>

      <!-- Card list -->
      <template v-if="data.stats && data.stats.length > 0">
        <EndgameCard
          v-for="stat in visibleItems"
          :key="stat.type + '-' + stat.balance + '-' + stat.definition"
          :stat="stat"
          :user-path="userPath"
        />
        <EmptyState
          v-if="!hasResults"
          :title="t('eg_no_filter_results')"
        />
      </template>
      <EmptyState
        v-else
        :title="t('eg_no_endgames_title')"
        :description="t('eg_no_endgames_desc')"
      />
    </template>
  </AppLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchEndgamesReport } from '../api'
import { useFiltersStore } from '../stores/filters'
import { useEndgameFiltering } from '../composables/useEndgameFiltering'
import { useInfiniteScroll } from '../composables/useInfiniteScroll'
import AppLayout from '../components/layout/AppLayout.vue'
import TheSidebar from '../components/sidebar/TheSidebar.vue'
import UserBadges from '../components/ui/UserBadges.vue'
import BaseSelect from '../components/ui/BaseSelect.vue'
import StatCard from '../components/ui/StatCard.vue'
import EndgameCard from '../components/endgames/EndgameCard.vue'
import EmptyState from '../components/ui/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const filters = useFiltersStore()

const loading = ref(true)
const data = ref(null)
const chesscomUser = ref('')
const lichessUser = ref('')

const userPath = computed(() => route.params.userPath || '')

const egSort = ref('total')

const sortOptions = computed(() => [
  { value: 'total', label: t('eg_sort_games') },
  { value: 'win_pct', label: t('eg_sort_win_pct') },
  { value: 'loss_pct', label: t('eg_sort_loss_pct') },
  { value: 'draw_pct', label: t('eg_sort_draw_pct') },
])

// Sync egSort into filter store so useEndgameFiltering picks it up
watch(egSort, (val) => { filters.sort = val })

const rawStats = computed(() => {
  if (!data.value || !data.value.stats) return []
  // Only show stats for default definition
  const def = data.value.default_definition || 'minor-or-queen'
  return data.value.stats.filter(s => s.definition === def)
})

const { filteredStats, hasResults } = useEndgameFiltering(rawStats)
const { visibleItems, reset } = useInfiniteScroll(filteredStats, 10)

// Reset scroll when filters change
watch(filteredStats, () => reset())

async function loadData() {
  loading.value = true
  try {
    const result = await fetchEndgamesReport(userPath.value)

    // Handle redirects
    if (result.redirect) {
      router.push(result.redirect)
      return
    }
    if (result.no_games) {
      const query = {}
      if (result.chesscom_user) query.chesscom = result.chesscom_user
      if (result.lichess_user) query.lichess = result.lichess_user
      router.push({ path: '/no-games', query })
      return
    }

    data.value = result
    chesscomUser.value = result.chesscom_user || ''
    lichessUser.value = result.lichess_user || ''

    // Restore filter state
    if (!filters.restoreFromSessionStorage()) {
      egSort.value = 'total'
    }
  } catch (e) {
    router.push('/')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

watch(userPath, loadData)

function formatNumber(n) {
  if (n == null) return '0'
  return n.toLocaleString()
}
</script>

<style scoped>
.loading-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}
.subtitle {
  color: var(--text-secondary);
  margin-bottom: 24px;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sort-select-inline {
  display: inline-block;
  width: auto;
}
.sort-select-inline :deep(.base-select__field) {
  padding: 4px 8px;
  font-size: 0.9rem;
  width: auto;
}
.sort-select-inline :deep(.base-select__label) {
  display: none;
}
.stats-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}
@media (max-width: 768px) {
  .stats-bar { flex-direction: column; }
}
</style>
