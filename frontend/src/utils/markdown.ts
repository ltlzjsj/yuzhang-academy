import MarkdownIt from 'markdown-it'
// @ts-ignore — no types for markdown-it-katex
import mdKatex from 'markdown-it-katex'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import DOMPurify from 'dompurify'
import 'highlight.js/styles/atom-one-light.css'
import 'katex/dist/katex.min.css'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('python', python)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)

const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang, ignoreIllegals: true }).value}</code></pre>`
      } catch {
        /* fallthrough */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  },
})

// Render $inline$ and $$block$$ as KaTeX.
md.use(mdKatex, { throwOnError: false, errorColor: '#cc0000' })

// 预处理：把 `SiO$_2$`、`Fe$_3$O$_4$` 这种"文字+裸下标/上标"模式
// 合并成整体 `$SiO_2$` / `$Fe_3O_4$`，避免 KaTeX 把下标切成独立片段、
// 然后浏览器在空格/片段边界换行导致视觉错位。
function mergeChemSubscripts(src: string): string {
  // 反复应用：吃掉 `Word$_X$` 或 `Word$^X$`，把 Word 纳入前一个 math
  // Word = 连续的 ASCII 字母/数字（化学式片段，如 SiO, CaMg, Fe）
  let prev = ''
  let cur = src
  const re = /([A-Za-z][A-Za-z0-9]*)\$([_^])\{?([A-Za-z0-9+\-,]+)\}?\$/g
  while (prev !== cur) {
    prev = cur
    cur = cur.replace(re, (_m, word, op, sub) => `$${word}${op}{${sub}}$`)
  }
  // 再把 `$A$$B$` 这种相邻 math 合并成 `$AB$`（针对 Fe$_3$O$_4$ 展开后的情况）
  cur = cur.replace(/\$([^$\n]+)\$\$([^$\n]+)\$/g, (_m, a, b) => `$${a}${b}$`)
  return cur
}

export function renderMarkdown(src: string): string {
  const pre = mergeChemSubscripts(src || '')
  const raw = md.render(pre)
  return DOMPurify.sanitize(raw, {
    // Preserve KaTeX markup
    ADD_ATTR: ['class', 'style', 'aria-hidden'],
  })
}
