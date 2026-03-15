import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useThemeStore } from '@/stores/theme'

describe('useThemeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    localStorage.getItem.mockClear()
    localStorage.setItem.mockClear()
    document.documentElement.removeAttribute('data-theme')
    // Reset matchMedia to default (no dark mode preference)
    matchMedia.mockImplementation((query) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  })

  it('init() reads dark from localStorage', () => {
    localStorage.getItem.mockReturnValue('dark')
    const store = useThemeStore()
    store.init()
    expect(store.darkMode).toBe(true)
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('init() reads light from localStorage', () => {
    localStorage.getItem.mockReturnValue('light')
    const store = useThemeStore()
    store.init()
    expect(store.darkMode).toBe(false)
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('init() falls back to system preference when no saved theme', () => {
    localStorage.getItem.mockReturnValue(null)
    matchMedia.mockImplementation(() => ({
      matches: true,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    const store = useThemeStore()
    store.init()
    expect(store.darkMode).toBe(true)
  })

  it('toggle() flips state and updates localStorage', () => {
    const store = useThemeStore()
    store.init()
    expect(store.darkMode).toBe(false)

    store.toggle()
    expect(store.darkMode).toBe(true)
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')

    store.toggle()
    expect(store.darkMode).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'light')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })
})
