import { describe, it, expect, beforeEach } from 'vitest'
import { ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useFiltering } from '@/composables/useFiltering'
import { useFiltersStore } from '@/stores/filters'

const mockItems = [
  { eco_code: 'B90', color: 'white', platform: 'chesscom', time_class: 'blitz', times_played: 5, game_date_iso: '2025-06-15', eval_loss_raw: 120, loss_pct: 50 },
  { eco_code: 'C50', color: 'black', platform: 'lichess', time_class: 'rapid', times_played: 3, game_date_iso: '2025-08-01', eval_loss_raw: 80, loss_pct: 30 },
  { eco_code: 'D00', color: 'white', platform: 'chesscom', time_class: 'bullet', times_played: 1, game_date_iso: '2025-03-01', eval_loss_raw: 200, loss_pct: 80 },
  { eco_code: 'A45', color: 'black', platform: 'lichess', time_class: 'blitz', times_played: 8, game_date_iso: '2025-09-10', eval_loss_raw: 50, loss_pct: 20 },
  { eco_code: 'E60', color: 'white', platform: 'chesscom', time_class: 'rapid', times_played: 2, game_date_iso: '2025-07-01', eval_loss_raw: 150, loss_pct: 60 },
]

describe('useFiltering', () => {
  let filters

  beforeEach(() => {
    setActivePinia(createPinia())
    filters = useFiltersStore()
    // Reset to allow all items through
    filters.platform = 'all'
    filters.timeControls = ['blitz', 'rapid', 'bullet', 'daily']
    filters.colors = ['white', 'black']
    filters.minGames = 1
    filters.dateFrom = ''
    filters.sort = 'eval-loss'
  })

  it('returns all items with no filters', () => {
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    expect(filteredItems.value.length).toBe(5)
  })

  it('filters by platform', () => {
    filters.platform = 'chesscom'
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    expect(filteredItems.value.every(i => i.platform === 'chesscom')).toBe(true)
    expect(filteredItems.value.length).toBe(3)
  })

  it('filters by time control', () => {
    filters.timeControls = ['blitz']
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    expect(filteredItems.value.every(i => i.time_class === 'blitz')).toBe(true)
    expect(filteredItems.value.length).toBe(2)
  })

  it('filters by color', () => {
    filters.colors = ['white']
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    expect(filteredItems.value.every(i => i.color === 'white')).toBe(true)
    expect(filteredItems.value.length).toBe(3)
  })

  it('filters by min games', () => {
    filters.minGames = 5
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    expect(filteredItems.value.every(i => i.times_played >= 5)).toBe(true)
    expect(filteredItems.value.length).toBe(2)
  })

  it('filters by date', () => {
    filters.dateFrom = '2025-06-01'
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    expect(filteredItems.value.every(i => i.game_date_iso >= '2025-06-01')).toBe(true)
    expect(filteredItems.value.length).toBe(4)
  })

  it('applies combined filters', () => {
    filters.platform = 'chesscom'
    filters.colors = ['white']
    filters.minGames = 3
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    expect(filteredItems.value.length).toBe(1)
    expect(filteredItems.value[0].eco_code).toBe('B90')
  })

  it('sorts by eval_loss_raw descending', () => {
    filters.sort = 'eval-loss'
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    const losses = filteredItems.value.map(i => i.eval_loss_raw)
    for (let i = 1; i < losses.length; i++) {
      expect(losses[i - 1]).toBeGreaterThanOrEqual(losses[i])
    }
  })

  it('sorts by loss_pct descending', () => {
    filters.sort = 'loss-pct'
    const items = ref([...mockItems])
    const { filteredItems } = useFiltering(items)
    const pcts = filteredItems.value.map(i => i.loss_pct)
    for (let i = 1; i < pcts.length; i++) {
      expect(pcts[i - 1]).toBeGreaterThanOrEqual(pcts[i])
    }
  })

  it('returns empty when no items match', () => {
    filters.platform = 'chesscom'
    filters.colors = ['black']
    filters.minGames = 10
    const items = ref([...mockItems])
    const { filteredItems, hasResults } = useFiltering(items)
    expect(filteredItems.value.length).toBe(0)
    expect(hasResults.value).toBe(false)
  })
})
