import seo from './seo.json'

const websiteId = `${seo.siteUrl}/#website`
const website = {
  '@type': 'WebSite', '@id': websiteId,
  name: 'deceit.games', alternateName: 'Deceit', url: `${seo.siteUrl}/`,
  inLanguage: 'ru-RU', description: seo.home.description,
}

function serialize(): string {
  const url = `${seo.siteUrl}/`
  const graph: Record<string, unknown>[] = [website, {
    '@type': 'WebPage', '@id': `${url}#webpage`, url,
    name: seo.home.title, description: seo.home.description,
    inLanguage: 'ru-RU', isPartOf: { '@id': websiteId },
  }]
  graph.push({
    '@type': 'WebApplication', '@id': `${seo.siteUrl}/#webapplication`,
    name: 'deceit.games', url, applicationCategory: 'GameApplication',
    operatingSystem: 'Web', inLanguage: 'ru-RU',
    image: `${seo.siteUrl}/pwa-512-v20260717.png`, description: seo.home.description,
    isPartOf: { '@id': websiteId },
  })
  return JSON.stringify({ '@context': 'https://schema.org', '@graph': graph }).replace(/</g, '\\u003c')
}

export const PUBLIC_SCHEMAS = { home: serialize() }
