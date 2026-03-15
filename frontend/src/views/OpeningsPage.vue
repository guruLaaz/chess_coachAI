<template>
  <AppLayout>
    <template #sidebar>
      <TheSidebar
        :user-path="userPath"
        :chesscom-user="data?.chesscom_user || ''"
        :lichess-user="data?.lichess_user || ''"
        page="openings"
      />
    </template>

    <template v-if="loading">
      <div class="openings-spinner">
        <span class="openings-spinner__icon" />
        {{ t('loading_board') }}
      </div>
    </template>

    <template v-else-if="data">
      <!-- Header -->
      <h1>
        Chess Coach:
        <UserBadges
          :chesscom-user="data.chesscom_user"
          :lichess-user="data.lichess_user"
        />
      </h1>

      <div class="openings-subtitle" v-if="filterEco">
        {{ t('opening_deviations_for', { count: data.items.length, eco: filterEco, color: filterColor }) }}
        &mdash; {{ t('endgame_subtitle_prefix', 0, { default: 'sorted by' }) }}
        <BaseSelect
          :model-value="filters.sort"
          :options="sortOptions"
          class="openings-sort-select"
          @update:model-value="onSortChange"
        />
      </div>
      <div class="openings-subtitle" v-else>
        {{ allItems.length }} {{ t('endgame_subtitle_prefix') }}
        &mdash; sorted by
        <BaseSelect
          :model-value="filters.sort"
          :options="sortOptions"
          class="openings-sort-select"
          @update:model-value="onSortChange"
        />
      </div>

      <!-- Stats bar -->
      <div class="openings-stats-bar">
        <div class="openings-stat-games">
          <div>
            <div class="openings-stat-label">{{ t('stat_total_games') }}</div>
            <div class="openings-stat-value">{{ data.total_games_analyzed.toLocaleString() }}</div>
            <div v-if="data.new_games_analyzed > 0" class="openings-stat-delta openings-stat-delta--positive">
              <svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 2 L10 7 H7 V10 H5 V7 H2 Z" fill="currentColor"/></svg>
              {{ t(data.new_games_analyzed === 1 ? 'stat_new_games_analyzed' : 'stat_new_games_analyzed_plural', { count: data.new_games_analyzed }) }}
            </div>
            <div v-else class="openings-stat-delta openings-stat-delta--neutral">
              {{ t('stat_no_new_games') }}
            </div>
          </div>
          <div class="openings-stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <ellipse cx="12" cy="5" rx="9" ry="3"/>
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
          </div>
        </div>
        <StatCard :label="t('stat_avg_eval')" :value="'±' + data.avg_eval_loss" />
        <StatCard :label="t('stat_theory')" :value="data.theory_knowledge_pct + '%'" />
        <StatCard :label="t('stat_accuracy')" :donut="true" :donut-pct="data.accuracy_pct" />
      </div>

      <!-- Card list -->
      <template v-if="allItems.length > 0">
        <template v-if="hasResults">
          <OpeningCard
            v-for="(item, idx) in visibleItems"
            :key="idx"
            :item="item"
            :user-path="userPath"
          />
        </template>
        <EmptyState v-else :title="t('no_filter_results')" />
      </template>
      <EmptyState
        v-else
        icon="&#9816;"
        :title="t('empty_title')"
        :description="t('empty_desc')"
      />
    </template>
  </AppLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchOpeningsReport, fetchOpeningsFiltered } from '@/api'
import { useFiltersStore } from '@/stores/filters'
import { useFiltering } from '@/composables/useFiltering'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'
import AppLayout from '@/components/layout/AppLayout.vue'
import TheSidebar from '@/components/sidebar/TheSidebar.vue'
import UserBadges from '@/components/ui/UserBadges.vue'
import StatCard from '@/components/ui/StatCard.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import OpeningCard from '@/components/openings/OpeningCard.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const filters = useFiltersStore()

const userPath = computed(() => route.params.userPath || '')
const filterEco = computed(() => route.params.eco || null)
const filterColor = computed(() => route.params.color || null)

const data = ref(null)
const loading = ref(true)
const allItems = ref([])

const sortOptions = [
  { value: 'eval-loss', label: t('sort_biggest') },
  { value: 'loss-pct', label: t('sort_losspct') },
]

function onSortChange(val) {
  filters.sort = val
  filters.saveToSessionStorage()
}

// Filtering & pagination
const { filteredItems, hasResults } = useFiltering(allItems)
const { visibleItems, reset: resetScroll } = useInfiniteScroll(filteredItems, 10)

// Reset scroll when filters change
watch(filteredItems, () => {
  resetScroll()
})

async function loadData() {
  loading.value = true
  try {
    let response
    if (filterEco.value && filterColor.value) {
      response = await fetchOpeningsFiltered(userPath.value, filterEco.value, filterColor.value)
    } else {
      response = await fetchOpeningsReport(userPath.value)
    }

    if (response.redirect) {
      router.push(response.redirect)
      return
    }
    if (response.no_games) {
      const query = {}
      if (response.chesscom_user) query.chesscom = response.chesscom_user
      if (response.lichess_user) query.lichess = response.lichess_user
      router.push({ path: '/no-games', query })
      return
    }

    data.value = response
    allItems.value = response.items || []

    // Restore filters or auto-escalate TC
    await nextTick()
    const restored = filters.restoreFromSessionStorage()
    if (!restored && !hasResults.value && allItems.value.length > 0) {
      // Try enabling bullet
      if (!filters.timeControls.includes('bullet')) {
        filters.timeControls = [...filters.timeControls, 'bullet']
      }
      await nextTick()
      if (!hasResults.value) {
        // Try enabling daily
        if (!filters.timeControls.includes('daily')) {
          filters.timeControls = [...filters.timeControls, 'daily']
        }
      }
      filters.saveToSessionStorage()
    }
  } catch (err) {
    console.error('Failed to load openings data:', err)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

// Reload when route changes (e.g., navigating between filtered and unfiltered)
watch(() => [route.params.userPath, route.params.eco, route.params.color], () => {
  loadData()
})
</script>

<style scoped>
h1 {
  font-size: 1.8rem;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.openings-subtitle {
  color: var(--text-secondary);
  margin-bottom: 32px;
  font-size: 0.95rem;
}
.openings-sort-select {
  display: inline-block;
  width: auto;
}
.openings-sort-select :deep(.base-select__field) {
  width: auto;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.9rem;
}
.openings-stats-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 28px;
}
.openings-stat-games {
  flex: 1;
  min-width: 120px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 20px;
  text-align: left;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.openings-stat-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
}
.openings-stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 4px;
}
.openings-stat-delta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  margin-top: 4px;
}
.openings-stat-delta--positive {
  color: #16a34a;
}
.openings-stat-delta--neutral {
  color: #94a3b8;
}
.openings-stat-icon {
  width: 40px;
  height: 40px;
  background: var(--badge-bg);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.openings-stat-icon svg {
  width: 22px;
  height: 22px;
}
.openings-spinner {
  text-align: center;
  padding: 60px 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}
.openings-spinner__icon {
  display: block;
  width: 32px;
  height: 32px;
  margin: 0 auto 12px;
  border: 3px solid var(--border);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@media (max-width: 768px) {
  .openings-stats-bar {
    flex-direction: column;
  }
}
</style>
