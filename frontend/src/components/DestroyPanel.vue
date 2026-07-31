<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()

const remaining = computed(() => store.secondsRemaining)
const total = computed(() => store.ttlSeconds || 60)
const percent = computed(() =>
  total.value > 0 ? Math.min(100, Math.round((remaining.value / total.value) * 100)) : 0,
)

/** State is carried by text + numerals, never by colour alone. */
const phase = computed(() => {
  if (store.isDestroyed) {
    return { label: '已销毁', tone: 'text-ink-muted', bar: 'bg-ink-muted' }
  }
  if (remaining.value <= 10) {
    return { label: '即将销毁', tone: 'text-danger', bar: 'bg-danger' }
  }
  return { label: '倒计时进行中', tone: 'text-accent-strong', bar: 'bg-accent' }
})

const countdownText = computed(() =>
  store.isDestroyed
    ? '沙箱文件已物理销毁，无法再次下载。'
    : `距离物理销毁还有 ${remaining.value} 秒（共 ${total.value} 秒）。`,
)
</script>

<template>
  <div
    v-if="store.job"
    class="space-y-3"
  >
    <div class="flex items-center gap-3">
      <AppIcon
        :name="store.isDestroyed ? 'shield' : 'clock'"
        class="size-6 shrink-0"
        :class="phase.tone"
      />
      <div class="min-w-0 flex-1">
        <p class="flex items-baseline gap-2">
          <span
            class="font-mono text-3xl font-bold tabular-nums"
            :class="phase.tone"
          >
            {{ store.isDestroyed ? '00' : String(remaining).padStart(2, '0') }}
          </span>
          <span class="text-sm text-ink-muted">秒</span>
          <span
            class="text-sm font-semibold"
            :class="phase.tone"
          >{{ phase.label }}</span>
        </p>
      </div>
      <AppButton
        variant="danger"
        icon="trash"
        :loading="store.destroying"
        :disabled="store.isDestroyed"
        @click="store.destroyNow()"
      >
        立即销毁
      </AppButton>
    </div>

    <div
      class="h-2 w-full overflow-hidden rounded-full bg-line-soft"
      role="progressbar"
      :aria-valuenow="remaining"
      aria-valuemin="0"
      :aria-valuemax="total"
      :aria-label="`销毁倒计时剩余 ${remaining} 秒`"
    >
      <div
        class="h-full transition-[width] duration-300 ease-linear"
        :class="phase.bar"
        :style="{ width: `${store.isDestroyed ? 0 : percent}%` }"
      />
    </div>

    <p
      class="text-sm text-ink-soft"
      role="status"
      aria-live="polite"
    >
      {{ countdownText }}
    </p>

    <InlineMessage
      v-if="store.destroyReport"
      tone="success"
    >
      已销毁 {{ store.destroyReport.files_shredded }} 个文件（{{
        store.destroyReport.bytes_shredded
      }}
      字节）；沙箱目录
      {{ store.destroyReport.sandbox_exists_after ? '仍然存在，请检查后端' : '已不存在' }}。
    </InlineMessage>

    <InlineMessage
      v-if="store.destroyError"
      tone="error"
      :detail="store.destroyError.detail"
      :code="store.destroyError.code"
    >
      {{ store.destroyError.message }}
    </InlineMessage>
  </div>

  <p
    v-else
    class="text-sm text-ink-muted"
  >
    导出成功后，这里会显示 {{ total }} 秒物理销毁倒计时与【立即销毁】按钮。
  </p>
</template>
