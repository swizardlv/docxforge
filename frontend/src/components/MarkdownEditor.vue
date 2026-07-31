<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue'

const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

const editorId = useId()
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const gutterRef = ref<HTMLDivElement | null>(null)

const lines = computed(() => model.value.split('\n').length)
const characters = computed(() => model.value.length)

/** Keeps the gutter glued to the textarea's scroll position. */
function syncScroll(): void {
  if (gutterRef.value && textareaRef.value) {
    gutterRef.value.scrollTop = textareaRef.value.scrollTop
  }
}

/** Tab inserts two spaces instead of moving focus out of the editor. */
async function handleTab(event: KeyboardEvent): Promise<void> {
  const el = textareaRef.value
  if (!el || props.disabled) {
    return
  }
  event.preventDefault()
  const { selectionStart, selectionEnd } = el
  const indent = '  '
  model.value = `${model.value.slice(0, selectionStart)}${indent}${model.value.slice(selectionEnd)}`
  await nextTick()
  el.selectionStart = el.selectionEnd = selectionStart + indent.length
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <label
      :for="editorId"
      class="df-label"
    >Markdown 正文</label>
    <div
      class="flex min-h-0 flex-1 overflow-hidden rounded-md border border-line bg-surface focus-within:border-accent"
    >
      <!-- Line numbers are decorative; screen readers read the textarea only. -->
      <div
        ref="gutterRef"
        aria-hidden="true"
        class="w-12 shrink-0 overflow-hidden border-r border-line-soft bg-surface-muted py-3 text-right font-mono text-[13px]/6 text-ink-muted select-none"
      >
        <div
          v-for="n in lines"
          :key="n"
          class="pr-2 tabular-nums"
        >
          {{ n }}
        </div>
        <div class="h-16" />
      </div>
      <textarea
        :id="editorId"
        ref="textareaRef"
        v-model="model"
        :disabled="disabled"
        spellcheck="false"
        autocomplete="off"
        autocapitalize="off"
        wrap="off"
        :aria-describedby="`${editorId}-hint`"
        class="min-h-[18rem] flex-1 resize-none overflow-auto bg-surface px-3 py-3 font-mono text-[13px]/6 text-ink outline-none disabled:bg-surface-muted disabled:text-ink-muted"
        @scroll="syncScroll"
        @keydown.tab="handleTab"
      />
    </div>
    <p
      :id="`${editorId}-hint`"
      class="df-hint flex items-center justify-between"
    >
      <span>支持 H1-H6、列表、表格、引用与代码块；Tab 键插入两个空格。</span>
      <span class="font-mono tabular-nums">{{ lines }} 行 · {{ characters }} 字符</span>
    </p>
  </div>
</template>
