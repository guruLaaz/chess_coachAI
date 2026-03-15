import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import i18n from '@/i18n'
import LandingPage from '@/views/LandingPage.vue'

// Mock the API
vi.mock('@/api', () => ({
  submitAnalysis: vi.fn(),
}))

// Mock AnalyzeForm as a simple form
vi.mock('@/components/forms/AnalyzeForm.vue', () => ({
  default: {
    name: 'AnalyzeForm',
    props: ['errorKeys', 'compact', 'chesscomUser', 'lichessUser'],
    emits: ['submit'],
    template: `
      <form @submit.prevent="$emit('submit', { chesscomUser: 'hikaru', lichessUser: '' })">
        <input name="chesscom" />
        <input name="lichess" />
        <div v-if="errorKeys && errorKeys.length" class="error">{{ errorKeys[0].key }}</div>
        <button type="submit">Submit</button>
      </form>
    `,
  },
}))

// Mock SimpleLayout
vi.mock('@/components/layout/SimpleLayout.vue', () => ({
  default: {
    name: 'SimpleLayout',
    template: '<div><slot /><slot name="header-controls" /></div>',
  },
}))

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ params: {} }),
}))

function mountPage() {
  return mount(LandingPage, {
    global: {
      plugins: [createPinia(), i18n],
      stubs: {
        'router-link': { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('LandingPage', () => {
  beforeEach(() => {
    mockPush.mockClear()
  })

  it('renders the form', () => {
    const wrapper = mountPage()
    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.findAll('input').length).toBe(2)
  })

  it('navigates on successful submit', async () => {
    const { submitAnalysis } = await import('@/api')
    submitAnalysis.mockResolvedValue({ redirect: '/u/hikaru/status' })

    const wrapper = mountPage()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockPush).toHaveBeenCalledWith('/u/hikaru/status')
  })

  it('displays error on server error', async () => {
    const { submitAnalysis } = await import('@/api')
    submitAnalysis.mockRejectedValue(new Error('400: {"error_keys":[{"key":"error_no_username"}]}'))

    const wrapper = mountPage()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    // The error should propagate to the AnalyzeForm via errorKeys prop
    const form = wrapper.findComponent({ name: 'AnalyzeForm' })
    expect(form.props('errorKeys').length).toBeGreaterThan(0)
  })
})
