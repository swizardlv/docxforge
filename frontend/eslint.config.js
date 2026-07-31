import js from '@eslint/js'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default defineConfigWithVueTs(
  {
    name: 'docxforge/ignores',
    ignores: ['dist/**', 'node_modules/**', 'coverage/**'],
  },
  {
    name: 'docxforge/files',
    files: ['**/*.{js,ts,mts,tsx,vue}'],
  },
  js.configs.recommended,
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  {
    name: 'docxforge/language-options',
    languageOptions: {
      globals: { ...globals.browser },
    },
    rules: {
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
  {
    name: 'docxforge/node-configs',
    files: ['*.config.{js,ts}'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
)
