<script lang="ts">
/**
 * Single stroke-icon component. All glyphs are inline SVG paths - no emoji and
 * no icon font, so they inherit `currentColor` and stay crisp at any size.
 */
export const ICON_PATHS = {
  logo: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5', 'm9 15 1.4-3.2L13.6 10l-3.2-1.4'],
  document: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5'],
  upload: ['M12 16V4', 'm7 9 5-5 5 5', 'M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2'],
  download: ['M12 4v12', 'm7 11 5 5 5-5', 'M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2'],
  shield: ['M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z', 'm9.2 12 2 2 3.6-3.8'],
  trash: [
    'M4 7h16',
    'M10 11v6',
    'M14 11v6',
    'M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12',
    'M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2',
  ],
  refresh: ['M20 12a8 8 0 1 1-2.34-5.66', 'M20 4v5h-5'],
  alert: ['M12 8.5v5', 'M12 17h.01', 'M10.3 3.9 2.6 17a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z'],
  check: ['m5 13 4 4L19 7'],
  spinner: ['M12 3a9 9 0 1 0 9 9'],
  bolt: ['M13 3 5 14h6l-1 7 8-11h-6z'],
  outline: ['M8 6h12', 'M8 12h12', 'M8 18h12', 'M4 6h.01', 'M4 12h.01', 'M4 18h.01'],
  plus: ['M12 5v14', 'M5 12h14'],
  clock: ['M12 7.5V12l2.8 1.8', 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z'],
  server: ['M4 5.5h16v5H4z', 'M4 13.5h16v5H4z', 'M7.5 8h.01', 'M7.5 16h.01'],
  table: ['M4 5h16v14H4z', 'M4 10h16', 'M10 10v9'],
  code: ['m9 8-4 4 4 4', 'm15 8 4 4-4 4'],
  quote: ['M8 7H5v5h3l-1 5', 'M18 7h-3v5h3l-1 5'],
  image: ['M4 5h16v14H4z', 'm5 17 5-5 3 3 2.5-2.5L20 16', 'M9 9.5h.01'],
} as const

export type IconName = keyof typeof ICON_PATHS
</script>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ name: IconName; spin?: boolean }>(), { spin: false })

const paths = computed(() => ICON_PATHS[props.name])
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
    :class="spin ? 'df-spin' : undefined"
  >
    <path
      v-for="(d, index) in paths"
      :key="index"
      :d="d"
    />
  </svg>
</template>

<style scoped>
.df-spin {
  animation: df-rotate 900ms linear infinite;
}

@keyframes df-rotate {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .df-spin {
    animation: none;
  }
}
</style>
