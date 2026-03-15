import { describe, it, expect } from 'vitest'
import { translateMessage } from '@/utils/translateMessage'

// Simple mock t() that returns the key (or key with interpolation)
function mockT(key, params) {
  const translations = {
    status_analyzing_game: 'Analyzing game',
    status_fetching_chesscom: 'Fetching Chess.com games...',
    status_fetching_lichess: 'Fetching Lichess games...',
    status_fetched_lichess: 'Fetched {0} Lichess games',
    status_analysis_done: 'Analysis complete: {0} games',
    status_fetching_archive: 'Fetching Chess.com archive',
    eg_games_suffix: 'games',
    status_fetched_starting: 'Fetched {0} games, starting analysis',
    status_endgame_done: 'Endgame analysis complete, starting openings',
    status_all_cached: 'All games cached, skipping engine analysis',
    status_no_games: 'No games found.',
  }
  let result = translations[key] || key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      result = result.replace(`{${k}}`, v)
    }
  }
  return result
}

// French mock
function mockTFr(key, params) {
  const translations = {
    status_analyzing_game: 'Analyse de la partie',
    status_fetching_chesscom: 'Récupération des parties Chess.com...',
    status_fetching_lichess: 'Récupération des parties Lichess...',
    status_fetched_lichess: '{0} parties Lichess récupérées',
    status_analysis_done: 'Analyse terminée : {0} parties',
    status_fetching_archive: 'Récupération archive Chess.com',
    eg_games_suffix: 'parties',
  }
  let result = translations[key] || key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      result = result.replace(`{${k}}`, v)
    }
  }
  return result
}

describe('translateMessage', () => {
  it('translates "Analyzing game 5/120..."', () => {
    const result = translateMessage('Analyzing game 5/120...', mockT)
    expect(result).toBe('Analyzing game 5/120\u2026')
  })

  it('translates "Fetching Chess.com games... (200/2280)"', () => {
    const result = translateMessage('Fetching Chess.com games... (200/2280)', mockT)
    expect(result).toBe('Fetching Chess.com games... (200/2280)')
  })

  it('translates "Fetched 200 Lichess games"', () => {
    const result = translateMessage('Fetched 200 Lichess games', mockT)
    expect(result).toBe('Fetched 200 Lichess games')
  })

  it('translates "Analysis complete: 500 games"', () => {
    const result = translateMessage('Analysis complete: 500 games', mockT)
    expect(result).toBe('Analysis complete: 500 games')
  })

  it('translates "Fetching Chess.com archive 3/12 (150 games)"', () => {
    const result = translateMessage('Fetching Chess.com archive 3/12 (150 games)', mockT)
    expect(result).toBe('Fetching Chess.com archive 3/12 (150 games)')
  })

  it('returns original for unknown message', () => {
    const result = translateMessage('Unknown status message', mockT)
    expect(result).toBe('Unknown status message')
  })

  it('returns empty string for empty input', () => {
    expect(translateMessage('', mockT)).toBe('')
    expect(translateMessage(null, mockT)).toBe('')
  })

  it('works with French locale', () => {
    const result = translateMessage('Analyzing game 10/50...', mockTFr)
    expect(result).toBe('Analyse de la partie 10/50\u2026')
  })
})
