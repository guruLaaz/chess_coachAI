import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchOpeningsReport, fetchEndgamesReport, fetchEndgamesAll as fetchEndgamesAllApi } from '../api'

export const useUserStore = defineStore('user', () => {
  const userPath = ref('')
  const chesscomUser = ref('')
  const lichessUser = ref('')
  const reportData = ref(null)

  async function fetchOpenings(path) {
    userPath.value = path
    reportData.value = await fetchOpeningsReport(path)
  }

  async function fetchEndgames(path) {
    userPath.value = path
    reportData.value = await fetchEndgamesReport(path)
  }

  async function fetchEndgamesAll(path, params) {
    userPath.value = path
    reportData.value = await fetchEndgamesAllApi(path, params)
  }

  return {
    userPath, chesscomUser, lichessUser, reportData,
    fetchOpenings, fetchEndgames, fetchEndgamesAll,
  }
})
