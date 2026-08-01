# Chrome 浏览器文件夹导入兼容性修复与体验增强

## 1. 原因诊断

在 Chrome 浏览器中，`<input type="file">` 上非标准属性 `webkitdirectory` 在 Vue 模板中直接书写时，可能由于 Vue 属性处理机制未能直接渲染为 DOM 原生 attribute，导致调用 `.click()` 时无法唤起 Chrome 的目录选择器。

---

## 2. 解决方案

### 方案 A：显式 DOM 属性注入
在组件挂载阶段 (`onMounted`)，显式调用 DOM API 为输入框追加属性：
```typescript
folderInputRef.value?.setAttribute('webkitdirectory', '')
folderInputRef.value?.setAttribute('directory', '')
```

### 方案 B：Chrome 86+ 原生 `window.showDirectoryPicker()` (优先推荐)
对于 Chrome / Edge 浏览器，优先调用现代 Web 的 `showDirectoryPicker()` 原生 API：
1. 弹出流畅的操作系统原生文件夹选择框。
2. 通过 `FileSystemDirectoryHandle` 递归获取文本与图片文件。
3. 若浏览器不支持该 API 或抛出非异常，自动降级至 `<input>` 点击事件。

---

## 3. 测试与校验

- 前端 `pnpm lint` 校验通过，`pnpm build` 打包无报错。
- 后端 73/73 pytest 单元测试通过，Ruff 校验通过。
