/**
 * Lightweight structural scan of the Markdown source.
 *
 * This is a preview aid only - the authoritative AST is produced server-side by
 * the renderer module. We deliberately avoid pulling a full Markdown parser
 * into the bundle: the right panel just needs a heading tree plus block counts.
 */

export interface OutlineNode {
  id: string
  level: number
  text: string
  /** 1-based line number in the source. */
  line: number
  children: OutlineNode[]
}

export interface DocumentStats {
  headings: number
  paragraphs: number
  lists: number
  listItems: number
  tables: number
  codeBlocks: number
  quotes: number
  images: number
  characters: number
  /** CJK-aware: each CJK glyph counts as one word. */
  words: number
  estimatedPages: number
}

export interface OutlineResult {
  tree: OutlineNode[]
  flat: OutlineNode[]
  stats: DocumentStats
}

const ATX_HEADING = /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/
const SETEXT_UNDERLINE = /^ {0,3}(=+|-{2,})\s*$/
const FENCE = /^ {0,3}(`{3,}|~{3,})/
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+\S/
const BLOCKQUOTE = /^ {0,3}>/
const THEMATIC_BREAK = /^ {0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})$/
const TABLE_DELIMITER = /^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/
const IMAGE = /!\[[^\]]*\]\([^)]*\)/g
const WORDS_PER_PAGE = 420

/** Strips inline Markdown markers so headings read cleanly in the tree. */
export function stripInline(text: string): string {
  return text
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/(\*|_)(.*?)\1/g, '$2')
    .replace(/~~(.*?)~~/g, '$1')
    .trim()
}

function countWords(text: string): number {
  const cjk = text.match(/[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g)?.length ?? 0
  const latin = text
    .replace(/[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g, ' ')
    .split(/\s+/)
    .filter((token) => /[\p{L}\p{N}]/u.test(token)).length
  return cjk + latin
}

function buildTree(flat: OutlineNode[]): OutlineNode[] {
  const roots: OutlineNode[] = []
  const stack: OutlineNode[] = []
  for (const node of flat) {
    while (stack.length > 0) {
      const top = stack[stack.length - 1]
      if (top && top.level >= node.level) {
        stack.pop()
      } else {
        break
      }
    }
    if (stack.length === 0) {
      roots.push(node)
    } else {
      const parent = stack[stack.length - 1]
      if (parent) {
        parent.children.push(node)
      }
    }
    stack.push(node)
  }
  return roots
}

export function parseOutline(markdown: string): OutlineResult {
  const lines = markdown.split(/\r?\n/)
  const flat: OutlineNode[] = []
  const stats: DocumentStats = {
    headings: 0,
    paragraphs: 0,
    lists: 0,
    listItems: 0,
    tables: 0,
    codeBlocks: 0,
    quotes: 0,
    images: 0,
    characters: markdown.length,
    words: 0,
    estimatedPages: 0,
  }

  let fence: string | null = null
  let inList = false
  let inQuote = false
  let inTable = false
  let paragraphOpen = false
  let prose = ''

  const pushHeading = (level: number, raw: string, line: number) => {
    const text = stripInline(raw)
    if (!text) {
      return
    }
    stats.headings += 1
    flat.push({ id: `h-${line}-${flat.length}`, level, text, line, children: [] })
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    if (line === undefined) {
      continue
    }

    const fenceMatch = line.match(FENCE)

    if (fence) {
      if (fenceMatch && line.trim().startsWith(fence)) {
        fence = null
      }
      continue
    }
    if (fenceMatch && fenceMatch[1]) {
      fence = fenceMatch[1].slice(0, 3)
      stats.codeBlocks += 1
      paragraphOpen = false
      inList = false
      inQuote = false
      inTable = false
      continue
    }

    stats.images += line.match(IMAGE)?.length ?? 0

    if (!line.trim()) {
      paragraphOpen = false
      inList = false
      inQuote = false
      inTable = false
      continue
    }

    const atx = line.match(ATX_HEADING)
    if (atx && atx[1] && atx[2]) {
      pushHeading(atx[1].length, atx[2], index + 1)
      prose += `${stripInline(atx[2])} `
      paragraphOpen = false
      inList = false
      inQuote = false
      inTable = false
      continue
    }

    // Setext heading: underline directly below an open paragraph line.
    if (paragraphOpen && SETEXT_UNDERLINE.test(line) && !THEMATIC_BREAK.test(line)) {
      const previous = lines[index - 1] ?? ''
      const level = line.trim().startsWith('=') ? 1 : 2
      stats.paragraphs = Math.max(0, stats.paragraphs - 1)
      pushHeading(level, previous, index)
      paragraphOpen = false
      continue
    }

    if (THEMATIC_BREAK.test(line)) {
      paragraphOpen = false
      inList = false
      inQuote = false
      inTable = false
      continue
    }

    const listMatch = line.match(LIST_ITEM)
    if (listMatch) {
      if (!inList) {
        stats.lists += 1
        inList = true
      }
      stats.listItems += 1
      prose += `${stripInline(line.replace(LIST_ITEM, ''))} `
      paragraphOpen = false
      inQuote = false
      inTable = false
      continue
    }
    inList = false

    if (BLOCKQUOTE.test(line)) {
      if (!inQuote) {
        stats.quotes += 1
        inQuote = true
      }
      prose += `${stripInline(line.replace(/^ {0,3}>\s?/, ''))} `
      paragraphOpen = false
      inTable = false
      continue
    }
    inQuote = false

    if (line.trim().startsWith('|')) {
      const next = lines[index + 1] ?? ''
      if (!inTable && next.includes('-') && TABLE_DELIMITER.test(next)) {
        stats.tables += 1
        inTable = true
      }
      if (inTable) {
        prose += `${stripInline(line.replace(/\|/g, ' '))} `
        paragraphOpen = false
        continue
      }
    }
    if (inTable && TABLE_DELIMITER.test(line)) {
      continue
    }
    inTable = false

    if (!paragraphOpen) {
      stats.paragraphs += 1
      paragraphOpen = true
    }
    prose += `${stripInline(line)} `
  }

  stats.words = countWords(prose)
  stats.estimatedPages = stats.words > 0 ? Math.max(1, Math.ceil(stats.words / WORDS_PER_PAGE)) : 0

  return { tree: buildTree(flat), flat, stats }
}
