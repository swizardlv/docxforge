<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

import AppHeader from '@/components/AppHeader.vue'
import DestroyPanel from '@/components/DestroyPanel.vue'
import DocumentFields from '@/components/DocumentFields.vue'
import ExportPanel from '@/components/ExportPanel.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import OutputOptions from '@/components/OutputOptions.vue'
import SecurityNotice from '@/components/SecurityNotice.vue'
import StructurePreview from '@/components/StructurePreview.vue'
import TemplatePicker from '@/components/TemplatePicker.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()

onMounted(() => {
  void store.connect()
})

onBeforeUnmount(() => {
  store.stopCountdown()
})
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <AppHeader />
    <SecurityNotice />

    <main class="mx-auto w-full max-w-[1600px] flex-1 px-4 py-4">
      <InlineMessage
        v-if="store.fallbackReason"
        tone="warn"
        class="mb-4"
      >
        {{ store.fallbackReason }}
      </InlineMessage>

      <div class="grid items-start gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <!-- Left column: authoring -->
        <div class="flex min-w-0 flex-col gap-4">
          <SectionCard
            title="Markdown 编辑器"
            icon="code"
            description="左侧写内容，右侧实时查看文档结构"
            body-class="flex min-h-0 flex-col p-4"
          >
            <MarkdownEditor
              v-model="store.markdown"
              :disabled="store.exporting"
            />
          </SectionCard>

          <SectionCard
            title="模板与封皮"
            icon="document"
          >
            <div class="space-y-4">
              <TemplatePicker />
              <DocumentFields />
            </div>
          </SectionCard>

          <SectionCard
            title="目录与页眉页脚"
            icon="outline"
          >
            <OutputOptions />
          </SectionCard>
        </div>

        <!-- Right column: preview, export, destruction -->
        <div class="flex min-w-0 flex-col gap-4 xl:sticky xl:top-[76px]">
          <SectionCard
            title="文档结构预览"
            icon="outline"
            description="由 Markdown 解析出的标题树与节点统计"
            body-class="flex max-h-[26rem] min-h-0 flex-col p-4"
          >
            <StructurePreview />
          </SectionCard>

          <SectionCard
            title="导出"
            icon="bolt"
          >
            <ExportPanel />
          </SectionCard>

          <SectionCard
            title="销毁区"
            icon="shield"
            description="倒计时归零或点击【立即销毁】后，文件将被物理擦除"
          >
            <DestroyPanel />
          </SectionCard>
        </div>
      </div>
    </main>

    <footer class="border-t border-line-soft bg-surface">
      <p class="mx-auto max-w-[1600px] px-4 py-3 text-xs text-ink-muted">
        DocXForge · 本地优先渲染，源文与产物均不落持久化存储。
      </p>
    </footer>
  </div>
</template>
