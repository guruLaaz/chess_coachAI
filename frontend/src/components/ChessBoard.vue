<template>
  <div class="chess-board" :style="{ width: size + 'px', height: size + 'px' }">
    <div v-if="loading" class="chess-board__loading">
      <span class="chess-board__spinner" />
      <span>{{ t('loading_board') }}</span>
    </div>
    <div v-else class="chess-board__svg" v-html="svg" />
  </div>
</template>

<script setup>
import { watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useBoardLoader } from '@/composables/useBoardLoader'

const props = defineProps({
  fen: { type: String, required: true },
  move: { type: String, default: '' },
  color: { type: String, default: 'white', validator: (v) => ['white', 'black'].includes(v) },
  arrowColor: { type: String, default: '' },
  size: { type: Number, default: 200 },
})

const route = useRoute()
const { t } = useI18n()
const userPath = route.params.userPath || ''
const { svg, loading, load } = useBoardLoader(userPath)

function buildSpec() {
  return {
    fen: props.fen,
    move: props.move,
    color: props.color,
    arrowColor: props.arrowColor,
    size: props.size,
  }
}

onMounted(() => load(buildSpec()))

watch(
  () => [props.fen, props.move, props.color, props.arrowColor, props.size],
  () => load(buildSpec()),
)
</script>

<style scoped>
.chess-board {
  display: inline-block;
  text-align: center;
}
.chess-board__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 8px;
  color: var(--text-muted, #94a3b8);
  font-size: 0.85rem;
}
.chess-board__spinner {
  width: 20px;
  height: 20px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: board-spin 0.6s linear infinite;
}
@keyframes board-spin {
  to { transform: rotate(360deg); }
}
.chess-board__svg :deep(svg) {
  width: 100%;
  height: 100%;
}
</style>
