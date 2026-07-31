<script setup lang="ts">
import { computed } from 'vue'

import AppIcon, { type IconName } from '@/components/ui/AppIcon.vue'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
type Size = 'md' | 'sm'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
    icon?: IconName
    loading?: boolean
    disabled?: boolean
    type?: 'button' | 'submit'
    block?: boolean
    /** Accessible name when the label is visually hidden. */
    label?: string
  }>(),
  {
    variant: 'secondary',
    size: 'md',
    icon: undefined,
    loading: false,
    disabled: false,
    type: 'button',
    block: false,
    label: undefined,
  },
)

const emit = defineEmits<{ (event: 'click', payload: MouseEvent): void }>()

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-strong border-accent',
  secondary: 'bg-surface text-ink border-line hover:bg-surface-muted hover:border-brand-soft',
  danger: 'bg-danger text-white border-danger hover:bg-[#991b1b]',
  ghost: 'bg-transparent text-ink-soft border-transparent hover:bg-surface-muted',
}

const isBlocked = computed(() => props.disabled || props.loading)

const classes = computed(() => [
  'inline-flex items-center justify-center gap-2 rounded-md border font-semibold',
  'transition-colors duration-150 select-none cursor-pointer',
  'disabled:cursor-not-allowed disabled:opacity-55',
  props.size === 'sm' ? 'min-h-11 px-3 text-sm' : 'min-h-11 px-4 text-[15px]',
  props.block ? 'w-full' : '',
  VARIANTS[props.variant],
])

function onClick(event: MouseEvent) {
  if (isBlocked.value) {
    return
  }
  emit('click', event)
}
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="isBlocked"
    :aria-busy="loading ? 'true' : undefined"
    :aria-label="label"
    @click="onClick"
  >
    <AppIcon
      v-if="loading"
      name="spinner"
      spin
      class="size-[18px] shrink-0"
    />
    <AppIcon
      v-else-if="icon"
      :name="icon"
      class="size-[18px] shrink-0"
    />
    <span class="truncate"><slot /></span>
  </button>
</template>
