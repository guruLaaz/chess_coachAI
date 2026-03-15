import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const feedbackOpen = ref(false)

  function openFeedback() {
    feedbackOpen.value = true
  }

  function closeFeedback() {
    feedbackOpen.value = false
  }

  return { feedbackOpen, openFeedback, closeFeedback }
})
