import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'

// Mock onMounted/onUnmounted since we're not in a component context
vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onMounted: vi.fn((fn) => fn()),
    onUnmounted: vi.fn(),
  }
})

import { useInfiniteScroll } from '@/composables/useInfiniteScroll'

describe('useInfiniteScroll', () => {
  const makeItems = (n) => Array.from({ length: n }, (_, i) => ({ id: i }))

  it('initial visibleItems is first pageSize items', () => {
    const items = ref(makeItems(50))
    const { visibleItems } = useInfiniteScroll(items, 10)
    expect(visibleItems.value.length).toBe(10)
    expect(visibleItems.value[0].id).toBe(0)
    expect(visibleItems.value[9].id).toBe(9)
  })

  it('loadMore() adds pageSize more', () => {
    const items = ref(makeItems(50))
    const { visibleItems, loadMore } = useInfiniteScroll(items, 10)
    loadMore()
    expect(visibleItems.value.length).toBe(20)
  })

  it('loadMore() caps at total items', () => {
    const items = ref(makeItems(15))
    const { visibleItems, loadMore } = useInfiniteScroll(items, 10)
    loadMore()
    expect(visibleItems.value.length).toBe(15)
    // Additional loadMore should not exceed
    loadMore()
    expect(visibleItems.value.length).toBe(15)
  })

  it('reset() goes back to first page', () => {
    const items = ref(makeItems(50))
    const { visibleItems, loadMore, reset } = useInfiniteScroll(items, 10)
    loadMore()
    loadMore()
    expect(visibleItems.value.length).toBe(30)
    reset()
    expect(visibleItems.value.length).toBe(10)
  })
})
