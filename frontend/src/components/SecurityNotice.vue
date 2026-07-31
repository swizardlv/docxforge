<script setup lang="ts">
import { computed } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()

/** PRD module D mandates this exact wording. */
const NOTICE = '数据全流程在临时内存中计算，销毁倒计时已启动'

const detail = computed(() => {
  const ttl = store.ttlSeconds
  return store.job && !store.isDestroyed
    ? `当前任务将在 ${store.secondsRemaining} 秒后被物理销毁。`
    : `导出后 ${ttl} 秒内未销毁的文件会被自动擦除。`
})
</script>

<template>
  <div class="border-b border-accent/20 bg-accent-soft">
    <p
      class="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-2 gap-y-1 px-4 py-2 text-sm text-accent-strong"
    >
      <AppIcon
        name="shield"
        class="size-[18px] shrink-0"
      />
      <strong class="font-semibold">{{ NOTICE }}</strong>
      <span class="text-ink-soft">{{ detail }}</span>
    </p>
  </div>
</template>
