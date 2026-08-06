import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { crx } from '@crxjs/vite-plugin'
import manifest from './manifest.json'

const isExtension = process.env.BUILD_TARGET === 'ext'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tailwindcss(),
    react(), 
    ...(isExtension ? [crx({ manifest }) as any] : [])
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
