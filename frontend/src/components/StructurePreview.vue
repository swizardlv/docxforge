<script setup lang="ts">
import { computed } from 'vue'

import OutlineTree from '@/components/OutlineTree.vue'
import AppIcon, { type IconName } from '@/components/ui/AppIcon.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()
const emit = defineEmits<{ (e: 'selectLine', line: number): void }>()

const outline = computed(() => store.outline)

const blocks = computed<{ key: string; icon: IconName; label: string; value: number }[]>(() => {
  const s = outline.value.stats
  return [
    { key: 'headings', icon: 'outline', label: '标题', value: s.headings },
    { key: 'paragraphs', icon: 'document', label: '段落', value: s.paragraphs },
    { key: 'lists', icon: 'outline', label: '列表', value: s.lists },
    { key: 'tables', icon: 'table', label: '表格', value: s.tables },
    { key: 'code', icon: 'code', label: '代码块', value: s.codeBlocks },
    { key: 'quotes', icon: 'quote', label: '引用', value: s.quotes },
    { key: 'images', icon: 'image', label: '图片', value: s.images },
  ]
})
</script>

<template>
  <div class="flex min-h-0 flex-col gap-3">
    <dl class="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <div
        v-for="block in blocks"
        :key="block.key"
        class="rounded-md border border-line-soft bg-surface-muted px-2 py-2"
      >
        <dt class="flex items-center gap-1.5 text-xs text-ink-muted">
          <AppIcon
            :name="block.icon"
            class="size-4 shrink-0"
          />
          {{ block.label }}
        </dt>
        <dd class="mt-0.5 font-mono text-lg font-bold text-ink tabular-nums">
          {{ block.value }}
        </dd>
      </div>
      <div class="rounded-md border border-line-soft bg-surface-muted px-2 py-2">
        <dt class="flex items-center gap-1.5 text-xs text-ink-muted">
          <AppIcon
            name="document"
            class="size-4 shrink-0"
          />
          预估页数
        </dt>
        <dd class="mt-0.5 font-mono text-lg font-bold text-ink tabular-nums">
          ≈{{ outline.stats.estimatedPages }}
        </dd>
      </div>
    </dl>

    <div class="min-h-0 flex-1 overflow-auto rounded-md border border-line-soft p-2">
      <OutlineTree
        v-if="outline.tree.length"
        :nodes="outline.tree"
        @select-line="(line) => emit('selectLine', line)"
      />
      <p
        v-else
        class="px-2 py-6 text-center text-sm text-ink-muted"
      >
        还没有识别到标题。用 <code class="font-mono">#</code> 开头写一级标题即可生成目录结构。
      </p>
    </div>

    <p class="text-xs text-ink-muted">
      结构由前端快速扫描得到，仅用于预览；最终 AST 与分页以后端渲染结果为准。
    </p>
  </div>
</template>
