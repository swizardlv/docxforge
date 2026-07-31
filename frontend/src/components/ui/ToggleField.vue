<script setup lang="ts">
defineProps<{ label: string; hint?: string; disabled?: boolean }>()

const model = defineModel<boolean>({ required: true })
</script>

<template>
  <label
    class="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 transition-colors duration-150 hover:bg-surface-muted"
    :class="disabled ? 'cursor-not-allowed opacity-60' : ''"
  >
    <input
      v-model="model"
      type="checkbox"
      :disabled="disabled"
      class="size-5 shrink-0 cursor-pointer rounded border-line accent-[#0369a1]"
    >
    <span class="min-w-0">
      <span class="block text-sm font-medium text-ink">{{ label }}</span>
      <span
        v-if="hint"
        class="block text-xs text-ink-muted"
      >{{ hint }}</span>
    </span>
  </label>
</template>
