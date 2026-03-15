import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFiltersStore } from '@/stores/filters'

describe('useFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    sessionStorage.getItem.mockClear()
    sessionStorage.setItem.mockClear()
  })

  it('has correct default state values', () => {
    const store = useFiltersStore()
    expect(store.platform).toBe('all')
    expect(store.timeControls).toEqual(['blitz', 'rapid'])
    expect(store.colors).toEqual(['white', 'black'])
    expect(store.minGames).toBe(3)
    expect(store.dateFrom).toBe('')
    expect(store.dateDays).toBe('')
    expect(store.sort).toBe('eval-loss')
  })

  it('saveToSessionStorage() writes JSON to sessionStorage', () => {
    const store = useFiltersStore()
    store.platform = 'chesscom'
    store.saveToSessionStorage()
    expect(sessionStorage.setItem).toHaveBeenCalled()
    const call = sessionStorage.setItem.mock.calls[0]
    const saved = JSON.parse(call[1])
    expect(saved.platform).toBe('chesscom')
  })

  it('restoreFromSessionStorage() reads and applies saved state', () => {
    const saved = JSON.stringify({
      platform: 'lichess',
      tc: ['bullet'],
      colors: ['white'],
      minGames: 5,
      dateFrom: '2025-01-01',
      dateDays: '30',
      sort: 'loss-pct',
    })
    sessionStorage.getItem.mockReturnValue(saved)
    const store = useFiltersStore()
    const result = store.restoreFromSessionStorage()
    expect(result).toBe(true)
    expect(store.platform).toBe('lichess')
    expect(store.timeControls).toEqual(['bullet'])
    expect(store.colors).toEqual(['white'])
    expect(store.minGames).toBe(5)
    expect(store.dateFrom).toBe('2025-01-01')
    expect(store.sort).toBe('loss-pct')
  })

  it('restoreFromSessionStorage() returns false when nothing saved', () => {
    sessionStorage.getItem.mockReturnValue(null)
    const store = useFiltersStore()
    expect(store.restoreFromSessionStorage()).toBe(false)
  })

  it('reset() restores defaults', () => {
    const store = useFiltersStore()
    store.platform = 'chesscom'
    store.minGames = 10
    store.sort = 'loss-pct'
    store.reset()
    expect(store.platform).toBe('all')
    expect(store.minGames).toBe(3)
    expect(store.sort).toBe('eval-loss')
    expect(store.timeControls).toEqual(['blitz', 'rapid'])
  })
})
