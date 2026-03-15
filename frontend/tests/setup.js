import { vi } from 'vitest'

// Mock localStorage
const localStore = {}
global.localStorage = {
  getItem: vi.fn((key) => localStore[key] || null),
  setItem: vi.fn((key, val) => { localStore[key] = String(val) }),
  removeItem: vi.fn((key) => { delete localStore[key] }),
  clear: vi.fn(() => Object.keys(localStore).forEach((k) => delete localStore[k])),
}

// Mock sessionStorage
const sessionStore = {}
global.sessionStorage = {
  getItem: vi.fn((key) => sessionStore[key] || null),
  setItem: vi.fn((key, val) => { sessionStore[key] = String(val) }),
  removeItem: vi.fn((key) => { delete sessionStore[key] }),
  clear: vi.fn(() => Object.keys(sessionStore).forEach((k) => delete sessionStore[k])),
}

// Mock matchMedia
global.matchMedia = vi.fn().mockImplementation((query) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}))
