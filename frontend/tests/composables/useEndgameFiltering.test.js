import { describe, it, expect, beforeEach } from 'vitest'
import { ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useEndgameFiltering } from '@/composables/useEndgameFiltering'
import { useFiltersStore } from '@/stores/filters'

function makeStat(overrides = {}) {
  return {
    endgame_type: 'R vs R',
    total: 10,
    win_pct: 50,
    loss_pct: 30,
    draw_pct: 20,
    game_details_json: JSON.stringify([
      { r: 'win', tc: 'blitz', p: 'chesscom', c: 'white', d: '2025-08-01' },
      { r: 'loss', tc: 'blitz', p: 'chesscom', c: 'black', d: '2025-08-02' },
      { r: 'win', tc: 'rapid', p: 'lichess', c: 'white', d: '2025-07-01' },
      { r: 'draw', tc: 'rapid', p: 'lichess', c: 'black', d: '2025-07-15' },
      { r: 'loss', tc: 'bullet', p: 'chesscom', c: 'white', d: '2025-06-01' },
    ]),
    example_candidates_json: JSON.stringify([
      { tc: 'blitz', p: 'chesscom', color: 'white', url: 'game1' },
      { tc: 'rapid', p: 'lichess', color: 'black', url: 'game2' },
    ]),
    ...overrides,
  }
}

describe('useEndgameFiltering', () => {
  let filters

  beforeEach(() => {
    setActivePinia(createPinia())
    filters = useFiltersStore()
    // Allow all items through
    filters.platform = 'all'
    filters.timeControls = ['blitz', 'rapid', 'bullet', 'daily']
    filters.colors = ['white', 'black']
    filters.minGames = 1
    filters.dateFrom = ''
    filters.sort = 'games'
  })

  it('recomputes W/L/D percentages correctly with all games', () => {
    const stats = ref([makeStat()])
    const { filteredStats } = useEndgameFiltering(stats)
    const s = filteredStats.value[0]
    // 2 wins, 2 losses, 1 draw out of 5
    expect(s.win_pct).toBe(40)
    expect(s.loss_pct).toBe(40)
    expect(s.draw_pct).toBe(20)
    expect(s.total).toBe(5)
  })

  it('filters by platform and recomputes', () => {
    filters.platform = 'chesscom'
    const stats = ref([makeStat()])
    const { filteredStats } = useEndgameFiltering(stats)
    const s = filteredStats.value[0]
    // chesscom games: win(blitz), loss(blitz), loss(bullet) = 3 games
    expect(s.total).toBe(3)
    expect(s.win_pct).toBe(33) // 1/3
    expect(s.loss_pct).toBe(67) // 2/3
  })

  it('picks matching example candidate', () => {
    filters.platform = 'lichess'
    const stats = ref([makeStat()])
    const { filteredStats } = useEndgameFiltering(stats)
    const example = filteredStats.value[0].example
    expect(example).not.toBeNull()
    expect(example.p).toBe('lichess')
  })

  it('returns empty when all games filtered out', () => {
    // Use a combination that won't trigger auto-escalation
    // Set all TCs including bullet/daily so auto-escalation has nothing to add
    filters.platform = 'all'
    filters.timeControls = ['daily']
    filters.colors = ['white', 'black']
    filters.minGames = 100  // No stat will have 100+ matching games
    const stats = ref([makeStat()])
    const { filteredStats, hasResults } = useEndgameFiltering(stats)
    expect(filteredStats.value.length).toBe(0)
    expect(hasResults.value).toBe(false)
  })
})
