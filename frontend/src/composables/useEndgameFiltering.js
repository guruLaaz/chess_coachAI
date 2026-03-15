import { computed, ref, watch } from 'vue'
import { useFiltersStore } from '../stores/filters'

/**
 * Composable that handles client-side cross-filtering of endgame stats.
 * Each stat has embedded game_details_json and example_candidates_json.
 * Filters from the store are applied per-game, then W/L/D are recomputed.
 *
 * @param {import('vue').Ref<Array>} stats - reactive ref of raw stat objects from API
 * @returns {{ filteredStats, visibleCount, hasResults }}
 */
export function useEndgameFiltering(stats) {
  const filters = useFiltersStore()
  const autoEscalated = ref(false)

  // Parse JSON strings once on load (memoized)
  const parsed = computed(() => {
    return (stats.value || []).map(s => ({
      ...s,
      _gameDetails: parseJson(s.game_details_json),
      _exampleCandidates: parseJson(s.example_candidates_json),
    }))
  })

  const filteredStats = computed(() => {
    const list = parsed.value
    const tcSet = new Set(filters.timeControls)
    const colorSet = new Set(filters.colors)
    const platform = filters.platform
    const minGames = filters.minGames
    const dateFrom = filters.dateFrom
    const sort = filters.sort

    const results = []

    for (const stat of list) {
      const details = stat._gameDetails
      let fWins = 0, fLosses = 0, fDraws = 0
      let myClockSum = 0, myClockCount = 0, oppClockSum = 0, oppClockCount = 0

      if (details.length > 0) {
        for (const g of details) {
          if (!gameMatchesFilters(g, tcSet, platform, colorSet, dateFrom)) continue
          if (g.r === 'win') fWins++
          else if (g.r === 'loss') fLosses++
          else fDraws++
          if (g.mc != null) { myClockSum += g.mc; myClockCount++ }
          if (g.oc != null) { oppClockSum += g.oc; oppClockCount++ }
        }
      }

      const fTotal = details.length > 0 ? (fWins + fLosses + fDraws) : (stat.total || 0)

      if (fTotal === 0 || fTotal < minGames) continue

      const winPct = fTotal ? Math.round(100 * fWins / fTotal) : 0
      const lossPct = fTotal ? Math.round(100 * fLosses / fTotal) : 0
      const drawPct = 100 - winPct - lossPct

      // Pick example matching active filters
      const example = pickExample(stat._exampleCandidates, tcSet, platform, colorSet)

      // Compute average clocks
      const avgMyClock = myClockCount > 0 ? myClockSum / myClockCount : null
      const avgOppClock = oppClockCount > 0 ? oppClockSum / oppClockCount : null

      results.push({
        ...stat,
        total: fTotal,
        win_pct: winPct,
        loss_pct: lossPct,
        draw_pct: drawPct,
        example,
        avg_my_clock: avgMyClock,
        avg_opp_clock: avgOppClock,
      })
    }

    // Sort
    results.sort((a, b) => {
      if (sort === 'win-pct' || sort === 'win_pct') return b.win_pct - a.win_pct
      if (sort === 'loss-pct' || sort === 'loss_pct') return b.loss_pct - a.loss_pct
      if (sort === 'draw-pct' || sort === 'draw_pct') return b.draw_pct - a.draw_pct
      // Default: games (total desc)
      return b.total - a.total
    })

    return results
  })

  const visibleCount = computed(() => filteredStats.value.length)
  const hasResults = computed(() => visibleCount.value > 0)

  // Auto-escalate TC on first visit if no results with default filters
  watch(filteredStats, (val) => {
    if (autoEscalated.value) return
    if (val.length > 0) return

    const tc = filters.timeControls
    // Try adding bullet
    if (!tc.includes('bullet')) {
      filters.timeControls = [...tc, 'bullet']
      autoEscalated.value = true
      return
    }
    // Try adding daily
    if (!tc.includes('daily')) {
      filters.timeControls = [...tc, 'daily']
      autoEscalated.value = true
    }
  }, { immediate: true })

  return { filteredStats, visibleCount, hasResults }
}

function parseJson(str) {
  if (!str) return []
  if (Array.isArray(str)) return str
  try { return JSON.parse(str) } catch { return [] }
}

function gameMatchesFilters(g, tcSet, platform, colorSet, dateFrom) {
  if (tcSet.size > 0 && g.tc) {
    const tc = g.tc === 'classical' ? 'daily' : g.tc
    if (!tcSet.has(tc)) return false
  }
  if (platform !== 'all' && g.p && g.p !== platform) return false
  if (colorSet.size > 0 && g.c && !colorSet.has(g.c)) return false
  if (dateFrom && g.d && g.d < dateFrom) return false
  return true
}

function pickExample(candidates, tcSet, platform, colorSet) {
  if (!candidates || !candidates.length) return null
  for (const c of candidates) {
    if (tcSet.size > 0 && c.tc && !tcSet.has(c.tc)) continue
    if (platform !== 'all' && c.p && c.p !== platform) continue
    if (colorSet.size > 0 && c.color && !colorSet.has(c.color)) continue
    return c
  }
  return null
}

export function formatClock(seconds) {
  if (seconds == null) return ''
  const s = Math.round(seconds)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return m + ':' + String(sec).padStart(2, '0')
}
