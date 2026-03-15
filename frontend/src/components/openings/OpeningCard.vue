<template>
  <article class="opening-card" :class="{ 'opening-card--positive': item.eval_loss_class === 'good' }">
    <div class="opening-card__header">
      <span class="opening-card__title">
        <strong>{{ item.eco_name }}</strong>
        <span class="opening-card__eco-badge">{{ item.eco_code }}</span>
        <span>{{ t('opening_as') }} {{ item.color }}</span>
      </span>
      <div class="opening-card__badges">
        <EvalBadge
          :value="`${item.eval_loss_display} ${t('opening_loss')}`"
          :type="item.eval_loss_class"
        />
        <span class="opening-card__eval-secondary">pos {{ item.eval_display }}</span>
        <span class="opening-card__result" :class="item.win_pct >= 50 ? 'win-high' : 'win-low'">
          W {{ item.win_pct }}% / L {{ item.loss_pct }}%
        </span>
      </div>
    </div>

    <div class="opening-card__boards">
      <div class="opening-card__board-panel">
        <h4 class="opening-card__board-label opening-card__board-label--best">
          {{ t('board_best') }} {{ item.best_san }}
        </h4>
        <ChessBoard
          :fen="item.fen"
          :move="item.best_move_uci"
          :color="item.color"
          arrow-color="#22c55e"
        />
      </div>
      <div class="opening-card__board-panel">
        <h4 class="opening-card__board-label opening-card__board-label--played">
          {{ t('board_played') }} {{ item.played_san }}
        </h4>
        <ChessBoard
          :fen="item.fen"
          :move="item.played_move_uci"
          :color="item.color"
          arrow-color="#ef4444"
        />
      </div>
    </div>

    <p class="opening-card__meta">
      {{ t('opening_move') }} {{ item.move_label }} &bull;
      {{ t('opening_book_moves') }} {{ item.book_moves }} &bull;
      <span class="opening-card__times" :class="{ 'opening-card__times--recurring': item.times_played > 1 }">
        {{ item.times_played }}&times; {{ t('opening_times_played') }}
      </span>
    </p>

    <div class="opening-card__recommendation">
      <span v-html="recommendationHtml"></span>
      <template v-if="item.game_url">
        &mdash;
        <a class="opening-card__game-link" :href="item.game_url" target="_blank" rel="noopener">
          {{ t('opening_view_game') }}
          <template v-if="item.opponent_name || (item.time_class && item.time_class !== 'unknown') || item.game_date">
            ({{ gameMeta }})
          </template>
          &rarr;
        </a>
      </template>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ChessBoard from '@/components/ChessBoard.vue'
import EvalBadge from '@/components/ui/EvalBadge.vue'

const props = defineProps({
  item: { type: Object, required: true },
  userPath: { type: String, required: true },
})

const { t } = useI18n()

const recommendationHtml = computed(() => {
  const raw = t('opening_play_instead', { best: props.item.best_san, played: props.item.played_san })
  return raw.replace(props.item.best_san, `<strong>${props.item.best_san}</strong>`)
})

const gameMeta = computed(() => {
  const parts = []
  if (props.item.opponent_name) parts.push(`vs ${props.item.opponent_name}`)
  if (props.item.time_class && props.item.time_class !== 'unknown') parts.push(props.item.time_class)
  if (props.item.game_date) parts.push(props.item.game_date)
  return parts.join(', ')
})
</script>

<style scoped>
.opening-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  border-left: 4px solid #f97316;
  box-shadow: var(--card-shadow);
}
.opening-card--positive {
  border-left-color: #22c55e;
}
.opening-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.opening-card__title {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.opening-card__eco-badge {
  background: var(--badge-bg);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 400;
}
.opening-card__badges {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.opening-card__eval-secondary {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.75rem;
  background: var(--badge-bg);
  color: var(--text-secondary);
}
.opening-card__result {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
}
.opening-card__result.win-high {
  background: #f0fdf4;
  color: #16a34a;
}
.opening-card__result.win-low {
  background: #fef2f2;
  color: #dc2626;
}
[data-theme="dark"] .opening-card__result.win-high {
  background: rgba(22, 163, 74, 0.15);
}
[data-theme="dark"] .opening-card__result.win-low {
  background: rgba(220, 38, 38, 0.15);
}
.opening-card__boards {
  display: flex;
  gap: 24px;
  justify-content: center;
  flex-wrap: wrap;
  margin: 16px 0;
}
.opening-card__board-panel {
  text-align: center;
}
.opening-card__board-label {
  margin-bottom: 8px;
  font-size: 0.95rem;
  color: var(--text-secondary);
}
.opening-card__board-label--best {
  color: #16a34a;
}
.opening-card__board-label--played {
  color: #dc2626;
}
.opening-card__meta {
  margin-top: 12px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}
.opening-card__times {
  background: var(--badge-bg);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.opening-card__times--recurring {
  background: #e0e7ff;
  color: #4338ca;
}
.opening-card__recommendation {
  margin-top: 12px;
  padding: 10px 16px;
  background: #f0fdf4;
  border-radius: 8px;
  color: #15803d;
  font-size: 1rem;
}
.opening-card__recommendation :deep(strong) {
  color: #16a34a;
}
[data-theme="dark"] .opening-card__recommendation {
  background: #052e16;
  color: #86efac;
}
[data-theme="dark"] .opening-card__recommendation :deep(strong) {
  color: #86efac;
}
.opening-card__game-link {
  font-size: 0.85rem;
  color: #2563eb;
  text-decoration: none;
}
.opening-card__game-link:hover {
  text-decoration: underline;
  color: #1d4ed8;
}
@media (max-width: 768px) {
  .opening-card__boards {
    flex-direction: column;
    align-items: center;
  }
}
</style>
