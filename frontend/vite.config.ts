/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import { imagetools } from 'vite-imagetools'

/**
 * Production Content-Security-Policy, injected as a <meta> tag at build time only (the dev server
 * needs inline scripts for HMR). Defence in depth for the JS-readable auth tokens (API_ALIGNMENT Q3).
 * `frame-ancestors` can't be set via <meta>, so hosting must send it as a header (docs/SECURITY.md).
 */
function contentSecurityPolicy(apiBaseUrl: string): Plugin {
  const apiOrigin = /^https?:\/\//i.test(apiBaseUrl) ? new URL(apiBaseUrl).origin : ''
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    // style-src needs 'unsafe-inline' for React `style` attributes (e.g. hero object-position).
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: ${apiOrigin}`.trim(),
    "font-src 'self'",
    `connect-src 'self' ${apiOrigin}`.trim(),
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ')

  return {
    name: 'moonlight:csp',
    apply: 'build',
    transformIndexHtml: () => [
      {
        tag: 'meta',
        attrs: { 'http-equiv': 'Content-Security-Policy', content: csp },
        injectTo: 'head-prepend',
      },
    ],
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load .env files for the config itself. Empty prefix = also read non-VITE_ vars, which stay
  // server-side (only VITE_* vars that client code references reach the bundle).
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [
      react(),
      tailwindcss(),
      // Resizes / re-encodes images at build time from query params
      // (e.g. `hero.webp?w=480;960&format=webp&as=srcset`). Source files are never modified.
      // Image imports live only in the src/assets/*.ts manifests (docs/ASSETS.md).
      imagetools(),
      contentSecurityPolicy(env.VITE_API_BASE_URL ?? '/api/v1'),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    build: {
      rolldownOptions: {
        output: {
          // Stable vendor chunks: library code rarely changes, so browsers keep it cached across
          // deploys while app chunks (which change often) are re-downloaded on their own.
          advancedChunks: {
            groups: [
              { name: 'vendor-react', test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
              { name: 'vendor-router', test: /node_modules[\\/](react-router|react-router-dom)[\\/]/ },
              { name: 'vendor-ui', test: /node_modules[\\/](clsx|tailwind-merge|lucide-react)[\\/]/ },
            ],
          },
        },
      },
    },
    server: {
      port: 5173,
      // Forward backend paths to FastAPI so the browser never hits CORS locally.
      // /static serves catalogue/template thumbnails referenced by relative URLs in API responses.
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/static': { target: apiTarget, changeOrigin: true },
      },
    },
    test: {
      include: ['src/**/*.test.{ts,tsx}'],
      environment: 'node',
      restoreMocks: true,
      unstubGlobals: true,
    },
  }
})
