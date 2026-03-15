import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = '_filters'

const DEFAULTS = {
  platform: 'all',
  timeControls: ['blitz', 'rapid'],
  colors: ['white', 'black'],
  minGames: 3,
  dateFrom: '',
  dateDays: '',
  sort: 'eval-loss',
}

export const useFiltersStore = defineStore('filters', () => {
  const platform = ref(DEFAULTS.platform)
  const timeControls = ref([...DEFAULTS.timeControls])
  const colors = ref([...DEFAULTS.colors])
  const minGames = ref(DEFAULTS.minGames)
  const dateFrom = ref(DEFAULTS.dateFrom)
  const dateDays = ref(DEFAULTS.dateDays)
  const sort = ref(DEFAULTS.sort)

  function reset() {
    platform.value = DEFAULTS.platform
    timeControls.value = [...DEFAULTS.timeControls]
    colors.value = [...DEFAULTS.colors]
    minGames.value = DEFAULTS.minGames
    dateFrom.value = DEFAULTS.dateFrom
    dateDays.value = DEFAULTS.dateDays
    sort.value = DEFAULTS.sort
    saveToSessionStorage()
  }

  function saveToSessionStorage() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        platform: platform.value,
        tc: timeControls.value,
        colors: colors.value,
        minGames: minGames.value,
        dateFrom: dateFrom.value,
        dateDays: dateDays.value,
        sort: sort.value,
      }))
    } catch (e) { /* ignore */ }
  }

  function restoreFromSessionStorage() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY)
      if (!raw) return false
      const state = JSON.parse(raw)
      if (state.platform) platform.value = state.platform
      if (state.tc) timeControls.value = state.tc
      if (state.colors) colors.value = state.colors
      if (state.minGames) minGames.value = parseInt(state.minGames, 10)
      if (state.dateFrom !== undefined) dateFrom.value = state.dateFrom
      if (state.dateDays !== undefined) dateDays.value = state.dateDays
      if (state.sort) sort.value = state.sort
      return true
    } catch (e) {
      return false
    }
  }

  return {
    platform, timeControls, colors, minGames, dateFrom, dateDays, sort,
    reset, saveToSessionStorage, restoreFromSessionStorage,
  }
})
