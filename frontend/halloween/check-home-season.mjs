import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import ts from 'typescript'

const source = (await readFile(new URL('./homeSeason.ts', import.meta.url), 'utf8'))
  .replace('import.meta.env.BASE_URL', JSON.stringify('/'))
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const manifest = {
  version: 1,
  revision: 'test-v1',
  images: Array.from({ length: 7 }, (_, index) => `carousel-image${index + 1}.png`),
  decorations: {
    buttonFingers: 'button-fingers.png',
    buttonWeb: 'button-web.svg',
    evilPumpkin: 'evil-pumpkin.png',
    logo: 'logo-halloween.svg',
  },
  stylesheet: 'theme.css',
}

async function scenario({ response = manifest, status = 200, imageError = false, stylesheetError = false } = {}) {
  const attributes = new Map()
  const properties = new Map()
  const links = []
  const requests = []
  const imageRequests = []
  const exports = {}
  const context = {
    exports,
    require: (name) => {
      assert.equal(name, 'vue')
      return {
        computed: (get) => ({ get value() { return get() } }),
        shallowRef: (value) => ({ value }),
        onMounted: (callback) => callback(),
      }
    },
    window: { setTimeout, clearTimeout, location: { origin: 'https://deceit.test' } },
    document: {
      documentElement: {
        setAttribute: (key, value) => attributes.set(key, value),
        removeAttribute: (key) => attributes.delete(key),
        style: {
          setProperty: (key, value) => properties.set(key, value),
          removeProperty: (key) => properties.delete(key),
        },
      },
      createElement: () => ({ remove() { this.removed = true } }),
      head: {
        append: (link) => {
          links.push(link)
          queueMicrotask(() => stylesheetError ? link.onerror?.() : link.onload?.())
        },
      },
    },
    Image: class {
      naturalWidth = 1214
      naturalHeight = 988
      decode() { return Promise.resolve() }
      set src(value) {
        imageRequests.push(value)
        const failedFilename = imageError === true ? 'carousel-image7.png' : imageError
        queueMicrotask(() => failedFilename && value.includes(failedFilename) ? this.onerror?.() : this.onload?.())
      }
    },
    fetch: async (url, options) => {
      requests.push({ url: String(url), options })
      return {
        ok: status >= 200 && status < 300,
        json: async () => {
          if (response === 'html') throw new SyntaxError('Unexpected token <')
          return response
        },
      }
    },
    URL,
    AbortController,
  }
  vm.runInNewContext(compiled, context)
  const season = exports.useHomeSeason()
  for (let attempt = 0; attempt < 30; attempt += 1) await Promise.resolve()
  return { season, attributes, properties, links, requests, imageRequests }
}

for (const [name, options] of [
  ['missing manifest', { status: 404 }],
  ['HTML fallback with status 200', { response: 'html' }],
  ['invalid manifest shape', { response: { ...manifest, images: [] } }],
  ['missing decorations', { response: { ...manifest, decorations: undefined } }],
  ['invalid decoration path', { response: { ...manifest, decorations: { ...manifest.decorations, logo: '../logo.svg' } } }],
  ['missing seventh image', { imageError: true }],
  ['missing fingers', { imageError: 'button-fingers.png' }],
  ['missing button cobweb', { imageError: 'button-web.svg' }],
  ['missing pumpkin', { imageError: 'evil-pumpkin.png' }],
  ['missing bloody logo', { imageError: 'logo-halloween.svg' }],
  ['missing stylesheet', { stylesheetError: true }],
]) {
  const result = await scenario(options)
  assert.equal(result.season.seasonActive.value, false, name)
  assert.equal(result.season.seasonImage(0, 'original.png'), 'original.png', name)
  assert.equal(result.attributes.has('data-home-season'), false, name)
  assert.equal(result.properties.size, 0, name)
  assert.ok(result.links.every((link) => link.removed), name)
}

const loaded = await scenario()
assert.equal(loaded.requests[0].options.cache, 'no-store')
assert.equal(loaded.season.seasonActive.value, true)
assert.equal(loaded.attributes.get('data-home-season'), 'halloween')
assert.equal(loaded.season.seasonImage(6, 'original.png'), 'https://deceit.test/seasonal/halloween/carousel-image7.png?v=test-v1')
assert.equal(loaded.links[0].media, 'all')
assert.equal(loaded.imageRequests.length, 11)
assert.equal(loaded.properties.get('--home-season-button-fingers'), 'url("https://deceit.test/seasonal/halloween/button-fingers.png?v=test-v1")')
assert.equal(loaded.properties.get('--home-season-button-web'), 'url("https://deceit.test/seasonal/halloween/button-web.svg?v=test-v1")')
assert.equal(loaded.properties.get('--home-season-evil-pumpkin'), 'url("https://deceit.test/seasonal/halloween/evil-pumpkin.png?v=test-v1")')
assert.equal(loaded.properties.get('--home-season-logo'), 'url("https://deceit.test/seasonal/halloween/logo-halloween.svg?v=test-v1")')
loaded.season.resetHomeSeason()
assert.equal(loaded.season.seasonActive.value, false)
assert.equal(loaded.season.seasonImage(6, 'original.png'), 'original.png')
assert.equal(loaded.attributes.has('data-home-season'), false)
assert.equal(loaded.links[0].removed, true)
assert.equal(loaded.properties.size, 0)

// A fresh page after deleting the optional folder must ignore assets from an earlier page.
const refreshed = await scenario({ status: 404 })
assert.equal(refreshed.season.seasonActive.value, false)
assert.equal(refreshed.season.seasonImage(6, 'original.png'), 'original.png')
assert.equal(refreshed.properties.size, 0)
console.log('Home season checks passed: activation, versioned decorations, rollback, deleted folder, invalid manifest, image/decorations and CSS failures.')
