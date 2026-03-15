import { computed } from 'vue'
import { useFiltersStore } from '../stores/filters'

/**
 * Composable that filters and sorts an array of items based on the filter store.
 * @param {import('vue').Ref<Array>} items - reactive ref of items to filter
 * @returns {{ filteredItems, visibleCount, hasResults }}
 */
export function useFiltering(items) {
  const filters = useFiltersStore()

  const filteredItems = computed(() => {
    const list = items.value || []

    const tcSet = new Set(filters.timeControls)
    const colorSet = new Set(filters.colors)

    const filtered = list.filter(item => {
      // Platform filter
      if (filters.platform !== 'all' && item.platform && item.platform !== filters.platform) {
        return false
      }

      // Time control filter (if any TCs selected)
      if (tcSet.size > 0 && item.time_class) {
        const tc = item.time_class === 'classical' ? 'daily' : item.time_class
        if (!tcSet.has(tc)) return false
      }

      // Color filter
      if (colorSet.size > 0 && item.color && !colorSet.has(item.color)) {
        return false
      }

      // Min games filter
      if (item.times_played != null && item.times_played < filters.minGames) {
        return false
      }

      // Date filter
      if (filters.dateFrom && item.game_date_iso && item.game_date_iso < filters.dateFrom) {
        return false
      }

      return true
    })

    // Sorting
    const sortField = filters.sort
    filtered.sort((a, b) => {
      if (sortField === 'loss-pct' || sortField === 'loss_pct') {
        return (b.loss_pct || 0) - (a.loss_pct || 0)
      }
      // Default: eval-loss / eval_loss_raw descending
      return (b.eval_loss_raw || 0) - (a.eval_loss_raw || 0)
    })

    return filtered
  })

  const visibleCount = computed(() => filteredItems.value.length)
  const hasResults = computed(() => visibleCount.value > 0)

  return { filteredItems, visibleCount, hasResults }
}
