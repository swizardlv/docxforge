<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()

const modeBadge = computed(() => {
  if (store.connecting) {
    return { text: '连接中', box: 'border-line bg-surface-muted text-ink-muted' }
  }
  if (store.isMock) {
    return { text: '演示数据（Mock API）', box: 'border-warn/40 bg-warn-soft text-warn' }
  }
  if (store.apiMode === 'live') {
    return { text: '已连接后端', box: 'border-success/40 bg-success-soft text-success' }
  }
  return { text: '未连接', box: 'border-line bg-surface-muted text-ink-muted' }
})

const engineText = computed(() => {
  const health = store.health
  if (!health) {
    return '等待健康检查…'
  }
  const cli = health.officecli_available
    ? `OfficeCLI ${health.officecli_version ?? '可用'}`
    : 'OfficeCLI 不可用'
  const sandbox = health.sandbox_is_memory_backed ? '内存沙箱' : '临时目录沙箱'
  return `v${health.version} · ${cli} · ${sandbox} · TTL ${health.job_ttl_seconds}s`
})
</script>

<template>
  <header class="sticky top-0 z-20 border-b border-line-soft bg-surface/95 backdrop-blur">
    <div class="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3">
      <span class="flex size-10 shrink-0 items-center justify-center rounded-md bg-brand text-white">
        <AppIcon
          name="logo"
          class="size-6"
        />
      </span>
      <div class="min-w-0 flex-1">
        <h1 class="text-lg font-bold tracking-tight text-ink">
          DocXForge
        </h1>
        <p class="truncate text-xs text-ink-muted">
          Markdown → 国标级 Word 标书渲染
        </p>
      </div>

      <p class="hidden max-w-md truncate font-mono text-xs text-ink-muted md:block">
        {{ engineText }}
      </p>

      <span
        class="inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold"
        :class="modeBadge.box"
      >
        <AppIcon
          name="server"
          class="size-4"
        />
        {{ modeBadge.text }}
      </span>

      <AppButton
        icon="refresh"
        size="sm"
        variant="secondary"
        :loading="store.connecting"
        @click="store.connect()"
      >
        重新连接
      </AppButton>
    </div>
  </header>
</template>
