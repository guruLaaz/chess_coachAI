<template>
  <div :class="['analyze-form', { 'analyze-form--compact': compact }]">
    <!-- Error messages from server -->
    <div v-if="errorKeys.length" class="analyze-form__errors">
      <p v-for="(err, i) in errorKeys" :key="i" class="analyze-form__error">
        {{ t(err.key, err) }}
      </p>
    </div>

    <div :class="['analyze-form__row', { 'analyze-form__row--compact': compact }]">
      <BaseInput
        v-model="chesscom"
        :label="t('label_chesscom')"
        :placeholder="t('label_chesscom')"
        id="chesscom-input"
      >
        <template #prefix>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M5.68 8.81c-.79-.79-.79-2.07 0-2.86l3.24-3.24a2.02 2.02 0 0 1 2.86 0l3.24 3.24c.79.79.79 2.07 0 2.86L11.78 12l3.24 3.19c.79.79.79 2.07 0 2.86l-3.24 3.24a2.02 2.02 0 0 1-2.86 0L5.68 18.05c-.79-.79-.79-2.07 0-2.86L8.92 12 5.68 8.81z"/>
          </svg>
        </template>
      </BaseInput>

      <BaseInput
        v-model="lichess"
        :label="t('label_lichess')"
        :placeholder="t('label_lichess')"
        id="lichess-input"
      >
        <template #prefix>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h-2v-2h2v2zm0-4h-2V7h2v6zm4 4h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
        </template>
      </BaseInput>
    </div>

    <!-- Client-side validation error -->
    <p v-if="validationError" class="analyze-form__error">
      {{ validationError }}
    </p>

    <BaseButton variant="primary" :size="compact ? 'sm' : 'md'" @click="onSubmit">
      {{ t('submit_btn') }}
    </BaseButton>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  chesscomUser: { type: String, default: '' },
  lichessUser: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  errorKeys: { type: Array, default: () => [] },
})

const emit = defineEmits(['submit'])
const { t } = useI18n()

const chesscom = ref(props.chesscomUser)
const lichess = ref(props.lichessUser)
const validationError = ref('')

watch(() => props.chesscomUser, (v) => { chesscom.value = v })
watch(() => props.lichessUser, (v) => { lichess.value = v })

function onSubmit() {
  validationError.value = ''
  if (!chesscom.value.trim() && !lichess.value.trim()) {
    validationError.value = t('error_msg')
    return
  }
  emit('submit', {
    chesscomUser: chesscom.value.trim(),
    lichessUser: lichess.value.trim(),
  })
}
</script>

<style scoped>
.analyze-form {
  padding: 32px;
}
.analyze-form--compact {
  padding: 16px;
}
.analyze-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.analyze-form__row--compact {
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}
.analyze-form__errors {
  margin-bottom: 12px;
}
.analyze-form__error {
  color: var(--error, #dc2626);
  font-size: 0.85rem;
  margin: 0 0 8px;
}
</style>
