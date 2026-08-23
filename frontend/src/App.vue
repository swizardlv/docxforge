<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import AppHeader from '@/components/AppHeader.vue'
import DestroyPanel from '@/components/DestroyPanel.vue'
import DocumentFields from '@/components/DocumentFields.vue'
import ExportPanel from '@/components/ExportPanel.vue'
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import OutputOptions from '@/components/OutputOptions.vue'
import SecurityNotice from '@/components/SecurityNotice.vue'
import StructurePreview from '@/components/StructurePreview.vue'
import StyleMappingPanel from '@/components/StyleMappingPanel.vue'
import TemplatePicker from '@/components/TemplatePicker.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { useForgeStore } from '@/stores/forge'

const store = useForgeStore()
const editorRef = ref<InstanceType<typeof MarkdownEditor> | null>(null)
const folderInputRef = ref<HTMLInputElement | null>(null)

function handleSelectLine(line: number): void {
  editorRef.value?.scrollToLine(line)
}

function triggerFolderImport(): void {
  folderInputRef.value?.click()
}

async function handleFolderImport(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files ?? [])
  if (files.length === 0) return
  await store.importFolderFiles(files)
  target.value = ''
}

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

    <main class="mx-auto flex w-full max-w-[1600px] flex-1 gap-4 px-4 py-4">
      <!-- Left sidebar: project files + template -->
      <aside class="hidden w-56 shrink-0 flex-col gap-4 xl:flex">
        <SectionCard
          title="项目文件"
          icon="document"
          body-class="flex min-h-0 flex-col p-3"
        >
          <div class="flex flex-col gap-1.5">
            <button
              class="w-full rounded bg-accent/10 px-2 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
              @click="triggerFolderImport"
            >
              📂 导入文件夹
            </button>
            <input
              ref="folderInputRef"
              type="file"
              webkitdirectory
              multiple
              class="hidden"
              @change="handleFolderImport"
            >

            <div
              v-if="store.projectFiles.length === 0"
              class="py-4 text-center text-xs text-ink-muted"
            >
              导入 Markdown 文件夹后<br>文件列表将显示在这里
            </div>

            <div
              v-else
              class="flex max-h-[40vh] flex-col gap-0.5 overflow-y-auto"
            >
              <button
                class="w-full rounded px-2 py-1 text-left text-xs transition-colors"
                :class="store.selectedFileKey === '__ALL__' ? 'bg-accent/10 font-medium text-accent' : 'text-ink-muted hover:bg-surface-muted hover:text-ink'"
                @click="store.selectProjectFile('__ALL__')"
              >
                ✨ 全部合并
              </button>
              <button
                v-for="file in store.projectFiles"
                :key="file.path"
                class="w-full rounded px-2 py-1 text-left text-xs transition-colors truncate"
                :class="store.selectedFileKey === file.path ? 'bg-accent/10 font-medium text-accent' : 'text-ink-muted hover:bg-surface-muted hover:text-ink'"
                @click="store.selectProjectFile(file.path)"
              >
                📄 {{ file.name }}
              </button>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          title="模板选择"
          icon="outline"
          body-class="p-3"
        >
          <TemplatePicker />
          <button
            v-if="store.selectedTemplate"
            class="mt-2 w-full rounded border border-line-soft px-2 py-1.5 text-xs text-ink-muted hover:bg-surface-muted hover:text-ink"
            @click="store.openStylePanel()"
          >
            🎨 样式映射
          </button>
          <button
            v-else
            disabled
            class="mt-2 w-full rounded border border-line-soft px-2 py-1.5 text-xs text-ink-muted/50"
          >
            先选择模板以编辑样式映射
          </button>
        </SectionCard>
      </aside>

      <!-- Main content: editor + preview + export -->
      <div class="flex min-w-0 flex-1 flex-col gap-4">
        <InlineMessage
          v-if="store.fallbackReason"
          tone="warn"
          class="mb-4"
        >
          {{ store.fallbackReason }}
        </InlineMessage>

        <div class="grid items-start gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <!-- Left: authoring -->
          <div class="flex min-w-0 flex-col gap-4">
            <SectionCard
              title="Markdown 编辑器"
              icon="code"
              description="左侧写内容，右侧实时查看文档结构"
              body-class="flex min-h-0 flex-col p-4"
            >
              <MarkdownEditor
                ref="editorRef"
                v-model="store.markdown"
                :disabled="store.exporting"
              />
            </SectionCard>

            <SectionCard
              title="模板与封皮"
              icon="document"
            >
              <div class="space-y-4">
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

          <!-- Right: preview, export, destruction -->
          <div class="flex min-w-0 flex-col gap-4 xl:sticky xl:top-[76px]">
            <SectionCard
              title="文档结构预览"
              icon="outline"
              description="由 Markdown 解析出的标题树与节点统计"
              body-class="flex max-h-[26rem] min-h-0 flex-col p-4"
            >
              <StructurePreview @select-line="handleSelectLine" />
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
      </div>
    </main>

    <StyleMappingPanel />

    <footer class="border-t border-line-soft bg-surface">
      <p class="mx-auto max-w-[1600px] px-4 py-3 text-xs text-ink-muted">
        DocXForge · 本地优先渲染，源文与产物均不落持久化存储。
      </p>
    </footer>
  </div>
</template>
