import {
  checkHtml, checkRobots, checkSitemap,
  cspAllowsHash, findMeta, jsonLdBlocks, pwaIcon192, pwaIcon512, seo, socialPreview,
  verificationPath, verificationToken,
} from './check-seo.mjs'

const args = process.argv.slice(2)
let origin = seo.siteUrl
if (args.length === 1 && !args[0].startsWith('--')) origin = args[0]
else if (args.length === 2 && args[0] === '--origin') origin = args[1]
else if (args.length) {
  console.error('Usage: node scripts/check-seo-live.mjs [origin] (or --origin URL)')
  process.exit(1)
}
let base
try {
  base = new URL(origin)
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password
    || base.pathname !== '/' || base.search || base.hash) throw new Error('Use an HTTP(S) origin without credentials, path, query or fragment.')
} catch (error) {
  console.error(`Invalid origin: ${error.message}`)
  process.exit(1)
}

const failures = []
const check = (condition, message) => { if (!condition) failures.push(message) }
const production = base.origin === new URL(seo.siteUrl).origin
const canonical = (path) => new URL(path, seo.siteUrl).href
let requestCount = 0
async function request(path, { method = 'GET', url = new URL(path, base).href } = {}) {
  requestCount++
  try {
    const response = await fetch(url, {
      method, redirect: 'manual', signal: AbortSignal.timeout(15000),
      headers: { 'User-Agent': 'Deceit-SEO-Check/1.0', 'Cache-Control': 'no-cache' },
    })
    const bytes = Buffer.from(await response.arrayBuffer())
    return { response, bytes, text: bytes.toString('utf8'), url }
  } catch (error) {
    const cause = error.cause?.message ?? ''
    check(false, `${method} ${url}: ${error.message}${cause ? ` (${cause})` : ''}. Check DNS, reachability and certificate coverage; TLS verification remains enabled.`)
    return null
  }
}

function hasNoindex(response) { return /\bnoindex\b/i.test(response.headers.get('x-robots-tag') ?? '') }
function status(result, expected) {
  if (result) check(result.response.status === expected, `${result.url}: expected HTTP ${expected}, got ${result.response.status}`)
}
function mime(result, pattern, description) {
  if (result) check(pattern.test(result.response.headers.get('content-type') ?? ''), `${result.url}: must be served as ${description}, got ${result.response.headers.get('content-type') ?? 'no Content-Type'}`)
}
async function redirect(path, destination, options) {
  const result = await request(path, options)
  if (!result) return
  check([301, 308].includes(result.response.status), `${result.url}: expected permanent redirect, got ${result.response.status}`)
  const location = result.response.headers.get('location')
  check(location && new URL(location, result.url).href === destination, `${result.url}: redirect must point directly to ${destination}; got ${location ?? 'missing Location'}`)
}
async function homepage() {
  const path = '/'
  const result = await request(path)
  if (!result) return
  status(result, 200)
  mime(result, /text\/html/i, 'HTML')
  check(!hasNoindex(result.response), `${path}: public page must not send X-Robots-Tag: noindex`)
  checkHtml(result.text, check)
  check(findMeta(result.text, 'name', 'yandex-verification') === verificationToken, 'home: published Yandex meta token is incorrect')
  const csp = result.response.headers.get('content-security-policy') ?? ''
  for (const { hash } of jsonLdBlocks(result.text)) check(cspAllowsHash(csp, hash), `${path}: HTTP CSP header blocks current JSON-LD (${hash}); update nginx hashes`)
  const head = await request(path, { method: 'HEAD' })
  status(head, 200)
  if (head) check(!hasNoindex(head.response), `${path}: HEAD response must also permit indexing`)
  const assets = Array.from(result.text.matchAll(/(?:src|href)=["'](\/assets\/[^"']+)["']/g), ([, asset]) => asset)
  for (const asset of new Set(assets)) {
    const loaded = await request(asset)
    status(loaded, 200)
    mime(loaded, asset.endsWith('.js') ? /(?:javascript|ecmascript)/i : /text\/css/i, asset.endsWith('.js') ? 'JavaScript' : 'CSS')
  }
}

console.log(`Checking SEO HTTP behavior at ${base.origin}; canonical metadata is ${seo.siteUrl}.`)
await Promise.all([
  homepage(),
  ...['/rules', '/admin', '/moderation', '/profile', '/history', '/room/1'].map(async (path) => {
    const result = await request(path)
    status(result, 200)
    mime(result, /text\/html/i, 'SPA HTML')
    if (result) {
      check(hasNoindex(result.response), `${path}: excluded SPA HTML must send X-Robots-Tag: noindex`)
      check(/<script\b[^>]*type=["']module["']/i.test(result.text), `${path}: existing direct link must serve the SPA entry point`)
    }
  }),
  ...['/does-not-exist-seo-check', '/room/not-a-number', '/missing-seo-verification.html', '/rules/index.html'].map(async (path) => status(await request(path), 404)),
  redirect('/rules/', canonical('/rules')),
  redirect('/index.html?seo-check=1', canonical('/?seo-check=1')),
  ...['/profile/', '/room/1/'].map((path) => redirect(path, canonical(path.slice(0, -1)))),
  (async () => {
    const result = await request('/robots.txt')
    status(result, 200)
    mime(result, /text\/plain/i, 'plain text')
    if (result) checkRobots(result.text, check)
  })(),
  (async () => {
    const result = await request('/sitemap.xml')
    status(result, 200)
    mime(result, /(?:application|text)\/xml/i, 'XML')
    if (result) checkSitemap(result.text, check)
  })(),
  (async () => {
    const result = await request(verificationPath)
    status(result, 200)
    mime(result, /text\/html/i, 'verification HTML')
    if (result) check(/<body\b[^>]*>\s*Verification:\s*1e1d0459b7904581\s*<\/body>/i.test(result.text), 'Yandex HTML verification file must contain the exact token; it must not return the SPA')
  })(),
  (async () => {
    const result = await request('/manifest.webmanifest')
    status(result, 200)
    mime(result, /application\/(?:manifest\+json|json)/i, 'web manifest JSON')
    if (!result) return
    try {
      const manifest = JSON.parse(result.text)
      const icons = manifest.icons?.map((icon) => icon.src) ?? []
      check(manifest.start_url === '/' && manifest.scope === '/' && icons.includes(pwaIcon192) && icons.includes(pwaIcon512), 'Published PWA manifest has stale start URL, scope or icons')
    } catch { check(false, 'Published manifest.webmanifest is not valid JSON') }
    check(/(?:no-cache|no-store|max-age=0)/i.test(result.response.headers.get('cache-control') ?? ''), 'manifest.webmanifest must be revalidated for PWA updates')
  })(),
  (async () => {
    const result = await request('/sw.js')
    status(result, 200)
    mime(result, /javascript/i, 'service-worker JavaScript')
    if (result) check(/(?:no-cache|no-store|max-age=0)/i.test(result.response.headers.get('cache-control') ?? ''), 'sw.js must be revalidated for PWA updates')
  })(),
  ...[pwaIcon192, pwaIcon512, socialPreview].map(async (path) => {
    const result = await request(path)
    status(result, 200)
    mime(result, /image\/png/i, 'PNG image')
    if (result) check(result.bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), `${path}: response must contain a PNG, not SPA/error HTML`)
  }),
])

if (production) {
  const http = new URL('/?seo-check=1', base)
  http.protocol = 'http:'
  const www = new URL('/?seo-check=1', base)
  www.hostname = `www.${base.hostname}`
  const wwwHttp = new URL(www)
  wwwHttp.protocol = 'http:'
  await Promise.all([
    redirect('/', canonical('/?seo-check=1'), { url: http.href }),
    redirect('/', canonical('/?seo-check=1'), { url: www.href }),
    redirect('/', canonical('/?seo-check=1'), { url: wwwHttp.href }),
  ])
} else console.log('Custom origin: public www/HTTP/TLS canonical-host tests are skipped; run against the default origin after deployment.')

if (failures.length) {
  console.error(`SEO live validation failed (${failures.length} findings / ${requestCount} requests):\n${failures.map((failure) => `- ${failure}`).join('\n')}`)
  process.exitCode = 1
} else console.log(`SEO live validation passed (${requestCount} requests): pages, redirects, crawl controls, assets, verification and TLS.`)
