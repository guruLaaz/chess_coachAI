import { ref } from 'vue'
import { renderBoards } from '@/api'

const DEBOUNCE_MS = 50

// Shared state across all ChessBoard instances
let pending = []
let timer = null

/**
 * Batch board loader composable.
 * Collects board render requests and fires a single POST after a 50ms debounce.
 */
export function useBoardLoader(userPath) {
  const svg = ref('')
  const loading = ref(true)

  function request(spec) {
    loading.value = true
    svg.value = ''

    return new Promise((resolve) => {
      pending.push({ spec, resolve, userPath })

      if (timer) clearTimeout(timer)
      timer = setTimeout(flush, DEBOUNCE_MS)
    })
  }

  async function flush() {
    const batch = pending.splice(0)
    if (!batch.length) return
    timer = null

    // Group by userPath
    const groups = {}
    for (const item of batch) {
      const key = item.userPath
      if (!groups[key]) groups[key] = []
      groups[key].push(item)
    }

    for (const [path, items] of Object.entries(groups)) {
      const specs = items.map((item) => item.spec)
      try {
        const result = await renderBoards(path, specs)
        const svgs = result.boards || result
        items.forEach((item, i) => {
          item.resolve(Array.isArray(svgs) ? svgs[i] : '')
        })
      } catch {
        items.forEach((item) => item.resolve(''))
      }
    }
  }

  async function load(spec) {
    const result = await request(spec)
    svg.value = result || ''
    loading.value = false
  }

  return { svg, loading, load }
}
