import type { Directive, DirectiveBinding } from 'vue'
import { getImageURL, parseAvatarVersion, releaseImageURL } from '@/services/mediaCache'

type MinioVal = | string | {
  key: string
  version?: number
  placeholder?: string
  fallback?: string
  lazy?: boolean
  animated?: boolean
  animateOnHover?: boolean
  gifMode?: 'still' | 'hover' | 'animated'
}

type ElEx = HTMLImageElement & {
  __m_req?: number
  __m_obs?: IntersectionObserver | null
  __m_key?: string
  __m_sig?: string
  __m_keys?: Set<string>
  __m_still_url?: string
  __m_anim_key?: string
  __m_anim_url?: string
  __m_anim_loading?: Promise<void>
  __m_hovering?: boolean
  __m_hover_enter?: (() => void)
  __m_hover_leave?: (() => void)
  __m_load?: (() => void)
  __m_error?: (() => void)
}

type Norm = {
  key: string
  version?: number
  placeholder?: string
  fallback?: string
  lazy: boolean
  gifMode?: 'still' | 'hover' | 'animated'
}

function isAvatarGifKey(key: string): boolean {
  return /^avatars\/.+\.gif(?:[?#].*)?$/i.test(key)
}

function staticAvatarGifKey(key: string): string {
  return key.replace(/\.gif((?:[?#].*)?)$/i, '.png$1')
}

function norm(v: unknown): Norm {
  if (typeof v === 'string') return { key: v, lazy: true }
  const o = (v ?? {}) as any
  const key = String(o.key || '')
  let gifMode: Norm['gifMode']
  if (o.gifMode === 'still' || o.gifMode === 'hover' || o.gifMode === 'animated') {
    gifMode = o.gifMode
  } else if (o.animated === true) {
    gifMode = 'animated'
  } else if (o.animateOnHover === true) {
    gifMode = 'hover'
  } else if (o.animateOnHover === false) {
    gifMode = 'still'
  } else if (isAvatarGifKey(key)) {
    gifMode = 'hover'
  }
  return {
    key,
    version: typeof o.version === 'number' ? o.version : undefined,
    placeholder: typeof o.placeholder === 'string' ? o.placeholder : undefined,
    fallback: typeof o.fallback === 'string' ? o.fallback : undefined,
    lazy: o.lazy !== false,
    gifMode,
  }
}

function versionFor(key: string, version?: number): number {
  return typeof version === 'number' ? version : parseAvatarVersion(key.split('/').pop() || '')
}

function releaseTracked(el: ElEx) {
  if (!el.__m_keys) return
  for (const key of el.__m_keys) {
    try { releaseImageURL(key) } catch {}
  }
  el.__m_keys.clear()
  el.__m_still_url = undefined
  el.__m_anim_key = undefined
  el.__m_anim_url = undefined
  el.__m_anim_loading = undefined
}

function trackKey(el: ElEx, key: string) {
  if (!el.__m_keys) el.__m_keys = new Set()
  el.__m_keys.add(key)
}

function clearHover(el: ElEx) {
  if (el.__m_hover_enter) el.removeEventListener('pointerenter', el.__m_hover_enter)
  if (el.__m_hover_leave) el.removeEventListener('pointerleave', el.__m_hover_leave)
  el.__m_hover_enter = undefined
  el.__m_hover_leave = undefined
  el.__m_hovering = false
}

function clearLoadListeners(el: ElEx) {
  if (el.__m_load) el.removeEventListener('load', el.__m_load)
  if (el.__m_error) el.removeEventListener('error', el.__m_error)
  el.__m_load = undefined
  el.__m_error = undefined
}

function setImageSource(el: ElEx, src: string, req: number) {
  clearLoadListeners(el)
  const finish = (state: 'loaded' | 'error') => {
    if (el.__m_req !== req) return
    clearLoadListeners(el)
    el.dataset.minioState = state
  }
  let decoding = false
  const onLoad = async () => {
    if (el.__m_req !== req || decoding) return
    decoding = true
    try { await el.decode() } catch {}
    finish(el.naturalWidth > 0 ? 'loaded' : 'error')
  }
  el.__m_load = () => { void onLoad() }
  el.__m_error = () => finish('error')
  el.addEventListener('load', el.__m_load)
  el.addEventListener('error', el.__m_error)
  el.src = src
  if (el.complete && el.naturalWidth > 0) void onLoad()
}

function setupHover(el: ElEx, avatarKey: string, stillUrl: string, version?: number) {
  clearHover(el)
  el.__m_still_url = stillUrl
  el.__m_anim_key = avatarKey
  const enter = () => {
    el.__m_hovering = true
    const req = el.__m_req || 0
    if (el.__m_anim_url) {
      el.src = el.__m_anim_url
      return
    }
    if (el.__m_anim_loading) return
    el.__m_anim_loading = getImageURL(avatarKey, versionFor(avatarKey, version))
      .then((url) => {
        if ((el.__m_req || 0) !== req) {
          try { releaseImageURL(avatarKey) } catch {}
          return
        }
        trackKey(el, avatarKey)
        el.__m_anim_url = url
        if (el.__m_hovering) el.src = url
      })
      .catch(() => {})
      .finally(() => {
        el.__m_anim_loading = undefined
      })
  }
  const leave = () => {
    el.__m_hovering = false
    if (el.__m_still_url) el.src = el.__m_still_url
  }
  el.__m_hover_enter = enter
  el.__m_hover_leave = leave
  el.addEventListener('pointerenter', enter)
  el.addEventListener('pointerleave', leave)
}

async function loadInto(el: ElEx, val: MinioVal) {
  const { key, version, placeholder, fallback, gifMode } = norm(val)
  const myReq = (el.__m_req = (el.__m_req || 0) + 1)
  clearLoadListeners(el)
  el.dataset.minioState = 'loading'
  let sourceChanged = false
  if (el.__m_key && el.__m_key !== key) {
    clearHover(el)
    releaseTracked(el)
    el.__m_key = undefined
    el.__m_sig = undefined
    sourceChanged = true
  }
  if (!key) {
    clearHover(el)
    releaseTracked(el)
    el.__m_key = undefined
    el.__m_sig = undefined
    if (placeholder) setImageSource(el, placeholder, myReq)
    else el.dataset.minioState = 'error'
    return
  }
  const useStaticGif = isAvatarGifKey(key) && gifMode !== 'animated'
  const sourceKey = useStaticGif ? staticAvatarGifKey(key) : key
  const sig = `${key}|${sourceKey}|${typeof version === 'number' ? version : ''}|${gifMode || ''}`
  if (el.__m_sig && el.__m_sig !== sig) {
    clearHover(el)
    releaseTracked(el)
    sourceChanged = true
  }
  if ((sourceChanged || !el.src) && placeholder) el.src = placeholder
  const v = versionFor(sourceKey, version)
  try {
    const url = await getImageURL(sourceKey, v)
    if (el.__m_req === myReq) {
      setImageSource(el, url, myReq)
      trackKey(el, sourceKey)
      el.__m_key = key
      el.__m_sig = sig
      if (useStaticGif && gifMode === 'hover') setupHover(el, key, url, version)
      else clearHover(el)
    } else {
      releaseImageURL(sourceKey)
    }
  } catch {
    if (el.__m_req === myReq) {
      const fallbackSrc = fallback || placeholder
      if (fallbackSrc) setImageSource(el, fallbackSrc, myReq)
      else {
        if (sourceChanged) el.removeAttribute('src')
        el.dataset.minioState = 'error'
      }
    }
  }
}

function mount(el: ElEx, binding: DirectiveBinding<MinioVal>) {
  el.setAttribute('referrerpolicy', 'no-referrer')
  el.dataset.minioState = 'loading'
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
  if (prev && cur.key === prev.key && cur.version === prev.version && cur.gifMode === prev.gifMode) return
  loadInto(el, binding.value)
}

function unmount(el: ElEx, _binding: DirectiveBinding<MinioVal>) {
  try { el.__m_obs?.disconnect() } catch {}
  clearLoadListeners(el)
  clearHover(el)
  el.__m_obs = null
  el.__m_req = 0
  releaseTracked(el)
  el.__m_key = undefined
  el.__m_sig = undefined
}

const minioImg: Directive<ElEx, MinioVal> = { mounted: mount, updated: update, unmounted: unmount }
export default minioImg
