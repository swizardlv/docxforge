<script setup lang="ts">
import AppIcon, { type IconName } from '@/components/ui/AppIcon.vue'

withDefaults(
  defineProps<{ title: string; icon?: IconName; description?: string; bodyClass?: string }>(),
  { icon: undefined, description: undefined, bodyClass: 'p-4' },
)
</script>

<template>
  <section class="df-card flex min-h-0 flex-col">
    <header class="flex items-center gap-2 border-b border-line-soft px-4 py-3">
      <AppIcon
        v-if="icon"
        :name="icon"
        class="size-[18px] shrink-0 text-accent"
      />
      <div class="min-w-0 flex-1">
        <h2 class="truncate text-sm font-bold tracking-wide text-ink uppercase">
          {{ title }}
        </h2>
        <p
          v-if="description"
          class="mt-0.5 text-xs text-ink-muted"
        >
          {{ description }}
        </p>
      </div>
      <slot name="actions" />
    </header>
    <div
      class="min-h-0 flex-1"
      :class="bodyClass"
    >
      <slot />
    </div>
  </section>
</template>
