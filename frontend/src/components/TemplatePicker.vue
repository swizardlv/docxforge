<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import AppButton from '@/components/ui/AppButton.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()
const selectId = useId()
const fileInput = ref<HTMLInputElement | null>(null)
const uploadNotice = ref<string | null>(null)

const busy = computed(() => store.templatesLoading || store.uploading)

const templateSummary = computed(() => {
  const template = store.selectedTemplate
  if (!template) {
    return '未选择模板时使用内置空白底稿，仅套用默认样式。'
  }
  const parts = [`${template.styles.length} 个样式`]
  parts.push(template.has_cover ? `含封皮（${template.cover_paragraph_count} 段）` : '无封皮')
  parts.push(template.has_numbering ? '含编号' : '无编号')
  parts.push(template.has_theme ? '含主题' : '无主题')
  return parts.join(' · ')
})

function pickFile(): void {
  uploadNotice.value = null
  fileInput.value?.click()
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }
  const ok = await store.uploadTemplate(file)
  uploadNotice.value = ok ? `模板「${file.name}」已上传并选中。` : null
}

async function removeSelected(): Promise<void> {
  if (store.templateId) {
    await store.removeTemplate(store.templateId)
  }
}
</script>

<template>
  <div class="space-y-3">
    <div>
      <label
        :for="selectId"
        class="df-label"
      >Word 模板</label>
      <div class="flex flex-wrap gap-2">
        <select
          :id="selectId"
          v-model="store.templateId"
          class="df-control min-w-0 flex-1 cursor-pointer"
          :disabled="busy"
          :aria-describedby="`${selectId}-summary`"
        >
          <option :value="null">
            不使用模板（内置空白底稿）
          </option>
          <option
            v-for="item in store.templates"
            :key="item.template_id"
            :value="item.template_id"
          >
            {{ item.name }}
          </option>
        </select>
        <AppButton
          icon="upload"
          size="sm"
          :loading="store.uploading"
          :disabled="store.templatesLoading"
          @click="pickFile"
        >
          上传 .docx
        </AppButton>
        <AppButton
          icon="refresh"
          size="sm"
          variant="ghost"
          label="刷新模板列表"
          :loading="store.templatesLoading"
          @click="store.loadTemplates()"
        >
          刷新
        </AppButton>
      </div>
      <p
        :id="`${selectId}-summary`"
        class="df-hint"
      >
        {{ templateSummary }}
      </p>
      <input
        ref="fileInput"
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        class="sr-only"
        tabindex="-1"
        @change="onFileChange"
      >
    </div>

    <div
      v-if="store.selectedTemplate"
      class="flex flex-wrap items-center gap-2"
    >
      <AppButton
        icon="trash"
        size="sm"
        variant="ghost"
        @click="removeSelected"
      >
        删除当前模板
      </AppButton>
      <span
        v-for="warning in store.selectedTemplate.warnings"
        :key="warning"
        class="rounded border border-warn/30 bg-warn-soft px-2 py-1 text-xs text-warn"
      >
        {{ warning }}
      </span>
    </div>

    <InlineMessage
      v-if="uploadNotice"
      tone="success"
    >
      {{ uploadNotice }}
    </InlineMessage>
    <InlineMessage
      v-if="store.templateError"
      tone="error"
      :detail="store.templateError.detail"
      :code="store.templateError.code"
    >
      {{ store.templateError.message }}
    </InlineMessage>
  </div>
</template>
