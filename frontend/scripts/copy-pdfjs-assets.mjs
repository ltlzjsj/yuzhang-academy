// Copies pdfjs-dist CJK/font assets into public/ so Vite can serve them.
// Runs as `postinstall` and as a `prebuild` safeguard.
//
// PDF.js can't render Chinese PDFs without the bundled `cmaps/` directory
// (Adobe CJK encodings) nor render missing standard fonts without
// `standard_fonts/`. These are not JS modules — they're opaque binary
// resources loaded at runtime via HTTP, so they must be on the web root.
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const pairs = [
  ['node_modules/pdfjs-dist/cmaps', 'public/pdfjs/cmaps'],
  ['node_modules/pdfjs-dist/standard_fonts', 'public/pdfjs/standard_fonts'],
]

for (const [src, dst] of pairs) {
  const s = resolve(root, src)
  const d = resolve(root, dst)
  if (!existsSync(s)) {
    console.warn(`[copy-pdfjs-assets] skip (missing): ${src}`)
    continue
  }
  rmSync(d, { recursive: true, force: true })
  mkdirSync(dirname(d), { recursive: true })
  cpSync(s, d, { recursive: true })
  console.log(`[copy-pdfjs-assets] ${src} → ${dst}`)
}
