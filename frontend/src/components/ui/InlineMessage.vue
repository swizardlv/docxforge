<script setup lang="ts">
import { computed } from 'vue'

import AppIcon, { type IconName } from '@/components/ui/AppIcon.vue'

type Tone = 'error' | 'warn' | 'success' | 'info'

const props = withDefaults(
  defineProps<{ tone?: Tone; title?: string; detail?: string | null; code?: string | null }>(),
  { tone: 'error', title: undefined, detail: null, code: null },
)

const TONES: Record<Tone, { box: string; icon: IconName; label: string }> = {
  error: { box: 'border-danger/40 bg-danger-soft text-danger', icon: 'alert', label: '错误' },
  warn: { box: 'border-warn/40 bg-warn-soft text-warn', icon: 'alert', label: '提示' },
  success: { box: 'border-success/40 bg-success-soft text-success', icon: 'check', label: '成功' },
  info: { box: 'border-accent/30 bg-accent-soft text-accent-strong', icon: 'shield', label: '信息' },
}

const tone = computed(() => TONES[props.tone])
</script>

<template>
  <div
    class="flex items-start gap-2 rounded-md border px-3 py-2 text-sm"
    :class="tone.box"
    :role="props.tone === 'error' ? 'alert' : 'status'"
  >
    <AppIcon
      :name="tone.icon"
      class="mt-0.5 size-[18px] shrink-0"
    />
    <div class="min-w-0 flex-1">
      <!-- Text label carries the state, so meaning never depends on colour alone. -->
      <p class="font-semibold">
        <span class="mr-1">{{ tone.label }}：</span>
        <span class="font-normal"><slot>{{ title }}</slot></span>
      </p>
      <p
        v-if="detail"
        class="mt-1 break-words font-mono text-xs opacity-90"
      >
        {{ detail }}
      </p>
      <p
        v-if="code"
        class="mt-1 font-mono text-xs opacity-80"
      >
        code: {{ code }}
      </p>
    </div>
  </div>
</template>
