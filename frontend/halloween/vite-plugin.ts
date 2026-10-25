import { readFile } from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import type { Plugin } from 'vite'

const PUBLIC_RESOURCES = [
  ...Array.from({ length: 7 }, (_, index) => `carousel-image${index + 1}.png`),
  'button-fingers.png',
  'button-web.svg',
  'evil-pumpkin.png',
  'logo-halloween.svg',
  'manifest.json',
  'theme.css',
]
const RESOURCE_NAMES = new Set(PUBLIC_RESOURCES)

/** Publish only the theme's browser resources; keep code and documentation private. */
export default function halloweenThemePlugin(): Plugin {
  let themeDirectory = ''
  let requestPrefix = '/seasonal/halloween/'

  return {
    name: 'halloween-home-theme',
    configResolved(config) {
      themeDirectory = path.resolve(config.root, 'halloween')
      const base = config.base.startsWith('/') ? config.base : '/'
      requestPrefix = `${base.replace(/\/$/, '')}/seasonal/halloween/`
    },
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const pathname = new URL(request.url ?? '/', 'http://localhost').pathname
        if (!pathname.startsWith(requestPrefix)) {
          next()
          return
        }
        if (request.method !== 'GET' && request.method !== 'HEAD') {
          response.statusCode = 405
          response.setHeader('Allow', 'GET, HEAD')
          response.end()
          return
        }

        const filename = pathname.slice(requestPrefix.length)
        if (!RESOURCE_NAMES.has(filename)) {
          response.statusCode = 404
          response.end()
          return
        }

        void readFile(path.join(themeDirectory, filename)).then((contents) => {
          response.setHeader('Content-Type', filename.endsWith('.png') ? 'image/png'
            : filename.endsWith('.svg') ? 'image/svg+xml'
              : filename.endsWith('.css') ? 'text/css; charset=utf-8' : 'application/json; charset=utf-8')
          response.setHeader('Content-Length', contents.length)
          response.setHeader('Cache-Control', filename === 'manifest.json' ? 'no-store' : 'no-cache')
          response.end(request.method === 'HEAD' ? undefined : contents)
        }, () => {
          response.statusCode = 404
          response.end()
        })
      })
    },
    generateBundle() {
      for (const filename of PUBLIC_RESOURCES) {
        this.emitFile({
          type: 'asset',
          fileName: `seasonal/halloween/${filename}`,
          source: readFileSync(path.join(themeDirectory, filename)),
        })
      }
    },
  }
}
