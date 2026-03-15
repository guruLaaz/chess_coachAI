<template>
  <SimpleLayout>
    <section class="hero">
      <span class="badge">⚡ {{ t('badge') }}</span>
      <h1>
        {{ t('hero_line1') }}<br>
        <span class="blue">{{ t('hero_line2') }}</span>
      </h1>
      <p class="subtitle">{{ t('subtitle') }}</p>

      <div class="form-card">
        <AnalyzeForm :error-keys="errorKeys" @submit="onSubmit" />
      </div>
    </section>
  </SimpleLayout>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import SimpleLayout from '@/components/layout/SimpleLayout.vue'
import AnalyzeForm from '@/components/forms/AnalyzeForm.vue'
import { submitAnalysis } from '@/api'

const router = useRouter()
const { t } = useI18n()

const errorKeys = ref([])

async function onSubmit({ chesscomUser, lichessUser }) {
  errorKeys.value = []
  try {
    const data = await submitAnalysis({
      chesscom_username: chesscomUser,
      lichess_username: lichessUser,
    })
    if (data.redirect) {
      router.push(data.redirect)
    }
  } catch (err) {
    try {
      const body = JSON.parse(err.message.replace(/^\d+:\s*/, ''))
      if (body.error_keys) {
        errorKeys.value = body.error_keys
      }
    } catch {
      // Non-JSON error — show generic
      errorKeys.value = [{ key: 'error_msg' }]
    }
  }
}
</script>

<style scoped>
.hero {
  background: var(--bg-secondary);
  padding: 140px 24px 100px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--badge-border, #d1d5db);
  border-radius: 9999px;
  padding: 6px 16px;
  font-size: 0.85rem;
  font-weight: 400;
  color: var(--badge-text);
  background: var(--badge-bg);
  margin-bottom: 24px;
}

h1 {
  font-size: 3.2rem;
  font-weight: 700;
  line-height: 1.15;
  margin-bottom: 20px;
}

.blue {
  color: var(--blue, #2563eb);
}

.subtitle {
  color: var(--text-secondary);
  font-size: 1.1rem;
  font-weight: 400;
  line-height: 1.6;
  max-width: 520px;
  margin: 0 auto 0;
}

.form-card {
  background: var(--card-bg);
  border-radius: 16px;
  box-shadow: var(--card-shadow, 0 4px 24px rgba(0, 0, 0, 0.08));
  max-width: 560px;
  width: 100%;
  margin-top: 32px;
}

@media (max-width: 768px) {
  .hero {
    padding: 100px 16px 60px;
  }
  h1 {
    font-size: 2rem;
  }
  .subtitle {
    font-size: 1rem;
  }
}
</style>
