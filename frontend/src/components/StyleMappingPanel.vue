<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import InlineMessage from '@/components/ui/InlineMessage.vue'
import { useForgeStore } from '@/stores/forge'
import { ROLE_LABELS, ROLE_ORDER, type StyleMap, type StyleRole } from '@/types/api'

const store = useForgeStore()

const dirty = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)

/** Build a local draft of the style_map that the user edits. */
const draftMap = ref<StyleMap | null>(null)

watch(
  () => store.templateStyles,
  (ts) => {
    if (ts) {
      draftMap.value = JSON.parse(JSON.stringify(ts.style_map))
      dirty.value = false
    }
  },
  { immediate: true },
)

function setRole(styleId: string, role: StyleRole): void {
  if (!draftMap.value) return
  // Clear the previous assignment for this role
  for (const key of ROLE_ORDER) {
    if (key === 'unused') continue
    const mapKey = roleToMapKey(key)
    if (mapKey && draftMap.value[mapKey as keyof StyleMap] === styleId) {
      ;(draftMap.value as Record<string, unknown>)[mapKey as string] = ''
    }
  }
  // Assign the new role
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
  for (const s of store.templateStyles?.styles ?? []) {
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
</script>

<template>
  <div
    v-if="store.stylePanelOpen"
    class="fixed inset-0 z-50 flex items-start justify-end bg-black/20 backdrop-blur-[1px]"
    @click.self="handleClose"
  >
    <div class="flex h-full w-full max-w-lg flex-col bg-surface shadow-xl">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-line-soft px-4 py-3">
        <h2 class="text-base font-semibold text-ink">
          样式映射 · {{ store.selectedTemplate?.name ?? '' }}
        </h2>
        <button
          class="rounded p-1 text-ink-muted hover:bg-surface-muted hover:text-ink"
          @click="handleClose"
        >
          ✕
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto p-4">
        <InlineMessage
          v-if="store.stylesLoading"
          tone="info"
        >
          加载样式…
        </InlineMessage>
        <InlineMessage
          v-else-if="store.stylesError"
          tone="error"
        >
          {{ store.stylesError.message }}
        </InlineMessage>
        <InlineMessage
          v-else-if="!store.templateStyles?.styles?.length"
          tone="warn"
        >
          该模板没有可识别的样式。若模板是在旧版本中上传的，请删除后重新上传以提取样式。
        </InlineMessage>

        <div
          v-else
          class="space-y-2"
        >
          <div
            v-for="entry in store.templateStyles.styles"
            :key="entry.style_id"
            class="rounded-md border border-line-soft bg-surface-muted/40 p-3"
          >
            <div class="flex items-center justify-between">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-ink">{{ entry.name || entry.style_id }}</span>
                  <span class="rounded bg-line-soft px-1.5 py-0.5 text-[10px] text-ink-muted">{{ entry.type }}</span>
                </div>
                <div class="mt-0.5 flex flex-wrap gap-x-3 gap-y-0 text-[11px] text-ink-muted">
                  <span v-if="entry.font">字体: {{ entry.font }}</span>
                  <span v-if="entry.size_pt">字号: {{ entry.size_pt }}pt</span>
                  <span v-if="entry.bold">粗体</span>
                  <span v-if="entry.italic">斜体</span>
                  <span v-if="entry.color">色: {{ entry.color }}</span>
                </div>
              </div>
              <select
                class="ml-3 shrink-0 rounded border border-line-soft bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-accent"
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
                  {{ role !== 'unused' && assignedRoles.has(role) && roleOf(entry.style_id) !== role ? '(已占用)' : '' }}
                </option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between border-t border-line-soft px-4 py-3">
        <InlineMessage
          v-if="saveError"
          tone="error"
          class="flex-1"
        >
          {{ saveError }}
        </InlineMessage>
        <span
          v-else-if="dirty"
          class="text-xs text-ink-muted"
        >
          有未保存的修改
        </span>
        <span
          v-else
          class="text-xs text-ink-muted"
        />
        <div class="flex gap-2">
          <button
            class="rounded border border-line-soft px-3 py-1.5 text-sm text-ink hover:bg-surface-muted disabled:opacity-50"
            :disabled="!dirty || saving"
            @click="dirty = false; draftMap = store.templateStyles ? JSON.parse(JSON.stringify(store.templateStyles.style_map)) : null"
          >
            重置
          </button>
          <button
            class="rounded bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent/90 disabled:opacity-50"
            :disabled="!dirty || saving"
            @click="handleSave"
          >
            {{ saving ? '保存中…' : '保存映射' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>