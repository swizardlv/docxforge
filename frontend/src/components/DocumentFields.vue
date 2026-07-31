<script setup lang="ts">
import { useId } from 'vue'

import AppButton from '@/components/ui/AppButton.vue'
import ToggleField from '@/components/ui/ToggleField.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()
const titleId = useId()
const filenameId = useId()
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label
          :for="titleId"
          class="df-label"
        >文档标题</label>
        <input
          :id="titleId"
          v-model="store.docTitle"
          class="df-control"
          type="text"
          placeholder="例如：XX市智能化项目投标书"
        >
        <p class="df-hint">
          写入文档属性，并作为默认文件名。
        </p>
      </div>
      <div>
        <label
          :for="filenameId"
          class="df-label"
        >输出文件名</label>
        <input
          :id="filenameId"
          v-model="store.filename"
          class="df-control"
          type="text"
          placeholder="留空则使用文档标题"
        >
        <p class="df-hint">
          无需填写扩展名，后端固定输出 .docx。
        </p>
      </div>
    </div>

    <div class="rounded-md border border-line-soft bg-surface-muted p-3">
      <ToggleField
        v-model="store.coverEnabled"
        label="注入模板封皮"
        hint="用下表的字段替换模板封皮中的占位文字"
      />
      <ToggleField
        v-model="store.coverPageBreakAfter"
        label="封皮后插入分页符"
        :disabled="!store.coverEnabled"
      />

      <fieldset
        class="mt-2"
        :disabled="!store.coverEnabled"
      >
        <legend class="df-label mb-2">
          封皮字段替换
        </legend>
        <div class="space-y-2">
          <div
            v-for="field in store.coverFields"
            :key="field.id"
            class="flex flex-wrap items-start gap-2"
          >
            <label
              class="sr-only"
              :for="`cover-find-${field.id}`"
            >占位文字</label>
            <input
              :id="`cover-find-${field.id}`"
              v-model="field.find"
              class="df-control min-w-0 flex-1 basis-40 font-mono text-sm"
              type="text"
              placeholder="模板中的原文"
            >
            <span
              aria-hidden="true"
              class="self-center text-ink-muted"
            >→</span>
            <label
              class="sr-only"
              :for="`cover-replace-${field.id}`"
            >替换为</label>
            <input
              :id="`cover-replace-${field.id}`"
              v-model="field.replace"
              class="df-control min-w-0 flex-1 basis-40 text-sm"
              type="text"
              placeholder="替换后的内容"
            >
            <AppButton
              icon="trash"
              size="sm"
              variant="ghost"
              :label="`删除字段 ${field.find || '未命名'}`"
              @click="store.removeCoverField(field.id)"
            />
          </div>
        </div>
        <AppButton
          icon="plus"
          size="sm"
          variant="ghost"
          class="mt-2"
          @click="store.addCoverField()"
        >
          添加字段
        </AppButton>
        <p class="df-hint">
          左侧填模板封皮里已有的文字，右侧填要替换成的内容；留空的行会被忽略。
        </p>
      </fieldset>
    </div>
  </div>
</template>
