import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { gunzipSync } from 'node:zlib'
import { loadPublicContent } from './load-public-content.mjs'

export const frontendRoot = resolve(import.meta.dirname, '..')
export const { seo, PUBLIC_SCHEMAS } = await loadPublicContent()
export const verificationToken = '1e1d0459b7904581'
export const verificationPath = `/yandex_${verificationToken}.html`
export const socialPreview = '/og/deceit-preview-v20260801.png'
export const pwaIcon192 = '/pwa-192-v20260717.png'
export const pwaIcon512 = '/pwa-512-v20260717.png'

export function decodeHtml(value) {
  return String(value).replace(/&(?:amp|lt|gt|quot|apos|#39|#\d+|#x[0-9a-f]+);/gi, (entity) => {
    const named = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'", '&#39;': "'" }
    return named[entity.toLowerCase()] ?? String.fromCodePoint(entity[2].toLowerCase() === 'x'
      ? parseInt(entity.slice(3, -1), 16) : parseInt(entity.slice(2, -1), 10))
  })
}

export function attributes(tag) {
  return Object.fromEntries(Array.from(tag.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g),
    ([, name, double, single]) => [name.toLowerCase(), decodeHtml(double ?? single)]))
}

export function findMeta(html, attribute, name) {
  return Array.from(html.matchAll(/<meta\b[^>]*>/gi), ([tag]) => attributes(tag))
    .find((attrs) => attrs[attribute] === name)?.content ?? ''
}

export function canonicalUrl(html) {
  return Array.from(html.matchAll(/<link\b[^>]*>/gi), ([tag]) => attributes(tag))
    .find((attrs) => attrs.rel === 'canonical')?.href ?? ''
}

export function readableText(html) {
  return decodeHtml(html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim()
}

export function jsonLdBlocks(html) {
  return Array.from(html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))
    .filter(([, attrs]) => attributes(attrs).type === 'application/ld+json')
    .map(([, , raw]) => ({ raw, hash: `sha256-${createHash('sha256').update(raw).digest('base64')}` }))
}

export function cspAllowsHash(policy, hash) {
  const directives = policy.split(';').map((item) => item.trim().split(/\s+/))
  const directive = directives.find(([name]) => name === 'script-src-elem')
    ?? directives.find(([name]) => name === 'script-src')
    ?? directives.find(([name]) => name === 'default-src')
  return directive?.includes(`'${hash}'`) ?? false
}

export function checkHtml(html, check) {
  const page = 'home'
  const url = `${seo.siteUrl}/`
  const metadata = seo.home
  const title = decodeHtml(/<title\b[^>]*>([^<]*)<\/title>/i.exec(html)?.[1] ?? '').trim()
  check(/<html\b[^>]*\blang=["']ru["']/i.test(html), `${page}: HTML must declare Russian lang="ru"`)
  check(title === metadata.title, `${page}: title must match src/content/seo.json`)
  check(findMeta(html, 'name', 'description') === metadata.description, `${page}: description must match shared metadata`)
  check(canonicalUrl(html) === url, `${page}: canonical must be ${url}`)
  const robots = findMeta(html, 'name', 'robots')
  check(/\bindex\b/i.test(robots) && !/\bnoindex\b/i.test(robots), `${page}: robots must permit indexing`)
  for (const [attribute, prefix] of [['property', 'og:'], ['name', 'twitter:']]) {
    check(findMeta(html, attribute, `${prefix}title`) === metadata.title, `${page}: ${prefix}title is stale`)
    check(findMeta(html, attribute, `${prefix}description`) === metadata.description, `${page}: ${prefix}description is stale`)
    check(findMeta(html, attribute, `${prefix}image`) === `${seo.siteUrl}${socialPreview}`, `${page}: ${prefix}image must use the social preview`)
  }
  check(findMeta(html, 'property', 'og:url') === url, `${page}: og:url must match canonical`)
  const body = /<body\b[^>]*>([\s\S]*?)<\/body>/i.exec(html)?.[1] ?? ''
  check(/<div\b[^>]*\bid=["']app["'][^>]*>\s*<\/div>/i.test(body), 'home: app mount must remain empty before Vue renders the existing page')
  check(readableText(body) === '', 'home: initial HTML must not add visible SEO text')
  check(!/<style\b/i.test(html), 'home: initial HTML must not add inline SEO CSS')
  const blocks = jsonLdBlocks(html)
  check(blocks.length === 1, `${page}: expected one route-specific JSON-LD graph`)
  for (const { raw, hash } of blocks) {
    let schema
    try { schema = JSON.parse(raw) } catch { check(false, `${page}: malformed JSON-LD`); continue }
    check(raw === PUBLIC_SCHEMAS.home, `${page}: JSON-LD must match the shared schema used by client navigation`)
    check(schema['@context'] === 'https://schema.org', `${page}: incorrect JSON-LD context`)
    const graph = schema['@graph'] ?? []
    const website = graph.find((item) => item['@type'] === 'WebSite')
    const webPage = graph.find((item) => item['@type'] === 'WebPage')
    const app = graph.find((item) => item['@type'] === 'WebApplication')
    check(website?.name === 'deceit.games' && website?.url === `${seo.siteUrl}/`, `${page}: WebSite must describe the actual site`)
    check(webPage?.url === url && webPage?.['@id'] === `${url}#webpage`, `${page}: WebPage must describe this canonical URL`)
    check(webPage?.name === metadata.title && webPage?.description === metadata.description, `${page}: WebPage metadata is stale`)
    check(webPage?.isPartOf?.['@id'] === `${seo.siteUrl}/#website`, `${page}: WebPage must reference the WebSite`)
    check(app?.name === 'deceit.games' && app?.url === url, 'home: WebApplication must describe deceit.games')
    const metaCsp = findMeta(html, 'http-equiv', 'Content-Security-Policy')
    check(cspAllowsHash(metaCsp, hash), `${page}: CSP meta must allow exact inline JSON-LD bytes (${hash})`)
  }
  return blocks.map(({ hash }) => hash)
}

export function checkRobots(robots, check) {
  check(robots.split(/\r?\n/).some((line) => line.trim() === `Sitemap: ${seo.siteUrl}/sitemap.xml`), 'robots.txt must advertise the canonical sitemap')
  for (const [, path] of robots.matchAll(/^Disallow:[ \t]*(\S*)/gmi)) {
    if (!path) continue
    check(!['/', '/rules', '/assets/index.js', '/admin', '/moderation', '/profile', '/history', '/room/1']
      .some((route) => route.startsWith(path.replace(/\*.*$/, ''))), `robots.txt blocks required rendering/index directives: ${path}`)
  }
}

export function checkSitemap(sitemap, check) {
  const urls = Array.from(sitemap.matchAll(/<loc\b[^>]*>([^<]*)<\/loc>/gi), ([, url]) => decodeHtml(url.trim()))
  check(urls.length === 1 && urls[0] === `${seo.siteUrl}/`, 'sitemap.xml must contain only the canonical homepage URL')
}

function nginxLocations(source) {
  const clean = source.replace(/^\s*#.*$/gm, '')
  const locations = []
  const pattern = /\blocation\s+(?:(=|\^~|~\*?)\s+)?([^\s{]+)\s*\{/g
  for (const match of clean.matchAll(pattern)) {
    let depth = 1, quoted = '', position = match.index + match[0].length
    const start = position
    for (; position < clean.length && depth; position++) {
      const char = clean[position]
      if (quoted) { if (char === quoted && clean[position - 1] !== '\\') quoted = ''; continue }
      if (char === '"' || char === "'") quoted = char
      else if (char === '{') depth++
      else if (char === '}') depth--
    }
    locations.push({ kind: match[1] ?? '', selector: match[2], body: clean.slice(start, position - 1) })
  }
  return locations
}

function locationFor(locations, path) {
  const exact = locations.find((item) => item.kind === '=' && item.selector === path)
  if (exact) return exact
  const prefixes = locations.filter((item) => ['', '^~'].includes(item.kind) && path.startsWith(item.selector))
    .sort((left, right) => right.selector.length - left.selector.length)
  if (prefixes[0]?.kind === '^~') return prefixes[0]
  return locations.find((item) => {
    if (!item.kind.startsWith('~')) return false
    try { return new RegExp(item.selector, item.kind === '~*' ? 'i' : '').test(path) } catch { return false }
  }) ?? prefixes[0]
}

function checkNginx(source, hashes, check) {
  const policies = Array.from(source.matchAll(/add_header\s+Content-Security-Policy\s+"([^"]+)"/g), ([, policy]) => policy)
  check(policies.length > 0, 'nginx must send a Content-Security-Policy header')
  for (const hash of hashes) check(policies.every((policy) => cspAllowsHash(policy, hash)), `nginx CSP header must allow current public-page JSON-LD (${hash}) in all header declarations`)
  const locations = nginxLocations(source)
  for (const path of ['/does-not-exist-seo-check', '/missing-verification.html', '/room/not-a-number', '/rules/index.html']) {
    const body = locationFor(locations, path)?.body ?? ''
    check(/(?:return\s+404\b|try_files\s+[^;]*=404\s*;)/.test(body) && !/try_files\s+[^;]*\/index\.html\s*;/.test(body), `nginx must return real 404 for unknown URL ${path}`)
  }
  const excludedRoutes = ['/rules', '/admin', '/moderation', '/profile', '/history', '/room/1']
  for (const path of excludedRoutes) check(/\/index\.html/.test(locationFor(locations, path)?.body ?? ''), `nginx must serve the SPA for known route ${path}`)
  check(/add_header\s+X-Robots-Tag\b/.test(source) && /noindex/.test(source), 'nginx must send server-side noindex for excluded routes')
  const robotsMaps = Array.from(source.matchAll(/map\s+\$(?:request_uri|uri)\s+(\$\w+)\s*\{([^}]+)\}/g))
    .filter(([, variable]) => source.includes(`X-Robots-Tag ${variable}`))
  for (const [, , map] of robotsMaps) {
    const directives = Array.from(map.matchAll(/~(\S+)\s+"([^"]+)"\s*;/g))
    for (const path of ['/', ...excludedRoutes]) {
      const directive = directives.find(([, expression]) => {
        try { return new RegExp(expression).test(path) } catch { return false }
      })
      check(path === '/' ? !/noindex/.test(directive?.[2] ?? '') : /noindex/.test(directive?.[2] ?? ''), `nginx indexing directive is incorrect for ${path}`)
    }
  }
  for (const path of ['/manifest.webmanifest', '/sw.js']) check(/(?:expires\s+-1|Cache-Control\s+[^;]*(?:no-cache|no-store|max-age=0))/.test(locationFor(locations, path)?.body ?? ''), `${path} must revalidate for PWA updates`)
}

async function main() {
  const args = process.argv.slice(2)
  if (args.some((arg) => arg !== '--built')) throw new Error('Usage: node scripts/check-seo.mjs [--built]')
  const built = args.includes('--built')
  const failures = []
  const check = (condition, message) => { if (!condition) failures.push(message) }
  const read = (file) => {
    if (!existsSync(file)) { check(false, `Missing ${file}`); return '' }
    return readFileSync(file, 'utf8')
  }
  const publicRoot = resolve(frontendRoot, 'public')
  check(seo.home.title === 'deceit.games — играйте в мафию онлайн и общайтесь в комнатах с трансляциями', 'Homepage title must retain the exact original text')
  check(seo.home.description === 'Играйте в рейтинговую мафию и улучшайте свою статистику. Смотрите совместные трансляции и общайтесь в чате. Играйте в настольные игры и заводите новых друзей', 'Homepage description must retain the exact original text')
  check(Object.keys(PUBLIC_SCHEMAS).length === 1 && Object.hasOwn(PUBLIC_SCHEMAS, 'home'), 'Only the homepage may expose a public JSON-LD schema')
  const sourceHtml = read(resolve(frontendRoot, 'index.html'))
  const hashes = new Set(Object.values(PUBLIC_SCHEMAS).map((json) => `sha256-${createHash('sha256').update(json).digest('base64')}`))
  for (const hash of checkHtml(sourceHtml, check)) hashes.add(hash)
  check(findMeta(sourceHtml, 'name', 'yandex-verification') === verificationToken, 'home: Yandex verification meta token is incorrect')
  check(/<body\b[^>]*>\s*Verification:\s*1e1d0459b7904581\s*<\/body>/i.test(read(resolve(publicRoot, `.${verificationPath}`))), 'Yandex verification HTML must contain the exact token in its body')
  checkSitemap(read(resolve(publicRoot, 'sitemap.xml')), check)
  checkRobots(read(resolve(publicRoot, 'robots.txt')), check)
  let manifest
  try { manifest = JSON.parse(read(resolve(publicRoot, 'manifest.webmanifest'))) } catch { check(false, 'manifest.webmanifest must contain valid JSON') }
  check(manifest?.start_url === '/' && manifest?.scope === '/', 'PWA manifest must start at canonical home with root scope')
  const icons = manifest?.icons?.map((icon) => icon.src) ?? []
  check(icons.includes(pwaIcon192) && icons.includes(pwaIcon512), 'PWA manifest must use both versioned icons')
  for (const asset of [pwaIcon192, pwaIcon512, socialPreview, '/pwa-192.png', '/pwa-512.png']) {
    check(existsSync(resolve(publicRoot, `.${asset}`)), `Missing public asset ${asset}`)
    if (built) check(existsSync(resolve(frontendRoot, 'dist', `.${asset}`)), `Missing built asset ${asset}`)
  }
  check(Array.from(sourceHtml.matchAll(/<link\b[^>]*>/gi), ([tag]) => attributes(tag)).some((attrs) => attrs.rel === 'apple-touch-icon' && attrs.href === pwaIcon192), 'Apple touch icon must use the versioned PWA icon')
  check(read(resolve(frontendRoot, 'src/main.ts')).includes("updateViaCache: 'none'"), 'Service-worker registration must bypass HTTP cache for updates')
  const home = read(resolve(frontendRoot, 'src/pages/Home.vue'))
  check(/<h1\b[^>]*>Список комнат<\/h1>/.test(home) && /<main\b/.test(home), 'Home Vue page must expose the existing room-list H1 inside main')
  const carousel = read(resolve(frontendRoot, 'src/views/Carousel.vue'))
  for (const heading of ['Трансляции', 'Статистика', 'Комьюнити', 'Web App']) check(new RegExp(`<h2\\b[^>]*>${heading}<\\/h2>`).test(carousel), `Carousel heading missing: ${heading}`)
  for (const [tag] of carousel.matchAll(/<img\b[^>]*>/gi)) check(Boolean(attributes(tag).alt?.trim()), 'Carousel images must keep meaningful text alternatives')
  for (const alt of [
    'deceit — место, где игра превращается в общение: собирайтесь в комнаты, играйте в мафию и не только, общайтесь, смотрите и проводите время вместе.',
    'Проводите время вместе — от игр до фильмов.',
    'Следи за своим уровнем игры и становись сильнее!',
    'Пространство для общения и новых знакомств!',
    'Запусти платформу как отдельное приложение.',
  ]) check(carousel.includes(`alt="${alt}"`), `Carousel text alternative must retain its original text: ${alt}`)
  for (const [, path] of carousel.matchAll(/import\s+imageSlide\d+\s+from\s+['"]@\/([^'"]+)['"]/g)) check(existsSync(resolve(frontendRoot, 'src', path)), `Carousel asset is missing: ${path}`)
  check(carousel.includes('aria-label="Предыдущий блок"') && carousel.includes('aria-label="Следующий блок"'), 'Carousel controls must retain accessible labels')
  const router = read(resolve(frontendRoot, 'src/router/index.ts'))
  check(router.includes('seo.json') && router.includes('seo.home'), 'SPA homepage metadata must consume the shared original metadata')
  for (const name of ['rules', 'history', 'profile', 'admin', 'moderation', 'room']) {
    const route = new RegExp(`name:\\s*['"]${name}['"][\\s\\S]*?(?=\\n\\s*},)`).exec(router)?.[0] ?? ''
    check(/robots:\s*['"]noindex\b/.test(route), `SPA route ${name} must retain noindex metadata`)
  }
  check(!existsSync(resolve(publicRoot, 'rules/index.html')), 'Public static rules page must not be generated')
  if (built) {
    const distRoot = resolve(frontendRoot, 'dist')
    const rootHtml = read(resolve(distRoot, 'index.html'))
    check(!existsSync(resolve(distRoot, 'rules/index.html')), 'Built output must not contain a static SEO rules page')
    for (const hash of checkHtml(rootHtml, check)) hashes.add(hash)
    for (const [file, html] of [['index.html', rootHtml]]) {
      try { check(gunzipSync(readFileSync(resolve(distRoot, `${file}.gz`))).equals(Buffer.from(html)), `Built gzip is stale: ${file}.gz`) }
      catch (error) { check(false, `Cannot verify built gzip ${file}.gz: ${error.message}`) }
    }
    for (const file of ['robots.txt', 'sitemap.xml', 'manifest.webmanifest', `.${verificationPath}`]) check(read(resolve(distRoot, file)) === read(resolve(publicRoot, file)), `Built public file is stale: ${file}`)
    check(!rootHtml.includes('/src/main.ts') && /<script\b[^>]*\bsrc=["']\/assets\//i.test(rootHtml), 'Built document must reference compiled JavaScript')
    for (const html of [rootHtml]) {
      for (const [, asset] of html.matchAll(/(?:src|href)=["'](\/assets\/[^"']+)["']/g)) check(existsSync(resolve(distRoot, `.${asset}`)), `Built HTML references missing asset ${asset}`)
    }
  }
  checkNginx(read(resolve(frontendRoot, '../nginx/nginx.conf.template')), hashes, check)
  if (failures.length) {
    console.error(`SEO ${built ? 'source/build' : 'source'} validation failed (${failures.length}):\n${failures.map((item) => `- ${item}`).join('\n')}`)
    process.exitCode = 1
  } else console.log(`SEO ${built ? 'source/build' : 'source'} validation passed: original homepage metadata/UI, structured data/CSP, crawl controls, verification and PWA.`)
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((error) => { console.error(error.message); process.exitCode = 1 })
}
