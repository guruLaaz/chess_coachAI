import { ref, computed, onMounted, onUnmounted } from 'vue'

/**
 * Infinite scroll composable.
 * Progressively reveals items from a full array as the user scrolls.
 */
export function useInfiniteScroll(items, pageSize = 10) {
  const count = ref(pageSize)

  const visibleItems = computed(() => {
    const arr = items.value || []
    return arr.slice(0, count.value)
  })

  function loadMore() {
    const arr = items.value || []
    if (count.value < arr.length) {
      count.value += pageSize
    }
  }

  function reset() {
    count.value = pageSize
  }

  function onScroll() {
    const scrollBottom = window.innerHeight + window.scrollY
    const docHeight = document.documentElement.scrollHeight
    if (docHeight - scrollBottom < 200) {
      loadMore()
    }
  }

  onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
  onUnmounted(() => window.removeEventListener('scroll', onScroll))

  return { visibleItems, loadMore, reset }
}
