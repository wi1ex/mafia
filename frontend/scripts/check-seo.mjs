import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const frontendRoot = resolve(import.meta.dirname, '..')
const publicRoot = resolve(frontendRoot, 'public')
const siteUrl = 'https://deceit.games'

function fail(message) {
  throw new Error(`SEO check failed: ${message}`)
}

function read(file) {
  if (!existsSync(file)) fail(`missing ${file}`)
  return readFileSync(file, 'utf8')
}

function findMeta(html, attribute, name) {
  const tag = new RegExp(`<meta\\s+[^>]*${attribute}=["']${name}["'][^>]*>`, 'i').exec(html)?.[0]
  return tag ? /content=["']([^"']+)["']/i.exec(tag)?.[1]?.trim() || '' : ''
}

const rootHtml = read(resolve(frontendRoot, 'index.html'))
const title = /<title>([^<]+)<\/title>/i.exec(rootHtml)?.[1]?.trim() || ''
const description = findMeta(rootHtml, 'name', 'description')
const canonical = /<link\s+[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["']/i.exec(rootHtml)?.[1] || ''

if (!/<html\s+lang=["']ru["']/i.test(rootHtml)) fail('root document must declare lang="ru"')
if (!title) fail('root document has no title')
if (!description) fail('root document has no meta description')
if (canonical !== `${siteUrl}/`) fail(`root canonical is incorrect: ${canonical || 'missing'}`)
if (!/index, follow/i.test(findMeta(rootHtml, 'name', 'robots'))) fail('root robots directive must allow indexing')
if (!findMeta(rootHtml, 'property', 'og:title') || !findMeta(rootHtml, 'property', 'og:description')) {
  fail('root document is missing Open Graph metadata')
}
if (!rootHtml.includes(`${siteUrl}/pwa-512.png`)) fail('root document must use the existing social-preview image')
if (/<noscript\b/i.test(rootHtml)) fail('root document must not add visible no-JavaScript content')

const jsonLdBlocks = Array.from(
  rootHtml.matchAll(/<script\s+type=["']application\/ld\+json["']\s*>([\s\S]*?)<\/script>/gi),
  ([, json]) => json.trim(),
)
if (!jsonLdBlocks.length) fail('root document has no JSON-LD')
for (const jsonLd of jsonLdBlocks) {
  try {
    JSON.parse(jsonLd)
  } catch {
    fail('root document has invalid JSON-LD')
  }
}

const sitemap = read(resolve(publicRoot, 'sitemap.xml'))
const sitemapUrls = Array.from(sitemap.matchAll(/<loc>([^<]+)<\/loc>/g), ([, url]) => url)
if (sitemapUrls.length !== 1 || sitemapUrls[0] !== `${siteUrl}/`) {
  fail('sitemap.xml must contain only the existing public root URL')
}

const robots = read(resolve(publicRoot, 'robots.txt'))
if (!robots.includes(`Sitemap: ${siteUrl}/sitemap.xml`)) fail('robots.txt is missing the canonical sitemap')
if (/Disallow:\s+\/(?:admin|moderation|profile|history|rules|room)/i.test(robots)) {
  fail('private SPA routes must expose server-side noindex instead of being blocked in robots.txt')
}

const nginx = read(resolve(frontendRoot, '../nginx/nginx.conf.template'))
for (const expected of ['map $request_uri $seo_robots_tag', 'X-Robots-Tag $seo_robots_tag', 'try_files $uri /index.html;']) {
  if (!nginx.includes(expected)) fail(`nginx config is missing ${expected}`)
}
for (const unwanted of ['error_page 404 /404.html;', 'try_files $uri $uri/ =404;', 'location = /mafia-online']) {
  if (nginx.includes(unwanted)) fail(`nginx config must not change visitor-visible routing: ${unwanted}`)
}

const router = read(resolve(frontendRoot, 'src/router/index.ts'))
if (!router.includes("{ path: '/:pathMatch(.*)*', redirect: { name: 'home' } }")) {
  fail('the original unknown-route behavior must remain unchanged')
}

const home = read(resolve(frontendRoot, 'src/pages/Home.vue'))
const header = read(resolve(frontendRoot, 'src/components/Header.vue'))
if (home.includes('home-seo-summary') || header.includes('href="/mafia-online/"')) {
  fail('visitor-visible SEO content or navigation must not be added')
}

for (const path of [
  'mafia-online',
  'kak-igrat-v-mafiyu',
  'roli-v-mafii',
  'pravila-mafii',
  'igry-s-translyaciyami',
  'og-mafia-online.png',
  'seo.css',
  '404.html',
]) {
  if (existsSync(resolve(publicRoot, path))) fail(`visitor-visible SEO artifact remains: ${path}`)
}
if (existsSync(resolve(frontendRoot, 'src/pages/NotFound.vue'))) fail('visitor-visible NotFound page remains')
if (!existsSync(resolve(publicRoot, 'pwa-512.png'))) fail('existing social-preview image is missing')

console.log('SEO source validation passed for the existing public URL without UI additions.')
