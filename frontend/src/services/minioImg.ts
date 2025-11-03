import type { Directive, DirectiveBinding } from 'vue'
import { getImageURL, parseAvatarVersion, retainImageURL, releaseImageURL } from '@/services/mediaCache'

type MinioVal = | string | {
  key: string
  version?: number
  placeholder?: string
  fallback?: string
  lazy?: boolean
}

type ElEx = HTMLImageElement & {
  __m_req?: number
  __m_obs?: IntersectionObserver | null
  __m_key?: string
}

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
  if (el.__m_key && el.__m_key !== key) {
    try { releaseImageURL(el.__m_key) } catch {}
    el.__m_key = undefined
  }
  if (!key) {
    if (placeholder) el.src = placeholder
    return
  }
  if (!el.src && placeholder) el.src = placeholder
  const v = typeof version === 'number' ? version : parseAvatarVersion(key.split('/').pop() || '')
  try {
    const url = await getImageURL(key, v)
    if (el.__m_req === myReq) {
      el.src = url
      el.__m_key = key
    } else {
      releaseImageURL(key)
    }
  } catch {
    if (fallback && el.__m_req === myReq) el.src = fallback
  }
}

function mount(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  el.setAttribute('referrerpolicy', 'no-referrer')
  const { lazy } = norm(binding.value)
  el.loading = lazy ? 'lazy' : 'eager'
  const run = () => loadInto(el, binding.value)
  if (lazy && 'IntersectionObserver' in window) {
    const obs = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) {
        try { obs.disconnect() } catch {}
        el.__m_obs = null
        run()
      }
    }, { rootMargin: '200px' })
    el.__m_obs = obs
    obs.observe(el)
  } else {
    run()
  }
}

function update(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  const cur = norm(binding.value)
  const prev = binding.oldValue ? norm(binding.oldValue as any) : null
  if (prev && cur.key === prev.key && cur.version === prev.version) return
  loadInto(el, binding.value)
}

function unmount(el: ElEx, _binding: DirectiveBinding<MinioVal>) {
  try { el.__m_obs?.disconnect() } catch {}
  el.__m_obs = null
  el.__m_req = 0
  if (el.__m_key) {
    try { releaseImageURL(el.__m_key) } catch {}
    el.__m_key = undefined
  }
}

const minioImg: Directive<ElEx, MinioVal> = { mounted: mount, updated: update, unmounted: unmount }
export default minioImg
