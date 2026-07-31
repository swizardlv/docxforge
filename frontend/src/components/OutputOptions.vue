<script setup lang="ts">
import { useId } from 'vue'

import ToggleField from '@/components/ui/ToggleField.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()
const levelsId = useId()
const tocTitleId = useId()
const headerId = useId()
const footerId = useId()
</script>

<template>
  <div class="grid gap-4 lg:grid-cols-2">
    <fieldset class="rounded-md border border-line-soft p-3">
      <legend class="px-1 text-sm font-bold text-ink">
        自动目录
      </legend>
      <ToggleField
        v-model="store.toc.enabled"
        label="生成自动目录（TOC）"
      />
      <div
        class="mt-2 grid gap-3 sm:grid-cols-2"
        :class="store.toc.enabled ? '' : 'opacity-60'"
      >
        <div>
          <label
            :for="tocTitleId"
            class="df-label"
          >目录标题</label>
          <input
            :id="tocTitleId"
            v-model="store.toc.title"
            class="df-control"
            type="text"
            placeholder="目录"
            :disabled="!store.toc.enabled"
          >
        </div>
        <div>
          <label
            :for="levelsId"
            class="df-label"
          >收录层级</label>
          <select
            :id="levelsId"
            v-model="store.toc.levels"
            class="df-control cursor-pointer"
            :disabled="!store.toc.enabled"
          >
            <option value="1-1">
              仅 H1
            </option>
            <option value="1-2">
              H1 - H2
            </option>
            <option value="1-3">
              H1 - H3
            </option>
            <option value="1-4">
              H1 - H4
            </option>
          </select>
        </div>
      </div>
      <div :class="store.toc.enabled ? '' : 'opacity-60'">
        <ToggleField
          v-model="store.toc.hyperlinks"
          label="目录项可点击跳转"
          :disabled="!store.toc.enabled"
        />
        <ToggleField
          v-model="store.toc.page_numbers"
          label="显示页码"
          :disabled="!store.toc.enabled"
        />
        <ToggleField
          v-model="store.toc.page_break_after"
          label="目录后插入分页符"
          :disabled="!store.toc.enabled"
        />
      </div>
    </fieldset>

    <fieldset class="rounded-md border border-line-soft p-3">
      <legend class="px-1 text-sm font-bold text-ink">
        页眉页脚
      </legend>
      <div class="grid gap-3">
        <div>
          <label
            :for="headerId"
            class="df-label"
          >页眉文字</label>
          <input
            :id="headerId"
            v-model="store.headerFooter.header_text"
            class="df-control"
            type="text"
            placeholder="留空则不添加页眉"
          >
        </div>
        <div>
          <label
            :for="footerId"
            class="df-label"
          >页脚文字</label>
          <input
            :id="footerId"
            v-model="store.headerFooter.footer_text"
            class="df-control"
            type="text"
            placeholder="留空则不添加页脚"
          >
        </div>
      </div>
      <ToggleField
        v-model="store.headerFooter.page_numbers"
        label="页脚插入页码"
      />
      <ToggleField
        v-model="store.headerFooter.different_first_page"
        label="封皮页不显示页眉页脚"
      />
    </fieldset>

    <fieldset class="rounded-md border border-line-soft p-3 lg:col-span-2">
      <legend class="px-1 text-sm font-bold text-ink">
        渲染选项
      </legend>
      <div class="grid gap-1 sm:grid-cols-2">
        <ToggleField
          v-model="store.options.fast_markdown"
          label="快速模式"
          hint="由 OfficeCLI 直接展开 Markdown，速度更快但链接与图片会降级为纯文本"
        />
        <ToggleField
          v-model="store.options.update_fields"
          label="打开时自动更新域"
          hint="写入 updateFields=true，保证目录页码是最新的"
        />
        <ToggleField
          v-model="store.options.validate_output"
          label="导出后校验 OpenXML"
          hint="更慢，但能提前发现结构错误"
        />
        <ToggleField
          v-model="store.options.use_resident"
          label="使用常驻进程"
          hint="渲染期间保持 officecli 进程常驻以提速"
        />
      </div>
    </fieldset>
  </div>
</template>
