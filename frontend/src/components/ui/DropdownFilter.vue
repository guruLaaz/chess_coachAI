<template>
  <div class="dropdown-filter" ref="wrapper">
    <button type="button" class="dropdown-filter__btn" @click="open = !open">
      {{ label }}
    </button>
    <div v-if="open" class="dropdown-filter__panel">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

defineProps({
  label: { type: String, required: true },
})

const open = ref(false)
const wrapper = ref(null)

function onClickOutside(e) {
  if (wrapper.value && !wrapper.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))
</script>

<style scoped>
.dropdown-filter {
  display: inline-block;
  position: relative;
}
.dropdown-filter__btn {
  background: var(--bg-primary);
  color: var(--text-label);
  border: 1px solid var(--border-input);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 0.9rem;
  font-family: inherit;
  cursor: pointer;
}
.dropdown-filter__btn:hover {
  border-color: #3b82f6;
}
.dropdown-filter__panel {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  background: var(--card-bg);
  border: 1px solid var(--border-input);
  border-radius: 8px;
  padding: 12px;
  z-index: 10;
  min-width: 140px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
