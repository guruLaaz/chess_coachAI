<template>
  <FeedbackModal v-model="uiStore.feedbackOpen" />
  <router-view />
</template>

<script setup>
import { useThemeStore } from '@/stores/theme'
import { useUiStore } from '@/stores/ui'
import FeedbackModal from '@/components/FeedbackModal.vue'

const themeStore = useThemeStore()
themeStore.init()

const uiStore = useUiStore()
</script>
