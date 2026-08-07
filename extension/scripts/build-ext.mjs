import { execSync } from 'node:child_process'
import { cpSync, mkdirSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const staticDir = path.join(root, 'static')
const distDir = path.join(root, 'dist')

// 1. Build the React popup (default vite build -> dist/).
execSync('npx vite build', { cwd: root, stdio: 'inherit' })

// 2. Copy static extension files (background/offscreen/content/manifest) into dist/.
for (const file of readdirSync(staticDir)) {
  const src = path.join(staticDir, file)
  if (statSync(src).isFile()) {
    cpSync(src, path.join(distDir, file))
  }
}

mkdirSync(distDir, { recursive: true })
console.log('[build-ext] Extension assembled in dist/.')
