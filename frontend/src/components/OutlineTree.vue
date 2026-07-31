<script setup lang="ts">
import type { OutlineNode } from '@/utils/outline'

defineProps<{ nodes: OutlineNode[]; depth?: number }>()

const LEVEL_STYLE: Record<number, string> = {
  1: 'text-[15px] font-bold text-ink',
  2: 'text-sm font-semibold text-ink-soft',
  3: 'text-sm text-ink-soft',
}
</script>

<template>
  <ul
    class="space-y-0.5"
    :class="(depth ?? 0) > 0 ? 'ml-3 border-l border-line-soft pl-3' : ''"
  >
    <li
      v-for="node in nodes"
      :key="node.id"
    >
      <div class="flex items-baseline gap-2 rounded px-1 py-1 hover:bg-surface-muted">
        <span
          class="shrink-0 rounded bg-accent-soft px-1.5 py-0.5 font-mono text-[11px] font-bold text-accent-strong"
        >
          H{{ node.level }}
        </span>
        <span
          class="min-w-0 flex-1 break-words"
          :class="LEVEL_STYLE[node.level] ?? 'text-sm text-ink-muted'"
        >
          {{ node.text }}
        </span>
        <span class="shrink-0 font-mono text-[11px] text-ink-muted tabular-nums">L{{ node.line }}</span>
      </div>
      <OutlineTree
        v-if="node.children.length"
        :nodes="node.children"
        :depth="(depth ?? 0) + 1"
      />
    </li>
  </ul>
</template>
