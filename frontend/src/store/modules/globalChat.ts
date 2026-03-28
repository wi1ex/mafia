import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import type { Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { alertDialog } from '@/services/confirm'
import { formatModerationAlert } from '@/services/moderation'
import { createAuthedSocket, disposeAuthedSocket } from '@/services/sio'
import { useUserStore } from '@/store/modules/user'

const CHAT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
const CHAT_IMAGE_MAX_SIZE_LABEL = '5 МБ'
const CHAT_ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png'])
const CHAT_HISTORY_LIMIT = 100
const CHAT_SOCKET_TIMEOUT_MS = 15_000

type ConnectionState = 'idle' | 'connecting' | 'ready' | 'reconnecting' | 'error'
type MutationKind = 'none' | 'reset' | 'append' | 'prepend' | 'context'
type RawRecord = Record<string, unknown>

export interface GlobalChatPermissions {
  can_open: boolean
  can_send: boolean
  can_react: boolean
  can_delete_own: boolean
}

export interface GlobalChatReaction {
  emoji: string
  count: number
  reacted_by_me: boolean
}

export interface GlobalChatReactionParticipant {
  emoji: string
  created_at: string
  user: GlobalChatAuthor
}

export interface GlobalChatReplyPreview {
  message_id: number
  author_username: string
  avatar_name: string | null
  snippet: string
  deleted: boolean
  has_image: boolean
}

export interface GlobalChatAuthor {
  id: number
  username: string
  avatar_name: string | null
}

export interface GlobalChatMention {
  id: number
  username: string
  avatar_name: string | null
}

export interface GlobalChatMessage {
  id: number
  created_at: string
  deleted: boolean
  deleted_at: string | null
  deleted_content_available: boolean
  text: string
  author: GlobalChatAuthor
  is_own: boolean
  can_delete: boolean
  reactions: GlobalChatReaction[]
  reply: GlobalChatReplyPreview | null
  image_object_key: string | null
  mentions: GlobalChatMention[]
}

export interface GlobalChatDeletedMessagePreview {
  message_id: number
  deleted_at: string | null
  content_available: boolean
  text: string
  image_object_key: string | null
  mentions: GlobalChatMention[]
  author: GlobalChatAuthor
}

interface ChatAck {
  ok?: boolean
  status?: number
  error?: string
  detail?: unknown
  unread_count?: unknown
  marked?: boolean
  permissions?: Partial<GlobalChatPermissions>
  reactions_allowlist?: unknown[]
  messages?: unknown[]
  has_more?: boolean
  cursor_before_id?: unknown
  message?: unknown
  preview?: unknown
  reactions?: unknown[]
  participants?: unknown[]
  unread_target_message_ids?: unknown[]
}

interface ChatImagePresignResponse {
  image_object_key?: string
  upload_url?: string
  expires_in?: unknown
  content_type?: string
  upload_method?: string
  upload_fields?: Record<string, unknown>
}

function isRecord(value: unknown): value is RawRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function asPositiveInt(raw: unknown): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return 0
  const normalized = Math.trunc(value)
  return normalized > 0 ? normalized : 0
}

function asString(raw: unknown): string {
  return typeof raw === 'string' ? raw : ''
}

function normalizePositiveIntList(raw: unknown): number[] {
  if (!Array.isArray(raw)) return []
  const out: number[] = []
  const seen = new Set<number>()
  for (const item of raw) {
    const value = asPositiveInt(item)
    if (value <= 0 || seen.has(value)) continue
    seen.add(value)
    out.push(value)
  }
  out.sort((left, right) => left - right)
  return out
}

function defaultPermissions(): GlobalChatPermissions {
  return {
    can_open: false,
    can_send: false,
    can_react: false,
    can_delete_own: false,
  }
}

function buildReplySnippet(text: string, hasImage: boolean): string {
  const source = String(text || '').replace(/\s+/g, ' ').trim()
  if (!source) return hasImage ? 'Изображение' : ''
  if (source.length <= 80) return source
  return `${source.slice(0, 77).trimEnd()}...`
}

function buildDraftReplyPreview(message: GlobalChatMessage): GlobalChatReplyPreview {
  return {
    message_id: message.id,
    author_username: message.author.username || `user${message.author.id}`,
    avatar_name: message.author.avatar_name || null,
    snippet: message.deleted ? 'Сообщение удалено' : buildReplySnippet(message.text, Boolean(message.image_object_key)),
    deleted: message.deleted,
    has_image: !message.deleted && Boolean(message.image_object_key),
  }
}

function buildClientMessageId(): string {
  const nativeId = globalThis.crypto?.randomUUID?.()
  if (nativeId) return nativeId
  const template = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
  return template.replace(/[xy]/g, (part) => {
    const rnd = Math.floor(Math.random() * 16)
    const value = part === 'x' ? rnd : ((rnd & 0x3) | 0x8)
    return value.toString(16)
  })
}

export const useGlobalChatStore = defineStore('globalChat', () => {
  const open = ref(false)
  const unread = ref(0)
  const unreadTargetMessageIds = ref<number[]>([])
  const initialized = ref(false)
  const loadingInitial = ref(false)
  const loadingMore = ref(false)
  const sending = ref(false)
  const uploadingImage = ref(false)
  const messages = ref<GlobalChatMessage[]>([])
  const draft = ref('')
  const hasMore = ref(false)
  const cursorBeforeId = ref<number | null>(null)
  const permissions = ref<GlobalChatPermissions>(defaultPermissions())
  const reactionsAllowlist = ref<string[]>([])
  const connectionState = ref<ConnectionState>('idle')
  const lastError = ref('')
  const draftReplyMessageId = ref<number | null>(null)
  const draftReplyPreview = ref<GlobalChatReplyPreview | null>(null)
  const draftImagePreviewUrl = ref('')
  const draftImageName = ref('')
  const draftImageObjectKey = ref('')
  const draftClientMessageId = ref('')
  const draftClientMessageKey = ref('')
  const lastMutationKind = ref<MutationKind>('none')
  const lastMutationToken = ref(0)
  const lastMutationMessageId = ref<number | null>(null)
  const lastMutationForceScroll = ref(false)

  const reactionBusy = reactive<Record<number, boolean>>({})
  const deleteBusy = reactive<Record<number, boolean>>({})
  const purgeBusy = reactive<Record<number, boolean>>({})
  const reactionParticipantsCache = reactive<Record<number, GlobalChatReactionParticipant[]>>({})

  let socket: Socket | null = null
  let draftImageFile: File | null = null
  let bootstrapToken = 0
  let draftAssetToken = 0
  let unreadSyncInited = false
  let onUnreadCountEvent: ((event: Event) => void) | null = null
  let autoMarkUnreadTargetsPromise: Promise<void> = Promise.resolve()

  const draftHasImage = computed(() => Boolean(draftImagePreviewUrl.value || draftImageName.value || draftImageObjectKey.value))
  const draftImageUploaded = computed(() => Boolean(draftImageObjectKey.value))
  const canSendCurrentDraft = computed(() => {
    if (!open.value || sending.value || uploadingImage.value) return false
    if (connectionState.value !== 'ready') return false
    if (!permissions.value.can_send) return false
    return Boolean(draft.value.trim() || draftHasImage.value)
  })

  function currentViewerUserId(): number {
    return asPositiveInt(useUserStore().user?.id)
  }

  function currentViewerIsAdmin(): boolean {
    return asString(useUserStore().user?.role).trim().toLowerCase() === 'admin'
  }

  function applyUnreadCount(raw: unknown): void {
    unread.value = Math.max(0, asPositiveInt(raw))
  }

  function syncUnreadWithTargets(): void {
    unread.value = unreadTargetMessageIds.value.length
  }

  function clearUnreadCount(): void {
    unread.value = 0
  }

  function setUnreadTargetMessageIds(raw: unknown): void {
    unreadTargetMessageIds.value = normalizePositiveIntList(raw)
    if (open.value && initialized.value) {
      syncUnreadWithTargets()
    }
  }

  function consumeUnreadTargetMessageId(messageId: number): void {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0) return
    unreadTargetMessageIds.value = unreadTargetMessageIds.value.filter((id) => id !== normalizedMessageId)
  }

  function clearUnreadTargetMessageIds(): void {
    unreadTargetMessageIds.value = []
  }

  function syncUnreadFromProfile(): void {
    if (open.value && initialized.value) {
      syncUnreadWithTargets()
      return
    }
    applyUnreadCount(useUserStore().user?.chat_unread_count)
  }

  function ensureUnreadSync(): void {
    if (unreadSyncInited) return
    if (onUnreadCountEvent) {
      window.removeEventListener('auth-chat_unread_count', onUnreadCountEvent)
    }
    onUnreadCountEvent = (event: Event) => {
      const payload = (event as CustomEvent)?.detail
      if (open.value && initialized.value) {
        syncUnreadWithTargets()
        return
      }
      applyUnreadCount(isRecord(payload) ? payload.count : 0)
    }
    window.addEventListener('auth-chat_unread_count', onUnreadCountEvent)
    unreadSyncInited = true
  }

  function enqueueLiveAlertAutoRead(rawMessageIds: unknown): void {
    const messageIds = normalizePositiveIntList(rawMessageIds)
    if (!open.value || !initialized.value || messageIds.length === 0) return

    autoMarkUnreadTargetsPromise = autoMarkUnreadTargetsPromise
      .catch(() => {})
      .then(async () => {
        for (const messageId of messageIds) {
          if (!open.value || !initialized.value) return
          await markAlertRead(messageId)
        }
      })
  }

  function markMutation(kind: MutationKind, messageId: number | null = null, forceScroll = false): void {
    lastMutationKind.value = kind
    lastMutationMessageId.value = messageId
    lastMutationForceScroll.value = forceScroll
    lastMutationToken.value += 1
  }

  function closeSocket(): void {
    if (!socket) return
    disposeAuthedSocket(socket)
    try { socket.off() } catch {}
    try { socket.close() } catch {}
    socket = null
  }

  async function deleteDraftImageUpload(key: string): Promise<void> {
    const normalizedKey = asString(key).trim()
    if (!normalizedKey) return
    try {
      await api.delete('/users/chat/image', { params: { key: normalizedKey } })
    } catch {}
  }

  function clearDraftImage(options: { cleanupRemote?: boolean } = {}): void {
    const shouldCleanupRemote = options.cleanupRemote !== false
    const uploadedKey = asString(draftImageObjectKey.value).trim()
    draftAssetToken += 1
    if (draftImagePreviewUrl.value) {
      try { URL.revokeObjectURL(draftImagePreviewUrl.value) } catch {}
    }
    draftImagePreviewUrl.value = ''
    draftImageName.value = ''
    draftImageObjectKey.value = ''
    draftImageFile = null
    if (shouldCleanupRemote && uploadedKey) {
      void deleteDraftImageUpload(uploadedKey)
    }
  }

  function clearReplyTarget(): void {
    draftReplyMessageId.value = null
    draftReplyPreview.value = null
  }

  function clearDraft(options: { cleanupRemote?: boolean } = {}): void {
    draft.value = ''
    clearReplyTarget()
    clearDraftImage(options)
    draftClientMessageId.value = ''
    draftClientMessageKey.value = ''
  }

  function resetState(): void {
    bootstrapToken += 1
    open.value = false
    unreadTargetMessageIds.value = []
    initialized.value = false
    loadingInitial.value = false
    loadingMore.value = false
    sending.value = false
    uploadingImage.value = false
    messages.value = []
    hasMore.value = false
    cursorBeforeId.value = null
    permissions.value = defaultPermissions()
    reactionsAllowlist.value = []
    connectionState.value = 'idle'
    lastError.value = ''
    Object.keys(reactionBusy).forEach((key) => { delete reactionBusy[Number(key)] })
    Object.keys(deleteBusy).forEach((key) => { delete deleteBusy[Number(key)] })
    Object.keys(purgeBusy).forEach((key) => { delete purgeBusy[Number(key)] })
    Object.keys(reactionParticipantsCache).forEach((key) => { delete reactionParticipantsCache[Number(key)] })
    clearDraft()
    markMutation('none')
  }

  function hardReset(): void {
    closeSocket()
    resetState()
    clearUnreadCount()
    clearUnreadTargetMessageIds()
  }

  function reactionSortIndex(emoji: string): number {
    const idx = reactionsAllowlist.value.indexOf(emoji)
    return idx >= 0 ? idx : Number.MAX_SAFE_INTEGER
  }

  function normalizeReactionList(raw: unknown, previous: GlobalChatReaction[] = []): GlobalChatReaction[] {
    if (!Array.isArray(raw)) {
      return [...previous].sort((a, b) => reactionSortIndex(a.emoji) - reactionSortIndex(b.emoji))
    }
    const previousMap = new Map(previous.map((item) => [item.emoji, item.reacted_by_me]))
    const out: GlobalChatReaction[] = []
    for (const item of raw) {
      if (!isRecord(item)) continue
      const emoji = asString(item.emoji)
      const count = asPositiveInt(item.count)
      if (!emoji || count <= 0) continue
      out.push({
        emoji,
        count,
        reacted_by_me: typeof item.reacted_by_me === 'boolean'
          ? item.reacted_by_me
          : Boolean(previousMap.get(emoji)),
      })
    }
    out.sort((a, b) => {
      const order = reactionSortIndex(a.emoji) - reactionSortIndex(b.emoji)
      if (order !== 0) return order
      return a.emoji.localeCompare(b.emoji)
    })
    return out
  }

  function normalizeReply(raw: unknown): GlobalChatReplyPreview | null {
    if (!isRecord(raw)) return null
    const messageId = asPositiveInt(raw.message_id)
    if (messageId <= 0) return null
    return {
      message_id: messageId,
      author_username: asString(raw.author_username).trim() || `user${messageId}`,
      avatar_name: asString(raw.avatar_name) || null,
      snippet: asString(raw.snippet),
      deleted: Boolean(raw.deleted),
      has_image: Boolean(raw.has_image),
    }
  }

  function normalizeMentionList(raw: unknown): GlobalChatMention[] {
    if (!Array.isArray(raw)) return []
    const out: GlobalChatMention[] = []
    const seen = new Set<string>()
    for (const item of raw) {
      if (!isRecord(item)) continue
      const userId = asPositiveInt(item.id)
      const username = asString(item.username).trim()
      if (userId <= 0 || !username) continue
      const usernameKey = username.toLowerCase()
      if (seen.has(usernameKey)) continue
      seen.add(usernameKey)
      out.push({
        id: userId,
        username,
        avatar_name: asString(item.avatar_name) || null,
      })
    }
    return out
  }

  function normalizeReactionParticipants(raw: unknown): GlobalChatReactionParticipant[] {
    if (!Array.isArray(raw)) return []
    const out: GlobalChatReactionParticipant[] = []
    for (const item of raw) {
      if (!isRecord(item)) continue
      const emoji = asString(item.emoji)
      const createdAt = asString(item.created_at) || new Date().toISOString()
      const userRaw = isRecord(item.user) ? item.user : {}
      const userId = asPositiveInt(userRaw.id)
      if (!emoji || userId <= 0) continue
      out.push({
        emoji,
        created_at: createdAt,
        user: {
          id: userId,
          username: asString(userRaw.username).trim() || `user${userId}`,
          avatar_name: asString(userRaw.avatar_name) || null,
        },
      })
    }
    out.sort((left, right) => {
      const leftTime = Date.parse(left.created_at)
      const rightTime = Date.parse(right.created_at)
      if (Number.isFinite(leftTime) && Number.isFinite(rightTime) && leftTime !== rightTime) {
        return leftTime - rightTime
      }
      const order = reactionSortIndex(left.emoji) - reactionSortIndex(right.emoji)
      if (order !== 0) return order
      return left.user.username.localeCompare(right.user.username)
    })
    return out
  }

  function clearReactionParticipantsCache(messageId?: number): void {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId > 0) {
      delete reactionParticipantsCache[normalizedMessageId]
      return
    }
    Object.keys(reactionParticipantsCache).forEach((key) => { delete reactionParticipantsCache[Number(key)] })
  }

  function normalizeMessage(raw: unknown, viewerUserId: number, previous?: GlobalChatMessage): GlobalChatMessage | null {
    if (!isRecord(raw)) return null
    const id = asPositiveInt(raw.id)
    if (id <= 0) return null

    const authorRaw = isRecord(raw.author) ? raw.author : {}
    const authorId = asPositiveInt(authorRaw.id) || previous?.author.id || 0
    const authorUsername = asString(authorRaw.username).trim() || previous?.author.username || `user${authorId || id}`
    const deleted = Boolean(raw.deleted)
    const deletedContentAvailable = deleted
      ? (typeof raw.deleted_content_available === 'boolean'
          ? Boolean(raw.deleted_content_available)
          : (previous?.deleted_content_available ?? true))
      : false
    const ownByAuthor = viewerUserId > 0 && authorId === viewerUserId
    const viewerIsAdmin = currentViewerIsAdmin()

    return {
      id,
      created_at: asString(raw.created_at) || previous?.created_at || new Date().toISOString(),
      deleted,
      deleted_at: asString(raw.deleted_at) || null,
      deleted_content_available: deletedContentAvailable,
      text: deleted ? '' : asString(raw.text),
      author: {
        id: authorId,
        username: authorUsername,
        avatar_name: asString(authorRaw.avatar_name) || null,
      },
      is_own: ownByAuthor,
      can_delete: Boolean(!deleted && (ownByAuthor || viewerIsAdmin || Boolean(raw.can_delete))),
      reactions: deleted ? [] : normalizeReactionList(raw.reactions, previous?.reactions || []),
      reply: normalizeReply(raw.reply),
      image_object_key: deleted ? null : (asString(raw.image_object_key) || null),
      mentions: deleted ? [] : normalizeMentionList(raw.mentions),
    }
  }

  function normalizeDeletedPreview(raw: unknown): GlobalChatDeletedMessagePreview | null {
    if (!isRecord(raw)) return null
    const messageId = asPositiveInt(raw.message_id)
    if (messageId <= 0) return null
    const authorRaw = isRecord(raw.author) ? raw.author : {}
    const authorId = asPositiveInt(authorRaw.id)
    return {
      message_id: messageId,
      deleted_at: asString(raw.deleted_at) || null,
      content_available: Boolean(raw.content_available),
      text: asString(raw.text),
      image_object_key: asString(raw.image_object_key) || null,
      mentions: normalizeMentionList(raw.mentions),
      author: {
        id: authorId,
        username: asString(authorRaw.username).trim() || `user${authorId || messageId}`,
        avatar_name: asString(authorRaw.avatar_name) || null,
      },
    }
  }

  function currentDraftIdentity(): string {
    const imageIdentity = draftImageFile
      ? `file:${draftImageFile.name}:${draftImageFile.size}:${draftImageFile.type}:${draftImageFile.lastModified}`
      : (draftImageObjectKey.value ? `key:${draftImageObjectKey.value}` : '')
    return JSON.stringify({
      text: draft.value,
      reply_to_message_id: asPositiveInt(draftReplyMessageId.value) || 0,
      image: imageIdentity,
    })
  }

  function ensureDraftClientMessageId(): string {
    const identity = currentDraftIdentity()
    if (!draftClientMessageId.value || draftClientMessageKey.value !== identity) {
      draftClientMessageId.value = buildClientMessageId()
      draftClientMessageKey.value = identity
    }
    return draftClientMessageId.value
  }

  function mergeMessages(rawItems: unknown[]): { insertedIds: number[] } {
    if (!Array.isArray(rawItems) || rawItems.length === 0) return { insertedIds: [] }
    const viewerUserId = currentViewerUserId()
    const next = [...messages.value]
    const indexById = new Map(next.map((item, index) => [item.id, index]))
    const insertedIds: number[] = []

    for (const rawItem of rawItems) {
      const rawId = isRecord(rawItem) ? asPositiveInt(rawItem.id) : 0
      if (rawId <= 0) continue
      const existingIndex = indexById.get(rawId)
      const existing = typeof existingIndex === 'number' ? next[existingIndex] : undefined
      const normalized = normalizeMessage(rawItem, viewerUserId, existing)
      if (!normalized) continue
      if (typeof existingIndex === 'number') {
        next[existingIndex] = normalized
      } else {
        indexById.set(rawId, next.length)
        next.push(normalized)
        insertedIds.push(rawId)
      }
      if (normalized.deleted) {
        clearReactionParticipantsCache(rawId)
      }
    }

    next.sort((a, b) => a.id - b.id)
    messages.value = next
    return { insertedIds }
  }

  function replaceMessages(rawItems: unknown[]): void {
    messages.value = []
    mergeMessages(rawItems)
  }

  function applyReactionsUpdate(messageId: number, rawReactions: unknown): void {
    const idx = messages.value.findIndex((item) => item.id === messageId)
    if (idx < 0) return
    const target = messages.value[idx]
    if (target.deleted) return
    const next = [...messages.value]
    next[idx] = {
      ...target,
      reactions: normalizeReactionList(rawReactions, target.reactions),
    }
    messages.value = next
    clearReactionParticipantsCache(messageId)
  }

  function applyPermissions(raw: unknown): void {
    const next = defaultPermissions()
    if (isRecord(raw)) {
      next.can_open = Boolean(raw.can_open)
      next.can_send = Boolean(raw.can_send)
      next.can_react = Boolean(raw.can_react)
      next.can_delete_own = Boolean(raw.can_delete_own)
    }
    permissions.value = next
  }

  function applyAllowlist(raw: unknown): void {
    if (!Array.isArray(raw)) {
      reactionsAllowlist.value = []
      return
    }
    reactionsAllowlist.value = raw
      .map((item) => asString(item))
      .filter((item, index, list) => Boolean(item) && list.indexOf(item) === index)
  }

  function describePermissionError(error: string, fallback: string): string {
    switch (error) {
      case 'active_game_player':
        return 'Во время активной игры общий чат недоступен.'
      case 'chat_disabled':
        return 'Общий чат временно закрыт администратором.'
      case 'chat_messages_disabled':
        return 'Отправка сообщений в общий чат временно отключена.'
      case 'not_verified':
        return 'Для доступа к общему чату необходимо пройти верификацию.'
      case 'user_timeout':
        return 'Вам выдан таймаут. Отправка сообщений недоступна.'
      case 'user_banned':
        return 'Аккаунт забанен. Общий чат недоступен.'
      default:
        return fallback
    }
  }

  function describeSendError(status: number, error: string, detail: unknown): string {
    if (error === 'text_moderation') {
      return formatModerationAlert(detail) || 'Текст сообщения не прошёл модерацию.'
    }
    switch (error) {
      case 'empty_message':
        return 'Сообщение не должно быть пустым.'
      case 'message_too_long':
        return 'Сообщение слишком длинное.'
      case 'reply_not_found':
        return 'Исходное сообщение не найдено.'
      case 'image_not_found':
        return 'Изображение не найдено. Выберите файл заново.'
      case 'bad_image_key':
      case 'forbidden_image_prefix':
        return 'Не удалось прикрепить изображение.'
      case 'rate_limited':
        return 'Слишком много действий подряд. Попробуйте чуть позже.'
      default:
        if (status === 403) return describePermissionError(error, 'Общий чат сейчас недоступен.')
        return 'Не удалось отправить сообщение.'
    }
  }

  function describeUploadError(status: number, detail: unknown): string {
    const error = asString(detail)
    switch (error) {
      case 'unsupported_media_type':
        return 'Можно загрузить только PNG или JPEG.'
      case 'file_too_large':
        return `Файл слишком большой. Максимум ${CHAT_IMAGE_MAX_SIZE_LABEL}.`
      case 'empty_file':
        return 'Файл пустой.'
      case 'bad_image':
        return 'Не удалось обработать изображение.'
      default:
        if (status === 403) return describePermissionError(error, 'Загрузка изображения недоступна.')
        return 'Не удалось загрузить изображение.'
    }
  }

  function maybeApplyAccessLoss(status: number, error: string): void {
    if (status !== 403) return
    if (error === 'active_game_player') {
      useUserStore().setInActiveGameAsAlivePlayer(true)
    }
    if (error === 'active_game_player' || error === 'chat_disabled' || error === 'not_verified' || error === 'user_timeout' || error === 'user_banned') {
      closePanel()
    }
  }

  function ensureSocket(): Socket {
    if (socket) return socket

    socket = createAuthedSocket('/chat', {
      path: '/ws/socket.io',
      transports: ['websocket', 'polling'],
      upgrade: true,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 200,
      reconnectionDelayMax: 2000,
    })

    socket.on('connect', () => {
      if (!open.value) return
      connectionState.value = initialized.value ? 'reconnecting' : 'connecting'
      void bootstrap()
    })

    socket.on('disconnect', (reason: string) => {
      if (!open.value) {
        connectionState.value = 'idle'
        return
      }
      connectionState.value = reason === 'io client disconnect' ? 'idle' : 'reconnecting'
    })

    socket.on('connect_error', () => {
      if (!open.value) return
      loadingInitial.value = false
      connectionState.value = 'error'
      lastError.value = 'Не удалось подключить общий чат.'
    })

    socket.on('chat_message_created', (payload: unknown) => {
      const { insertedIds } = mergeMessages([payload])
      if (insertedIds.length > 0) {
        const lastInsertedId = insertedIds[insertedIds.length - 1]
        markMutation('append', lastInsertedId, false)
      }
    })

    socket.on('chat_unread_targets', (payload: unknown) => {
      const messageIds = isRecord(payload) ? payload.message_ids : []
      const nextMessageIds = normalizePositiveIntList(messageIds)
      if (open.value && initialized.value) {
        const currentMessageIds = [...unreadTargetMessageIds.value]
        const currentMessageIdSet = new Set(currentMessageIds)
        const liveMessageIds = nextMessageIds.filter((id) => !currentMessageIdSet.has(id))
        if (liveMessageIds.length > 0) {
          const liveMessageIdSet = new Set(liveMessageIds)
          setUnreadTargetMessageIds(nextMessageIds.filter((id) => !liveMessageIdSet.has(id)))
          enqueueLiveAlertAutoRead(liveMessageIds)
          return
        }
      }
      setUnreadTargetMessageIds(nextMessageIds)
    })

    socket.on('chat_message_reactions_updated', (payload: unknown) => {
      if (!isRecord(payload)) return
      const messageId = asPositiveInt(payload.message_id)
      if (messageId <= 0) return
      applyReactionsUpdate(messageId, payload.reactions)
    })

    socket.on('chat_message_deleted', (payload: unknown) => {
      mergeMessages([payload])
    })

    socket.on('chat_cleared', () => {
      messages.value = []
      hasMore.value = false
      cursorBeforeId.value = null
      unread.value = 0
      unreadTargetMessageIds.value = []
      clearReplyTarget()
      if (draftImageObjectKey.value) {
        draftImageObjectKey.value = ''
      }
      Object.keys(reactionBusy).forEach((key) => { delete reactionBusy[Number(key)] })
      Object.keys(deleteBusy).forEach((key) => { delete deleteBusy[Number(key)] })
      Object.keys(purgeBusy).forEach((key) => { delete purgeBusy[Number(key)] })
      clearReactionParticipantsCache()
      markMutation('reset')
    })

    socket.on('chat_permissions_updated', (payload: unknown) => {
      if (!open.value) return
      if (isRecord(payload) && payload.refresh) {
        void refreshPermissions(false)
        return
      }

      if (isRecord(payload) && payload.permissions) {
        applyPermissions(payload.permissions)
      } else {
        void refreshPermissions(false)
        return
      }

      const error = isRecord(payload) ? asString(payload.error) : ''
      if (Boolean(isRecord(payload) && payload.force_close)) {
        if (error === 'active_game_player') {
          useUserStore().setInActiveGameAsAlivePlayer(true)
        }
        closePanel()
      }
    })

    return socket
  }

  async function emitAck<T extends ChatAck>(event: string, payload: Record<string, unknown> = {}): Promise<T> {
    const activeSocket = ensureSocket()
    return new Promise<T>((resolve, reject) => {
      try {
        ;(activeSocket as any).timeout(CHAT_SOCKET_TIMEOUT_MS).emit(event, payload, (err: unknown, response: T) => {
          if (err) {
            reject(err)
            return
          }
          resolve(response)
        })
      } catch (error) {
        reject(error)
      }
    })
  }

  async function bootstrap(): Promise<void> {
    const activeSocket = ensureSocket()
    if (!open.value || !activeSocket.connected) return

    const token = ++bootstrapToken
    loadingInitial.value = true
    lastError.value = ''

    try {
      const response = await emitAck<ChatAck>('chat_open', { limit: CHAT_HISTORY_LIMIT })
      if (token !== bootstrapToken || !open.value) return

      if (!response?.ok) {
        loadingInitial.value = false
        if (response.permissions) applyPermissions(response.permissions)
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        const message = describePermissionError(error, 'Не удалось открыть общий чат.')
        if (status === 403) {
          maybeApplyAccessLoss(status, error)
          void alertDialog(message)
          return
        }
        connectionState.value = 'error'
        lastError.value = message
        return
      }

      applyPermissions(response.permissions)
      applyAllowlist(response.reactions_allowlist)
      replaceMessages(response.messages || [])
      hasMore.value = Boolean(response.has_more)
      cursorBeforeId.value = asPositiveInt(response.cursor_before_id) || null
      setUnreadTargetMessageIds(response.unread_target_message_ids)
      unread.value = unreadTargetMessageIds.value.length
      initialized.value = true
      connectionState.value = 'ready'
      markMutation('reset', messages.value.length > 0 ? messages.value[messages.value.length - 1].id : null, true)
    } catch {
      if (token !== bootstrapToken || !open.value) return
      connectionState.value = 'error'
      lastError.value = 'Не удалось загрузить историю общего чата.'
    } finally {
      if (token === bootstrapToken) {
        loadingInitial.value = false
      }
    }
  }

  async function refreshPermissions(notifyOnLoss = false): Promise<boolean> {
    if (!open.value || connectionState.value === 'idle') return false
    try {
      const response = await emitAck<ChatAck>('chat_permissions')
      if (!response?.ok) {
        if (response.permissions) applyPermissions(response.permissions)
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        if (status === 403) {
          maybeApplyAccessLoss(status, error)
          if (notifyOnLoss) {
            void alertDialog(describePermissionError(error, 'Общий чат сейчас недоступен.'))
          }
        }
        return false
      }

      applyPermissions(response.permissions)
      return true
    } catch {
      return false
    }
  }

  function openPanel(): void {
    if (open.value) {
      if (connectionState.value === 'error') {
        const activeSocket = ensureSocket()
        loadingInitial.value = true
        lastError.value = ''
        if (activeSocket.connected) {
          void bootstrap()
        } else {
          try { activeSocket.connect() } catch {}
        }
      }
      return
    }
    open.value = true
    connectionState.value = 'connecting'
    lastError.value = ''
    loadingInitial.value = true
    const activeSocket = ensureSocket()
    if (activeSocket.connected) {
      void bootstrap()
    }
  }

  function closePanel(): void {
    closeSocket()
    resetState()
  }

  async function loadMore(): Promise<boolean> {
    if (!open.value || loadingInitial.value || loadingMore.value || !hasMore.value) return false
    const beforeId = asPositiveInt(cursorBeforeId.value)
    if (beforeId <= 0) {
      hasMore.value = false
      return false
    }

    loadingMore.value = true
    try {
      const response = await emitAck<ChatAck>('chat_history', {
        before_id: beforeId,
        limit: CHAT_HISTORY_LIMIT,
      })
      if (!response?.ok) {
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        if (status === 403) {
          maybeApplyAccessLoss(status, error)
          void alertDialog(describePermissionError(error, 'Общий чат недоступен.'))
        }
        return false
      }

      const { insertedIds } = mergeMessages(response.messages || [])
      hasMore.value = Boolean(response.has_more)
      cursorBeforeId.value = asPositiveInt(response.cursor_before_id) || null
      if (insertedIds.length > 0) {
        markMutation('prepend')
      }
      return insertedIds.length > 0
    } catch {
      return false
    } finally {
      loadingMore.value = false
    }
  }

  async function uploadDraftImageViaPresign(file: File): Promise<string> {
    const normalizedType = asString(file.type).toLowerCase()
    const { data } = await api.post<ChatImagePresignResponse>('/users/chat/image/presign', {
      content_type: normalizedType,
    })
    const key = asString(data?.image_object_key)
    const uploadUrl = asString(data?.upload_url)
    const contentType = asString(data?.content_type) || normalizedType
    const uploadMethod = asString(data?.upload_method).toUpperCase() || 'PUT'
    if (!key || !uploadUrl) {
      throw new Error('chat_image_presign_failed')
    }

    let response: Response
    if (uploadMethod === 'POST') {
      const form = new FormData()
      const uploadFields = isRecord(data?.upload_fields) ? data.upload_fields : {}
      Object.entries(uploadFields).forEach(([field, value]) => {
        const normalizedValue = asString(value)
        if (field && normalizedValue) {
          form.append(field, normalizedValue)
        }
      })
      if (!form.has('key')) form.append('key', key)
      if (!form.has('Content-Type')) form.append('Content-Type', contentType)
      form.append('file', file, file.name || 'chat-image')
      response = await fetch(uploadUrl, {
        method: 'POST',
        body: form,
      })
    } else {
      response = await fetch(uploadUrl, {
        method: 'PUT',
        headers: {
          'Content-Type': contentType,
        },
        body: file,
      })
    }
    if (!response.ok) {
      throw new Error('chat_presigned_upload_failed')
    }
    return key
  }

  async function uploadDraftImageViaProxy(file: File): Promise<string> {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post<{ image_object_key?: string }>('/users/chat/image', form)
    const key = asString(data?.image_object_key)
    if (!key) throw new Error('image_upload_failed')
    return key
  }

  function isRecoverableUploadFailure(error: any): boolean {
    const status = asPositiveInt(error?.response?.status)
    if (!status) return true
    return status >= 500
  }

  function createHandledUploadError(): Error {
    return new Error('global_chat_upload_handled')
  }

  function isHandledUploadError(error: unknown): boolean {
    return String((error as any)?.message || '') === 'global_chat_upload_handled'
  }

  async function uploadDraftImage(file: File): Promise<string> {
    try {
      return await uploadDraftImageViaPresign(file)
    } catch (presignError: any) {
      const shouldFallback = String(presignError?.message || '') === 'chat_presigned_upload_failed'
        || isRecoverableUploadFailure(presignError)
      if (!shouldFallback) throw presignError
    }

    return uploadDraftImageViaProxy(file)
  }

  async function ensureDraftImageUploaded(): Promise<string | null> {
    if (draftImageObjectKey.value) return draftImageObjectKey.value
    if (!draftImageFile) return null

    const assetToken = draftAssetToken
    let key = ''
    uploadingImage.value = true
    try {
      key = await uploadDraftImage(draftImageFile)
    } catch (error: any) {
      const status = asPositiveInt(error?.response?.status)
      const detail = error?.response?.data?.detail
      void alertDialog(describeUploadError(status, detail))
      if (status === 403) {
        maybeApplyAccessLoss(status, asString(detail))
      }
      throw createHandledUploadError()
    } finally {
      uploadingImage.value = false
    }

    if (assetToken !== draftAssetToken || !open.value) {
      void deleteDraftImageUpload(key)
      throw createHandledUploadError()
    }

    draftImageObjectKey.value = key
    return key
  }

  async function sendDraft(): Promise<boolean> {
    if (!canSendCurrentDraft.value) return false
    const textSnapshot = draft.value
    const replyToMessageIdSnapshot = asPositiveInt(draftReplyMessageId.value) || null
    const clientMessageIdSnapshot = ensureDraftClientMessageId()
    sending.value = true

    try {
      const imageObjectKey = await ensureDraftImageUploaded()
      const response = await emitAck<ChatAck>('chat_send', {
        client_message_id: clientMessageIdSnapshot,
        text: textSnapshot,
        reply_to_message_id: replyToMessageIdSnapshot,
        image_object_key: imageObjectKey,
      })

      if (!response?.ok) {
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        void alertDialog(describeSendError(status, error, response.detail))
        maybeApplyAccessLoss(status, error)
        return false
      }

      if (response.message) {
        const { insertedIds } = mergeMessages([response.message])
        const messageId = insertedIds[insertedIds.length - 1]
          || asPositiveInt(isRecord(response.message) ? response.message.id : 0)
          || null
        markMutation('append', messageId, true)
      }

      clearDraft({ cleanupRemote: false })
      return true
    } catch (error: any) {
      if (!open.value) return false
      if (!isHandledUploadError(error)) {
        void alertDialog('Не удалось отправить сообщение.')
      }
      return false
    } finally {
      sending.value = false
    }
  }

  async function toggleReaction(messageId: number, emoji: string): Promise<void> {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0 || !emoji || reactionBusy[normalizedMessageId]) return

    reactionBusy[normalizedMessageId] = true
    try {
      const response = await emitAck<ChatAck>('chat_react_toggle', {
        message_id: normalizedMessageId,
        emoji,
      })
      if (!response?.ok) {
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        const message = error === 'message_deleted'
          ? 'Сообщение уже удалено.'
          : error === 'emoji_not_allowed'
            ? 'Эта реакция недоступна.'
            : describePermissionError(error, 'Не удалось поставить реакцию.')
        void alertDialog(message)
        maybeApplyAccessLoss(status, error)
        return
      }

      applyReactionsUpdate(normalizedMessageId, response.reactions)
    } catch {
      void alertDialog('Не удалось поставить реакцию.')
    } finally {
      delete reactionBusy[normalizedMessageId]
    }
  }

  async function deleteMessage(messageId: number): Promise<void> {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0 || deleteBusy[normalizedMessageId]) return

    deleteBusy[normalizedMessageId] = true
    try {
      const response = await emitAck<ChatAck>('chat_delete', {
        message_id: normalizedMessageId,
      })
      if (!response?.ok) {
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        const message = error === 'already_deleted'
          ? 'Сообщение уже удалено.'
          : error === 'message_not_found'
            ? 'Сообщение не найдено.'
            : describePermissionError(error, 'Не удалось удалить сообщение.')
        void alertDialog(message)
        maybeApplyAccessLoss(status, error)
        return
      }

      if (response.message) {
        mergeMessages([response.message])
      }
    } catch {
      void alertDialog('Не удалось удалить сообщение.')
    } finally {
      delete deleteBusy[normalizedMessageId]
    }
  }

  async function loadReactionParticipants(messageId: number, options: { force?: boolean } = {}): Promise<GlobalChatReactionParticipant[] | null> {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0) return null
    if (!options.force && Object.prototype.hasOwnProperty.call(reactionParticipantsCache, normalizedMessageId)) {
      return reactionParticipantsCache[normalizedMessageId] || []
    }

    try {
      const response = await emitAck<ChatAck>('chat_reaction_participants', {
        message_id: normalizedMessageId,
      })
      if (!response?.ok) {
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        if (error === 'message_deleted') {
          clearReactionParticipantsCache(normalizedMessageId)
        }
        maybeApplyAccessLoss(status, error)
        return null
      }

      const participants = normalizeReactionParticipants(response.participants)
      reactionParticipantsCache[normalizedMessageId] = participants
      return participants
    } catch {
      return null
    }
  }

  async function previewDeletedMessage(messageId: number): Promise<GlobalChatDeletedMessagePreview | null> {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0) return null

    try {
      const response = await emitAck<ChatAck>('chat_deleted_message_preview', {
        message_id: normalizedMessageId,
      })
      if (!response?.ok) {
        const error = asString(response.error)
        const message = error === 'message_not_found'
          ? 'Сообщение не найдено.'
          : error === 'not_deleted'
            ? 'Сообщение еще не удалено.'
            : 'Не удалось открыть удаленное сообщение.'
        void alertDialog(message)
        return null
      }

      const preview = normalizeDeletedPreview(response.preview)
      if (!preview) {
        void alertDialog('Не удалось открыть удаленное сообщение.')
        return null
      }
      return preview
    } catch {
      void alertDialog('Не удалось открыть удаленное сообщение.')
      return null
    }
  }

  async function purgeDeletedMessage(messageId: number): Promise<boolean> {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0 || purgeBusy[normalizedMessageId]) return false

    purgeBusy[normalizedMessageId] = true
    try {
      const response = await emitAck<ChatAck>('chat_message_purge', {
        message_id: normalizedMessageId,
      })
      if (!response?.ok) {
        const error = asString(response.error)
        const message = error === 'message_not_found'
          ? 'Сообщение не найдено.'
          : error === 'not_deleted'
            ? 'Сообщение еще не удалено.'
            : error === 'already_purged'
              ? 'Сообщение уже удалено окончательно.'
              : 'Не удалось удалить сообщение окончательно.'
        void alertDialog(message)
        return false
      }

      if (response.message) {
        mergeMessages([response.message])
      }
      return true
    } catch {
      void alertDialog('Не удалось удалить сообщение окончательно.')
      return false
    } finally {
      delete purgeBusy[normalizedMessageId]
    }
  }

  async function loadContext(messageId: number): Promise<boolean> {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0) return false

    try {
      const response = await emitAck<ChatAck>('chat_message_context', {
        message_id: normalizedMessageId,
      })
      if (!response?.ok) {
        const status = asPositiveInt(response.status)
        const error = asString(response.error)
        if (status === 403) {
          maybeApplyAccessLoss(status, error)
        }
        return false
      }

      mergeMessages(response.messages || [])
      markMutation('context', normalizedMessageId, false)
      return true
    } catch {
      return false
    }
  }

  async function markAlertRead(messageId: number): Promise<boolean> {
    const normalizedMessageId = asPositiveInt(messageId)
    if (normalizedMessageId <= 0) return false

    try {
      const response = await emitAck<ChatAck>('chat_mark_alert_read', {
        message_id: normalizedMessageId,
      })
      if (!response?.ok) {
        return false
      }

      applyUnreadCount(response.unread_count)
      setUnreadTargetMessageIds(response.unread_target_message_ids)
      return Boolean(response.marked ?? true)
    } catch {
      return false
    }
  }

  function setReplyTarget(messageId: number): boolean {
    const target = messages.value.find((item) => item.id === asPositiveInt(messageId))
    if (!target || target.deleted) return false
    draftReplyMessageId.value = target.id
    draftReplyPreview.value = buildDraftReplyPreview(target)
    return true
  }

  function attachDraftImage(file: File | null): boolean {
    if (!file) return false
    const type = asString(file.type).toLowerCase()
    if (!CHAT_ALLOWED_IMAGE_TYPES.has(type)) {
      void alertDialog('Можно загрузить только PNG или JPEG.')
      return false
    }
    if (file.size > CHAT_IMAGE_MAX_BYTES) {
      void alertDialog(`Файл слишком большой. Максимум ${CHAT_IMAGE_MAX_SIZE_LABEL}.`)
      return false
    }

    clearDraftImage()
    draftImageFile = file
    draftImageName.value = file.name || 'image'
    draftImagePreviewUrl.value = URL.createObjectURL(file)
    return true
  }

  function isReactionBusy(messageId: number): boolean {
    return Boolean(reactionBusy[asPositiveInt(messageId)])
  }

  function isDeleteBusy(messageId: number): boolean {
    return Boolean(deleteBusy[asPositiveInt(messageId)])
  }

  function isPurgeBusy(messageId: number): boolean {
    return Boolean(purgeBusy[asPositiveInt(messageId)])
  }

  return {
    open,
    unread,
    unreadTargetMessageIds,
    initialized,
    loadingInitial,
    loadingMore,
    sending,
    uploadingImage,
    messages,
    draft,
    hasMore,
    cursorBeforeId,
    permissions,
    reactionsAllowlist,
    connectionState,
    lastError,
    draftReplyMessageId,
    draftReplyPreview,
    draftImagePreviewUrl,
    draftImageName,
    draftImageObjectKey,
    draftHasImage,
    draftImageUploaded,
    reactionParticipantsCache,
    canSendCurrentDraft,
    lastMutationKind,
    lastMutationToken,
    lastMutationMessageId,
    lastMutationForceScroll,

    ensureUnreadSync,
    syncUnreadFromProfile,
    clearUnreadCount,
    consumeUnreadTargetMessageId,
    clearUnreadTargetMessageIds,
    openPanel,
    closePanel,
    hardReset,
    loadMore,
    sendDraft,
    toggleReaction,
    deleteMessage,
    loadReactionParticipants,
    previewDeletedMessage,
    purgeDeletedMessage,
    loadContext,
    markAlertRead,
    setReplyTarget,
    clearReplyTarget,
    attachDraftImage,
    clearDraftImage,
    clearDraft,
    isReactionBusy,
    isDeleteBusy,
    isPurgeBusy,
  }
})
