import type { Directive, DirectiveBinding } from 'vue'
import { getImageURL, parseAvatarVersion } from '@/services/mediaCache'

type MinioVal = | string | { key: string; version?: number; placeholder?: string; fallback?: string; lazy?: boolean }

type ElEx = HTMLImageElement & { __m_req?: number; __m_obs?: IntersectionObserver | null }

function norm(v: unknown): { key: string; version?: number; placeholder?: string; fallback?: string; lazy: boolean } {
  if (typeof v === 'string') return { key: v, lazy: true }
  const o = (v ?? {}) as any
  return {
    key: String(o.key || ''),
    version: typeof o.version === 'number' ? o.version : undefined,
    placeholder: typeof o.placeholder === 'string' ? o.placeholder : undefined,
    fallback: typeof o.fallback === 'string' ? o.fallback : undefined,
    lazy: o.lazy !== false,
  }
}

async function loadInto(el: ElEx, val: MinioVal) {
  const { key, version, placeholder, fallback } = norm(val)
  const myReq = (el.__m_req = (el.__m_req || 0) + 1)

  if (!key) {
    if (placeholder) el.src = placeholder
    return
  }

  if (placeholder && !el.src) el.src = placeholder

  const v = typeof version === 'number' ? version : parseAvatarVersion(key.split('/').pop() || '')

  try {
    const url = await getImageURL(key, v)
    if (el.__m_req === myReq) el.src = url
  } catch {
    if (fallback && el.__m_req === myReq) el.src = fallback
  }
}

function mount(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  el.setAttribute('referrerpolicy', 'no-referrer')
  el.loading = 'lazy'

  const run = () => loadInto(el, binding.value)

  const { lazy } = norm(binding.value)
  if (lazy && 'IntersectionObserver' in window) {
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          try { obs.disconnect() } catch {}
          el.__m_obs = null
          run()
        }
      })
    }, { rootMargin: '200px' })
    el.__m_obs = obs
    obs.observe(el)
  } else {
    run()
  }
}

function update(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  loadInto(el, binding.value)
}

function unmount(el: ElEx) {
  try { el.__m_obs?.disconnect() } catch {}
  el.__m_obs = null
  el.__m_req = 0
}

const minioImg: Directive<ElEx, MinioVal> = { mounted: mount, updated: update, unmounted: unmount }
export default minioImg
