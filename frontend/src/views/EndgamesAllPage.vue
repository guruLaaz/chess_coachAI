<template>
  <AppLayout>
    <template #sidebar>
      <TheSidebar
        :user-path="userPath"
        :chesscom-user="chesscomUser"
        :lichess-user="lichessUser"
        page="endgames_all"
        :show-filters="false"
      />
    </template>

    <div v-if="loading" class="loading-state">{{ t('status_checking_msg') }}</div>

    <template v-else-if="data">
      <!-- Back link -->
      <router-link class="back-link" :to="`/u/${userPath}/endgames`">
        {{ t('eg_back') }}
      </router-link>

      <!-- Header -->
      <h1>
        {{ data.eg_type }}
        <span class="balance-badge" :class="`balance-badge--${data.balance}`">{{ data.balance }}</span>
      </h1>
      <div class="subtitle">
        {{ filteredGames.length }} {{ t('eg_games_suffix') }} &mdash;
        {{ t('eg_definition') }} {{ data.definition }} &mdash;
        {{ t('eg_sorted_recent') }}
      </div>

      <!-- Time class filter -->
      <div class="filter-row">
        <DropdownFilter :label="t('eg_time_class')">
          <ToggleGroup
            v-model="selectedTCs"
            :options="tcOptions"
            :min-selected="0"
            :columns="2"
          />
        </DropdownFilter>
      </div>

      <!-- Game rows -->
      <template v-if="data.games && data.games.length > 0">
        <div
          v-for="(g, idx) in visibleItems"
          :key="idx"
          class="game-row"
        >
          <div v-if="g.fen" class="game-board">
            <ChessBoard
              :fen="g.fen"
              :color="g.my_color || 'white'"
              :size="180"
            />
          </div>
          <div class="game-info">
            <div class="game-badges">
              <EvalBadge
                :value="(g.my_result || 'draw').toUpperCase()"
                :type="g.result_class === 'win' ? 'good' : g.result_class === 'loss' ? 'bad' : 'neutral'"
              />
              <EvalBadge
                v-if="g.material_diff != null"
                :value="'material ' + (g.material_diff > 0 ? '+' : '') + g.material_diff"
                :type="g.material_diff > 0 ? 'good' : g.material_diff < 0 ? 'bad' : 'neutral'"
              />
              <span v-if="g.my_clock_fmt" class="clock-badge">
                <span class="clock-icon">⏱</span>
                <span class="clock-you">{{ g.my_clock_fmt }}</span>
                <span v-if="g.opp_clock_fmt" class="clock-opp">{{ g.opp_clock_fmt }}</span>
              </span>
            </div>
            <a
              v-if="g.deep_link"
              class="game-link"
              :href="g.deep_link"
              target="_blank"
              rel="noopener"
            >{{ t('eg_view_game') }} →</a>
          </div>
        </div>

        <EmptyState
          v-if="filteredGames.length === 0"
          :title="t('eg_no_games_filter')"
        />
      </template>
      <EmptyState
        v-else
        :title="t('eg_no_games_title')"
        :description="t('eg_no_games_desc')"
      />
    </template>
  </AppLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchEndgamesAll } from '../api'
import { useInfiniteScroll } from '../composables/useInfiniteScroll'
import AppLayout from '../components/layout/AppLayout.vue'
import TheSidebar from '../components/sidebar/TheSidebar.vue'
import DropdownFilter from '../components/ui/DropdownFilter.vue'
import ToggleGroup from '../components/ui/ToggleGroup.vue'
import ChessBoard from '../components/ChessBoard.vue'
import EvalBadge from '../components/ui/EvalBadge.vue'
import EmptyState from '../components/ui/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(true)
const data = ref(null)
const chesscomUser = ref('')
const lichessUser = ref('')
const selectedTCs = ref(['bullet', 'blitz', 'rapid', 'daily'])

const userPath = computed(() => route.params.userPath || '')

const tcOptions = computed(() => [
  { value: 'bullet', label: t('tc_bullet') },
  { value: 'blitz', label: t('tc_blitz') },
  { value: 'rapid', label: t('tc_rapid') },
  { value: 'daily', label: t('tc_daily') },
])

const filteredGames = computed(() => {
  if (!data.value || !data.value.games) return []
  const tcSet = new Set(selectedTCs.value)
  if (tcSet.size === 0) return data.value.games
  return data.value.games.filter(g => {
    if (!g.time_class) return true
    return tcSet.has(g.time_class)
  })
})

const { visibleItems, reset } = useInfiniteScroll(filteredGames, 10)

// Reset scroll on filter change
watch(filteredGames, () => reset())

async function loadData() {
  loading.value = true
  try {
    const params = {
      def: route.query.def || 'minor-or-queen',
      type: route.query.type || '',
      balance: route.query.balance || '',
    }
    const result = await fetchEndgamesAll(userPath.value, params)

    if (result.redirect) {
      router.push(result.redirect)
      return
    }

    data.value = result
    chesscomUser.value = result.chesscom_user || ''
    lichessUser.value = result.lichess_user || ''
  } catch (e) {
    router.push('/')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
watch(userPath, loadData)
</script>

<style scoped>
.loading-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}
.back-link {
  display: inline-block;
  margin-bottom: 16px;
  color: #2563eb;
  text-decoration: none;
  font-size: 0.9rem;
}
.back-link:hover { text-decoration: underline; }
h1 {
  font-size: 1.6rem;
  margin-bottom: 8px;
}
.subtitle {
  color: var(--text-secondary);
  margin-bottom: 24px;
  font-size: 0.95rem;
}
.balance-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
}
.balance-badge--equal { background: var(--badge-bg); color: var(--text-secondary); }
.balance-badge--up { background: #f0fdf4; color: #16a34a; }
.balance-badge--down { background: #fef2f2; color: #dc2626; }
[data-theme="dark"] .balance-badge--up { background: rgba(22, 163, 74, 0.15); }
[data-theme="dark"] .balance-badge--down { background: rgba(220, 38, 38, 0.15); }
.filter-row {
  margin-bottom: 16px;
}
.game-row {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  display: flex;
  align-items: flex-start;
  gap: 20px;
  box-shadow: var(--card-shadow);
}
.game-board {
  flex-shrink: 0;
  text-align: center;
}
.game-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.game-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.clock-badge {
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.clock-icon { color: var(--text-secondary); }
.clock-you {
  background: #dcfce7;
  color: #16a34a;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
}
.clock-opp {
  background: var(--badge-bg);
  color: var(--text-secondary);
  padding: 1px 5px;
  border-radius: 4px;
}
.game-link {
  font-size: 0.85rem;
  color: #2563eb;
  text-decoration: none;
}
.game-link:hover { text-decoration: underline; color: #1d4ed8; }
@media (max-width: 768px) {
  .game-row {
    flex-direction: column;
    align-items: center;
  }
}
</style>
