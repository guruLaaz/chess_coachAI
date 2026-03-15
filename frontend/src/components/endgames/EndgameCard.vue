<template>
  <div class="eg-card" :style="{ borderLeftColor: borderColor }">
    <div class="eg-card__header">
      <span class="eg-card__type">{{ stat.type }}</span>
      <span class="eg-card__balance" :class="`eg-card__balance--${stat.balance}`">{{ stat.balance }}</span>
      <span class="eg-card__games">{{ stat.total }} {{ t('eg_games_suffix') }}</span>
      <span class="eg-card__pct" :class="winClass">W {{ stat.win_pct }}%</span>
      <span class="eg-card__pct" :class="lossClass">L {{ stat.loss_pct }}%</span>
      <span class="eg-card__pct eg-card__pct--neutral">D {{ stat.draw_pct }}%</span>
      <span v-if="stat.avg_my_clock != null" class="eg-card__clock">
        ⏱ <span class="eg-card__clock-you">{{ formatClock(stat.avg_my_clock) }}</span>
        <span v-if="stat.avg_opp_clock != null" class="eg-card__clock-opp">{{ formatClock(stat.avg_opp_clock) }}</span>
      </span>
    </div>
    <div v-if="stat.example" class="eg-card__body">
      <div class="eg-card__board-panel">
        <h4 class="eg-card__example-heading">
          <a
            v-if="stat.example.url"
            class="eg-card__game-link"
            :href="stat.example.url"
            target="_blank"
            rel="noopener"
          >{{ exampleLabel }} →</a>
          <span v-else>{{ exampleLabel }}</span>
        </h4>
        <ChessBoard
          :fen="stat.example.fen"
          :color="stat.example.color || 'white'"
          :size="180"
        />
        <EvalBadge
          v-if="stat.example.diff != null"
          :value="'material ' + (stat.example.diff > 0 ? '+' : '') + stat.example.diff"
          :type="stat.example.diff > 0 ? 'good' : stat.example.diff < 0 ? 'bad' : 'neutral'"
        />
      </div>
      <router-link class="eg-card__all-link" :to="allGamesLink">
        {{ t('eg_show_all') }} →
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ChessBoard from '../ChessBoard.vue'
import EvalBadge from '../ui/EvalBadge.vue'
import { formatClock } from '../../composables/useEndgameFiltering'

const props = defineProps({
  stat: { type: Object, required: true },
  userPath: { type: String, required: true },
})

const { t } = useI18n()

const BALANCE_COLORS = {
  up: '#22c55e',
  down: '#ef4444',
  equal: '#94a3b8',
}

const borderColor = computed(() => BALANCE_COLORS[props.stat.balance] || '#94a3b8')

const winClass = computed(() => {
  const pct = props.stat.win_pct
  return pct >= 50 ? 'eg-card__pct--good' : pct < 30 ? 'eg-card__pct--bad' : 'eg-card__pct--neutral'
})

const lossClass = computed(() => {
  const pct = props.stat.loss_pct
  return pct >= 50 ? 'eg-card__pct--bad' : pct < 20 ? 'eg-card__pct--good' : 'eg-card__pct--neutral'
})

const exampleLabel = computed(() => {
  const ex = props.stat.example
  const label = t('eg_example_game')
  const meta = []
  if (ex.opp) meta.push('vs ' + ex.opp)
  if (ex.tc) meta.push(ex.tc)
  if (ex.date) meta.push(ex.date)
  return meta.length ? `${label} (${meta.join(', ')})` : label
})

const allGamesLink = computed(() => {
  const s = props.stat
  return `/u/${props.userPath}/endgames/all?def=${encodeURIComponent(s.definition)}&type=${encodeURIComponent(s.type)}&balance=${encodeURIComponent(s.balance)}`
})
</script>

<style scoped>
.eg-card {
  background: var(--card-bg);
  border-left: 4px solid #94a3b8;
  padding: 20px 24px;
  margin-bottom: 16px;
  border-radius: 12px;
  box-shadow: var(--card-shadow);
}
.eg-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.eg-card__type {
  font-weight: 700;
  font-size: 1.05rem;
  color: var(--text-primary);
}
.eg-card__balance {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
}
.eg-card__balance--equal { background: var(--badge-bg); color: var(--text-secondary); }
.eg-card__balance--up { background: #f0fdf4; color: #16a34a; }
.eg-card__balance--down { background: #fef2f2; color: #dc2626; }
[data-theme="dark"] .eg-card__balance--up { background: rgba(22, 163, 74, 0.15); }
[data-theme="dark"] .eg-card__balance--down { background: rgba(220, 38, 38, 0.15); }
.eg-card__games {
  font-size: 0.85rem;
  color: var(--text-secondary);
}
.eg-card__pct {
  font-size: 0.85rem;
  font-weight: 600;
}
.eg-card__pct--good { color: #16a34a; }
.eg-card__pct--bad { color: #dc2626; }
.eg-card__pct--neutral { color: var(--text-secondary); }
.eg-card__clock {
  font-size: 0.85rem;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.eg-card__clock-you {
  background: #dcfce7;
  color: #16a34a;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
}
.eg-card__clock-opp {
  background: var(--badge-bg);
  color: var(--text-secondary);
  padding: 1px 5px;
  border-radius: 4px;
}
.eg-card__body {
  margin-top: 16px;
}
.eg-card__board-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.eg-card__example-heading {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary);
}
.eg-card__game-link {
  color: #2563eb;
  text-decoration: none;
  font-size: 0.85rem;
}
.eg-card__game-link:hover { text-decoration: underline; color: #1d4ed8; }
.eg-card__all-link {
  display: inline-block;
  margin-top: 10px;
  font-size: 0.85rem;
  color: #2563eb;
  text-decoration: none;
}
.eg-card__all-link:hover { text-decoration: underline; color: #1d4ed8; }
</style>
