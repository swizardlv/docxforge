<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()

const statusText = computed(() => {
  if (store.exporting) {
    return '正在渲染文档…'
  }
  if (store.exportError) {
    return '导出失败'
  }
  if (store.isDestroyed) {
    return '沙箱已销毁，文件不可下载'
  }
  if (store.job?.state === 'ready') {
    return `导出成功，耗时 ${store.job.elapsed_ms ?? 0} ms`
  }
  return '尚未导出'
})

const statusTone = computed(() => {
  if (store.exporting) {
    return 'border-accent/40 bg-accent-soft text-accent-strong'
  }
  if (store.exportError) {
    return 'border-danger/40 bg-danger-soft text-danger'
  }
  if (store.isDestroyed) {
    return 'border-line bg-surface-muted text-ink-muted'
  }
  if (store.job?.state === 'ready') {
    return 'border-success/40 bg-success-soft text-success'
  }
  return 'border-line bg-surface-muted text-ink-muted'
})
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap gap-2">
      <AppButton
        variant="primary"
        icon="bolt"
        class="flex-1 basis-48"
        :loading="store.exporting"
        :disabled="store.connecting"
        @click="store.exportDocument()"
      >
        {{ store.exporting ? '渲染中…' : '导出 Word 文档' }}
      </AppButton>
      <AppButton
        icon="download"
        class="flex-1 basis-40"
        :loading="store.downloading"
        :disabled="!store.canDownload"
        @click="store.downloadDocument()"
      >
        下载
      </AppButton>
    </div>

    <!-- aria-live so the export outcome is announced without a focus change. -->
    <div
      class="flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium"
      :class="statusTone"
      role="status"
      aria-live="polite"
    >
      <AppIcon
        :name="store.exporting ? 'spinner' : store.job?.state === 'ready' ? 'check' : 'document'"
        :spin="store.exporting"
        class="size-[18px] shrink-0"
      />
      <span class="min-w-0 flex-1">{{ statusText }}</span>
      <span
        v-if="store.job?.filename"
        class="truncate font-mono text-xs"
      >
        {{ store.job.filename }}
      </span>
    </div>

    <InlineMessage
      v-if="store.exportError"
      tone="error"
      :detail="store.exportError.detail"
      :code="store.exportError.code"
    >
      {{ store.exportError.message }}
    </InlineMessage>

    <InlineMessage
      v-if="store.downloadError"
      tone="error"
      :detail="store.downloadError.detail"
      :code="store.downloadError.code"
    >
      {{ store.downloadError.message }}
    </InlineMessage>

    <ul
      v-if="store.job?.warnings.length"
      class="space-y-1"
    >
      <li
        v-for="warning in store.job.warnings"
        :key="warning"
      >
        <InlineMessage tone="warn">
          {{ warning }}
        </InlineMessage>
      </li>
    </ul>
  </div>
</template>
