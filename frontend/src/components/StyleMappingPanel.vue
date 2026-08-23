<script setup lang="ts">
import { ref, computed } from 'vue'

import { useForgeStore } from '@/stores/forge'
import { ROLE_LABELS, ROLE_ORDER, type StyleMap, type StyleRole } from '@/types/api'

const store = useForgeStore()

const showAdvanced = ref(false)
const dirty = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)

const draftMap = ref<StyleMap | null>(null)

const preview = computed(() => store.templatePreview)
const styles = computed(() => store.templateStyles)

// --- Cover fragment editing -------------------------------------------------
const editingFragment = ref<{
  original: string
  mode: 'fixed' | 'doc_title'
  replace: string
} | null>(null)
const editMode = ref<'fixed' | 'doc_title'>('fixed')
const editReplace = ref('')

function overrides(): Array<{ find: string; replace: string | null; mode: string }> {
  return (preview.value?.overrides as any[]) ?? []
}

function overrideFor(original: string): { find: string; replace: string | null; mode: string } | undefined {
  return overrides().find((o) => o.find === original)
}

function displayText(original: string): string {
  const ov = overrideFor(original)
  if (!ov) return original
  if (ov.mode === 'doc_title') return '{{文件标题}}'
  return ov.replace ?? original
}

function hasOverride(original: string): boolean {
  return !!overrideFor(original)
}

function openEdit(original: string): void {
  const ov = overrideFor(original)
  editMode.value = (ov?.mode as 'fixed' | 'doc_title') ?? 'fixed'
  editReplace.value = ov?.replace ?? ''
  editingFragment.value = { original, mode: editMode.value, replace: editReplace.value }
}

function cancelEdit(): void {
  editingFragment.value = null
}

async function confirmEdit(): Promise<void> {
  if (!editingFragment.value) return
  const current = overrides()
  const others = current.filter((o) => o.find !== editingFragment.value!.original)
  const newOverrides = [...others]
  if (editMode.value === 'doc_title') {
    newOverrides.push({ find: editingFragment.value.original, replace: null, mode: 'doc_title' })
  } else if (editReplace.value.trim()) {
    newOverrides.push({ find: editingFragment.value.original, replace: editReplace.value.trim(), mode: 'fixed' })
  }
  // If empty + fixed mode, remove the override (no replacement)
  editingFragment.value = null
  const ok = await store.saveCoverOverrides(newOverrides)
  if (!ok) {
    saveError.value = store.stylesError?.message ?? '保存失败'
  }
}

function setRole(styleId: string, role: StyleRole): void {
  if (!draftMap.value) return
  for (const key of ROLE_ORDER) {
    if (key === 'unused') continue
    const mapKey = roleToMapKey(key)
    if (mapKey && draftMap.value[mapKey as keyof StyleMap] === styleId) {
      ;(draftMap.value as Record<string, unknown>)[mapKey as string] = ''
    }
  }
  const mapKey = roleToMapKey(role)
  if (mapKey) {
    ;(draftMap.value as unknown as Record<string, string>)[mapKey] = styleId
  }
  dirty.value = true
}

function roleToMapKey(role: StyleRole): string | null {
  if (role === 'unused') return null
  if (role.startsWith('heading')) return 'headings'
  return role
}

function roleOf(styleId: string): StyleRole {
  if (!draftMap.value) return 'unused'
  const dm = draftMap.value
  for (const [key, val] of Object.entries(dm.headings)) {
    if (val === styleId) return `heading${key}` as StyleRole
  }
  if (dm.paragraph === styleId) return 'paragraph'
  if (dm.list_ordered === styleId) return 'list_ordered'
  if (dm.list_bullet === styleId) return 'list_bullet'
  if (dm.quote === styleId) return 'quote'
  if (dm.code === styleId) return 'code'
  if (dm.caption === styleId) return 'caption'
  if (dm.table === styleId) return 'table'
  if (dm.title === styleId) return 'title'
  return 'unused'
}

const assignedRoles = computed(() => {
  const roles = new Set<StyleRole>()
  if (!draftMap.value) return roles
  for (const s of styles.value?.styles ?? []) {
    const r = roleOf(s.style_id)
    if (r !== 'unused') roles.add(r)
  }
  return roles
})

async function handleSave(): Promise<void> {
  if (!draftMap.value || !store.templateId) return
  saving.value = true
  saveError.value = null
  const ok = await store.saveStyleMap(store.templateId, draftMap.value)
  if (ok) {
    dirty.value = false
  } else {
    saveError.value = store.stylesError?.message ?? '保存失败'
  }
  saving.value = false
}

function handleClose(): void {
  if (dirty.value) {
    if (!confirm('有未保存的修改，确定要关闭吗？')) return
  }
  store.closeStylePanel()
}

function resetDraft(): void {
  if (store.templateStyles) {
    draftMap.value = JSON.parse(JSON.stringify(store.templateStyles.style_map))
    dirty.value = false
  }
}
</script>

<template>
  <div
    v-if="store.stylePanelOpen"
    class="fixed inset-0 z-50 flex items-start justify-end bg-black/20 backdrop-blur-[1px]"
    @click.self="handleClose"
  >
    <div class="flex h-full w-full max-w-2xl flex-col bg-surface shadow-xl">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-line-soft px-4 py-3">
        <h2 class="text-base font-semibold text-ink">
          模板结构预览 · {{ store.selectedTemplate?.name ?? '' }}
        </h2>
        <button
          class="rounded p-1 text-ink-muted hover:bg-surface-muted hover:text-ink"
          @click="handleClose"
        >
          ✕
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="store.stylesLoading && !preview" class="p-6 text-center text-sm text-ink-muted">
          加载模板结构…
        </div>

        <template v-else-if="preview">
          <!-- ── ① 封皮预览 ── -->
          <section class="border-b border-line-soft px-4 py-4">
            <div class="mb-3 flex items-center justify-between">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                📄 封皮预览
              </h3>
              <span class="text-[10px] text-ink-muted">悬停文本可编辑</span>
            </div>
            <div class="space-y-2 rounded-lg border border-line-soft bg-surface-muted/30 p-4">
              <div
                v-for="(item, idx) in (preview.cover as any[] || [])"
                :key="idx"
                class="border-b border-line-soft/50 pb-2 last:border-0 last:pb-0"
              >
                <template v-if="item.type === 'paragraph'">
                  <div class="group relative flex items-start">
                    <p
                      class="cursor-pointer text-sm leading-relaxed text-ink"
                      :class="hasOverride(item.text) ? 'rounded bg-accent/10 px-0.5' : ''"
                      @click="openEdit(item.text)"
                    >
                      {{ displayText(item.text) }}
                    </p>
                    <span
                      class="ml-1 mt-0.5 cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                      @click="openEdit(item.text)"
                    >✏️</span>
                  </div>
                  <p class="mt-0.5 text-[10px] text-ink-muted">
                    样式: {{ item.style || '(无)' }}
                  </p>
                </template>
                <template v-else-if="item.type === 'table'">
                  <div class="overflow-x-auto">
                    <table class="w-full border-collapse text-xs">
                      <tr
                        v-for="(row, ri) in (item.rows as string[][] || [])"
                        :key="ri"
                      >
                        <td
                          v-for="(cell, ci) in row"
                          :key="ci"
                          class="group relative cursor-pointer border border-line-soft px-2 py-1 text-ink"
                          :class="hasOverride(cell) ? 'bg-accent/10' : ''"
                          @click="openEdit(cell)"
                        >
                          {{ displayText(cell) }}
                          <span
                            class="absolute -right-1 -top-1 cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                          >✏️</span>
                        </td>
                      </tr>
                    </table>
                  </div>
                  <p class="mt-0.5 text-[10px] text-ink-muted">
                    表格 · {{ item.rows?.length }} 行
                  </p>
                </template>
              </div>
            </div>

            <!-- Edit popover -->
            <div
              v-if="editingFragment"
              class="mt-3 rounded-lg border border-accent/40 bg-surface p-3 shadow-md"
            >
              <p class="mb-2 text-xs text-ink-muted">
                为「{{ editingFragment.original.slice(0, 30) }}」设置替换
              </p>
              <label class="flex items-center gap-2 text-xs text-ink">
                <input
                  v-model="editMode"
                  type="radio"
                  value="fixed"
                >
                  本项目固定
                <input
                  v-model="editMode"
                  type="radio"
                  value="doc_title"
                  class="ml-3"
                >
                  跟随文件标题
              </label>
              <template v-if="editMode === 'fixed'">
                <input
                  v-model="editReplace"
                  type="text"
                  class="mt-2 w-full rounded border border-line-soft bg-surface px-2 py-1 text-sm text-ink outline-none focus:border-accent"
                  placeholder="输入固定文本，留空则恢复原样"
                >
              </template>
              <p
                v-else
                class="mt-2 text-xs text-ink-muted"
              >
                渲染时此处替换为当前文件标题
              </p>
              <div class="mt-2 flex justify-end gap-2">
                <button
                  class="rounded border border-line-soft px-2.5 py-1 text-xs text-ink hover:bg-surface-muted"
                  @click="cancelEdit"
                >
                  取消
                </button>
                <button
                  class="rounded bg-accent px-2.5 py-1 text-xs text-white hover:bg-accent/90"
                  @click="confirmEdit"
                >
                  确定
                </button>
              </div>
            </div>
            <span
              v-if="saveError"
              class="mt-2 block text-[10px] text-warn"
            >{{ saveError }}</span>
          </section>

          <!-- ── ② 标题层级预览 ── -->
          <section class="border-b border-line-soft px-4 py-4">
            <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">
              🔤 标题层级
            </h3>
            <div class="space-y-2">
              <div
                v-for="h in (preview.headings as any[] || [])"
                :key="h.level"
                class="flex items-center gap-3 rounded-lg border border-line-soft px-3 py-2"
              >
                <span
                  class="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-accent/10 text-xs font-bold text-accent"
                >
                  H{{ h.level }}
                </span>
                <div class="min-w-0 flex-1">
                  <p
                    class="truncate"
                    :style="{
                      fontFamily: h.font || undefined,
                      fontSize: h.size_pt ? `${h.size_pt}pt` : undefined,
                      fontWeight: h.bold ? 'bold' : undefined,
                      fontStyle: h.italic ? 'italic' : undefined,
                      color: h.color ? `#${h.color}` : undefined,
                    }"
                  >
                    {{ h.sample || '标题示例' }}
                  </p>
                  <p class="text-[10px] text-ink-muted">
                    {{ h.name }} · {{ h.font || '默认字体' }} · {{ h.size_pt ? `${h.size_pt}pt` : '默认字号' }}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <!-- ── ③ 页眉页脚 ── -->
          <section class="border-b border-line-soft px-4 py-4">
            <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">
              📐 页眉 / 页脚
            </h3>
            <div class="space-y-2">
              <div class="rounded-lg border border-line-soft bg-surface-muted/30 p-3">
                <p class="text-xs text-ink-muted">页眉</p>
                <p class="mt-1 text-sm text-ink">
                  {{ preview.header_text || '（未检测到页眉）' }}
                </p>
              </div>
              <div class="rounded-lg border border-line-soft bg-surface-muted/30 p-3">
                <p class="text-xs text-ink-muted">页脚</p>
                <p class="mt-1 text-sm text-ink">
                  {{ preview.footer_text || '（未检测到页脚）' }}
                </p>
              </div>
            </div>
          </section>

          <!-- ── ④ 高级：样式映射 ── -->
          <section class="px-4 py-4">
            <button
              class="flex w-full items-center justify-between rounded border border-line-soft px-3 py-2 text-xs text-ink-muted hover:bg-surface-muted"
              @click="showAdvanced = !showAdvanced"
            >
              ⚙️ 高级：样式角色映射
              <span class="ml-1">{{ showAdvanced ? '▲' : '▼' }}</span>
            </button>
            <div v-if="showAdvanced" class="mt-3 space-y-2">
              <div
                v-for="entry in (styles?.styles || [])"
                :key="entry.style_id"
                class="rounded-md border border-line-soft bg-surface-muted/40 p-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <div class="min-w-0 flex-1">
                    <span class="text-xs font-medium text-ink">{{ entry.name || entry.style_id }}</span>
                    <span class="ml-1.5 rounded bg-line-soft px-1 py-0.5 text-[9px] text-ink-muted">{{ entry.type }}</span>
                  </div>
                  <select
                    class="shrink-0 rounded border border-line-soft bg-surface px-1.5 py-0.5 text-[11px] text-ink outline-none focus:border-accent"
                    :value="roleOf(entry.style_id)"
                    @change="setRole(entry.style_id, ($event.target as HTMLSelectElement).value as StyleRole)"
                  >
                    <option
                      v-for="role in ROLE_ORDER"
                      :key="role"
                      :value="role"
                      :disabled="role !== 'unused' && assignedRoles.has(role) && roleOf(entry.style_id) !== role"
                    >
                      {{ ROLE_LABELS[role] }}
                    </option>
                  </select>
                </div>
              </div>
              <div class="flex items-center gap-2 pt-2">
                <button
                  class="rounded border border-line-soft px-2.5 py-1 text-[11px] text-ink hover:bg-surface-muted disabled:opacity-50"
                  :disabled="!dirty"
                  @click="resetDraft"
                >
                  重置
                </button>
                <button
                  class="rounded bg-accent px-2.5 py-1 text-[11px] text-white hover:bg-accent/90 disabled:opacity-50"
                  :disabled="!dirty || saving"
                  @click="handleSave"
                >
                  {{ saving ? '保存中…' : '保存映射' }}
                </button>
                <span v-if="dirty" class="text-[10px] text-ink-muted">有未保存修改</span>
                <span v-if="saveError" class="text-[10px] text-warn">{{ saveError }}</span>
              </div>
            </div>
          </section>
        </template>

        <!-- Fallback -->
        <div v-else class="p-6 text-center text-sm text-ink-muted">
          <p>该模板暂无可预览的结构数据。</p>
          <p class="mt-1 text-xs">若模板是在旧版本中上传的，请删除后重新上传。</p>
        </div>
      </div>
    </div>
  </div>
</template>