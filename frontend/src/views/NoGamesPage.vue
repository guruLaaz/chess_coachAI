<template>
  <SimpleLayout>
    <div class="nogames-container">
      <div class="nogames-card">
        <EmptyState
          icon="♘"
          :title="t('nogames_title')"
          :description="t('nogames_desc')"
          :action-label="t('nogames_try_another')"
          action-to="/"
        />
        <div class="nogames-users" v-if="chesscomUser || lichessUser">
          <UserBadges :chesscom-user="chesscomUser" :lichess-user="lichessUser" />
        </div>
        <p class="nogames-hint">{{ t('nogames_hint') }}</p>
      </div>
    </div>
  </SimpleLayout>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import SimpleLayout from '@/components/layout/SimpleLayout.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import UserBadges from '@/components/ui/UserBadges.vue'

const route = useRoute()
const { t } = useI18n()

const chesscomUser = computed(() => route.query.chesscom || '')
const lichessUser = computed(() => route.query.lichess || '')
</script>

<style scoped>
.nogames-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 60px);
  padding: 40px 24px;
}

.nogames-card {
  background: var(--card-bg);
  box-shadow: var(--card-shadow, 0 4px 24px rgba(0, 0, 0, 0.08));
  border-radius: 16px;
  padding: 48px;
  max-width: 480px;
  width: 100%;
  text-align: center;
}

.nogames-card :deep(.empty-state) {
  padding: 0 0 16px;
}

.nogames-users {
  margin-bottom: 16px;
}

.nogames-hint {
  color: var(--text-secondary);
  font-size: 0.85rem;
  margin-top: 20px;
  line-height: 1.5;
}
</style>
