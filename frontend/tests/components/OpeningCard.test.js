import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import i18n from '@/i18n'
import OpeningCard from '@/components/openings/OpeningCard.vue'

// Mock ChessBoard to avoid board rendering complexity
vi.mock('@/components/ChessBoard.vue', () => ({
  default: {
    name: 'ChessBoard',
    props: ['fen', 'move', 'color', 'arrowColor'],
    template: '<div class="mock-board" :data-fen="fen" :data-move="move" :data-color="color"></div>',
  },
}))

// Mock EvalBadge
vi.mock('@/components/ui/EvalBadge.vue', () => ({
  default: {
    name: 'EvalBadge',
    props: ['value', 'type'],
    template: '<span class="eval-badge" :class="type">{{ value }}</span>',
  },
}))

const mockItem = {
  eco_name: 'Sicilian Najdorf',
  eco_code: 'B90',
  color: 'white',
  eval_loss_display: '-1.2',
  eval_loss_class: 'bad',
  eval_display: '-0.3',
  eval_class: 'bad',
  move_label: '6.',
  played_san: 'd5',
  best_san: 'e5',
  book_moves: 'e5, c5',
  fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
  best_move_uci: 'e7e5',
  played_move_uci: 'd7d5',
  times_played: 3,
  game_url: 'https://chess.com/game/123',
  eval_loss_raw: 120,
  win_pct: 33,
  loss_pct: 33,
  time_class: 'blitz',
  platform: 'chesscom',
  opponent_name: 'opponent1',
  game_date: 'June 15, 2025',
  game_date_iso: '2025-06-15',
}

function mountCard(item = mockItem) {
  return mount(OpeningCard, {
    props: { item, userPath: 'hikaru' },
    global: {
      plugins: [createPinia(), i18n],
      stubs: {
        'router-link': { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('OpeningCard', () => {
  it('renders eco_name', () => {
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('Sicilian Najdorf')
  })

  it('renders eval badges with correct classes', () => {
    const wrapper = mountCard()
    const badges = wrapper.findAll('.eval-badge')
    expect(badges.length).toBeGreaterThan(0)
    expect(badges[0].classes()).toContain('bad')
  })

  it('renders recommendation with best_san and played_san', () => {
    const wrapper = mountCard()
    const rec = wrapper.find('.opening-card__recommendation')
    expect(rec.text()).toContain('e5')
    expect(rec.text()).toContain('d5')
  })

  it('renders game link with correct href', () => {
    const wrapper = mountCard()
    const link = wrapper.find('.opening-card__game-link')
    expect(link.attributes('href')).toBe('https://chess.com/game/123')
  })

  it('passes correct props to ChessBoard components', () => {
    const wrapper = mountCard()
    const boards = wrapper.findAll('.mock-board')
    expect(boards.length).toBe(2)
    // Best move board
    expect(boards[0].attributes('data-move')).toBe('e7e5')
    expect(boards[0].attributes('data-color')).toBe('white')
    // Played move board
    expect(boards[1].attributes('data-move')).toBe('d7d5')
  })
})
