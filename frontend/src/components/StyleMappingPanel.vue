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
            <h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">
              📄 封皮预览
            </h3>
            <div class="space-y-2 rounded-lg border border-line-soft bg-surface-muted/30 p-4">
              <div
                v-for="(item, idx) in (preview.cover as any[] || [])"
                :key="idx"
                class="border-b border-line-soft/50 pb-2 last:border-0 last:pb-0"
              >
                <template v-if="item.type === 'paragraph'">
                  <p class="text-sm leading-relaxed text-ink">
                    {{ item.text }}
                  </p>
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
                          class="border border-line-soft px-2 py-1 text-ink"
                        >
                          {{ cell }}
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