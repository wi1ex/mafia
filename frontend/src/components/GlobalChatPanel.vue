<template>
  <div v-if="canRender" :class="['global-chat-dock', { 'room-mode': isRoomMode }]">
    <Transition name="global-chat-panel-transition">
      <section v-if="chat.open" class="global-chat-panel" @click.stop>
        <header class="panel-header">
          <span class="panel-header-main">Общий чат</span>
          <button type="button" aria-label="Закрыть" @click="chat.closePanel()">
            <img :src="iconClose" alt="" />
          </button>
        </header>

        <div ref="listEl" class="panel-list" @scroll="onListScroll">
          <button v-if="showLoadMore" class="load-more" type="button" :disabled="loadingMore" @click="onLoadMore">
            {{ loadingMore ? 'Загрузка…' : 'Загрузить ещё сообщения' }}
          </button>

          <p v-if="!loadingInitial && messages.length === 0" class="empty-state">Сообщений пока нет.</p>

          <article v-for="message in messages" :key="message.id" :data-chat-message-id="message.id"
            :class="[
              'global-chat-message',
              {
                'global-chat-message--own': message.is_own,
                'global-chat-message--deleted': message.deleted,
                'global-chat-message--highlighted': highlightedMessageId === message.id,
              },
            ]"
          >
            <div class="message-main">
              <div class="message-meta">
                <div class="message-meta-author">
                  <img class="author-avatar" v-minio-img="{ key: message.author.avatar_name ? `avatars/${message.author.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар автора" />
                  <span class="author-name">{{ message.author.username || (`user${message.author.id}`) }}</span>
                </div>
                <span class="message-time">{{ formatMessageTime(message.created_at) }}</span>
              </div>

              <button v-if="message.reply" class="reply-preview" type="button" @click="onJumpToReply(message.reply.message_id)">
                <div class="reply-preview-body">
                  <img class="reply-avatar" v-minio-img="{ key: message.reply.avatar_name ? `avatars/${message.reply.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="" />
                  <span class="reply-author">{{ message.reply.author_username }}</span>
                </div>
                <span class="reply-snippet">{{ message.reply.snippet || (message.reply.has_image ? 'Изображение' : 'Сообщение') }}</span>
              </button>

              <div class="message-bubble">
                <p v-if="message.deleted" class="tombstone">Сообщение удалено</p>
                <div v-if="showDeletedModerationActions(message)" class="tombstone-actions">
                  <button class="icon-action-button" type="button" aria-label="Показать удаленное сообщение"
                          :disabled="isDeletedPreviewBusy(message.id)" @click="onPreviewDeletedMessage(message.id)">
                    <img :src="iconInfo" alt="" />
                  </button>
                  <button class="icon-action-button icon-action-button--danger" type="button" aria-label="Удалить сообщение окончательно"
                          :disabled="chat.isPurgeBusy(message.id)" @click="onPurgeDeletedMessage(message)">
                    <img :src="iconDelete" alt="" />
                  </button>
                </div>
                <template v-if="!message.deleted">
                  <img v-if="message.image_object_key" class="message-image" @click="onOpenImageLightbox($event, 'Вложение')" @load="onMessageMediaLoad" @error="onMessageMediaLoad" v-minio-img="{ key: message.image_object_key, lazy: true }" alt="Вложение" />
                  <p v-if="message.text" class="message-text">
                    <template v-for="(segment, index) in buildTextSegments(message.text)" :key="`${message.id}-text-${index}`">
                      <a v-if="segment.kind === 'link'" class="message-link" :href="segment.href" target="_blank" rel="noopener noreferrer nofollow" @click.stop>{{ segment.text }}</a>
                      <span v-else>{{ segment.text }}</span>
                    </template>
                  </p>
                </template>
              </div>

              <div v-if="!message.deleted && (message.reactions.length > 0 || reactionsAllowlist.length > 0)" class="reactions-row">
                <div v-for="reaction in orderedReactions(message)" :key="reaction.emoji" class="reaction-details-anchor"
                     @pointerenter="onReactionDetailsHover(message.id, reaction.emoji)" @pointerleave="closeReactionDetails(message.id, reaction.emoji)"
                     @focusin="onReactionDetailsFocus(message.id, reaction.emoji)" @focusout="onReactionDetailsFocusOut($event, message.id, reaction.emoji)">
                  <button :class="['reaction-chip', { 'reaction-chip--active': reaction.reacted_by_me }]"
                          type="button" :disabled="chat.isReactionBusy(message.id)" @click="onToggleReaction(message.id, reaction.emoji)">
                    <span>{{ reaction.emoji }}</span>
                    <span>{{ reaction.count }}</span>
                  </button>

                  <div v-if="reactionDetailsMessageId === message.id && reactionDetailsEmoji === reaction.emoji" class="reaction-details-popover" role="tooltip">
                    <p v-if="reactionDetailsLoadingMessageId === message.id" class="reaction-details-state">Загрузка...</p>
                    <p v-else-if="reactionDetailsErrorMessageId === message.id" class="reaction-details-state reaction-details-state--error">
                      Не удалось загрузить список реакций.
                    </p>
                    <template v-else-if="reactionParticipantsFor(message.id, reaction.emoji).length > 0">
                      <div v-for="participant in reactionParticipantsFor(message.id, reaction.emoji)" :key="`${participant.user.id}-${participant.created_at}`" class="reaction-details-item">
                        <img class="reaction-details-avatar" v-minio-img="{ key: participant.user.avatar_name ? `avatars/${participant.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар" />
                        <div class="reaction-details-meta">
                          <span class="reaction-details-name">{{ participant.user.username || (`user${participant.user.id}`) }}</span>
                          <small class="reaction-details-time">{{ formatMessageTime(participant.created_at) }}</small>
                        </div>
                      </div>
                    </template>
                    <p v-else class="reaction-details-state">Реакций пока нет.</p>
                  </div>
                </div>

                <div v-if="reactionsAllowlist.length > 0" class="reaction-details-anchor">
                  <button class="reaction-chip reaction-chip--picker" type="button" :disabled="chat.isReactionBusy(message.id)"
                          @pointerdown.stop @click="toggleMessageReactionPicker(message.id)">
                    <img :src="iconAddReaction" alt="" />
                  </button>
                  <button v-if="!message.deleted" class="reaction-chip reaction-chip--picker" type="button" @click="onReply(message.id)">
                    <img :src="iconReplyMessage" alt="" />
                  </button>
                  <button v-if="message.can_delete" class="reaction-chip reaction-chip--picker red" type="button"
                          :disabled="chat.isDeleteBusy(message.id)" @click="onDeleteMessage(message)">
                    <img :src="iconDelete" alt="" />
                  </button>
                  <Transition name="emoji-picker-pop">
                    <component :is="EmojiPicker" v-if="reactionPickerMessageId === message.id" mode="reactions" :reactions="reactionsAllowlist"
                               @select="onSelectReaction(message.id, $event)" @close="reactionPickerMessageId = null" />
                  </Transition>
                </div>
              </div>
            </div>
          </article>
        </div>

        <div v-if="statusText" class="panel-status" :class="{ 'panel-status--error': connectionState === 'error' }">
          <span>{{ statusText }}</span>
          <button v-if="connectionState === 'error'" type="button" @click="chat.openPanel()">Повторить</button>
        </div>

        <div v-if="draftReplyPreview" class="reply-bar">
          <div class="reply-bar-text">
            <span class="reply-bar-label">Ответ на сообщение {{ draftReplyPreview.author_username }}</span>
            <span class="reply-bar-snippet">{{ draftReplyPreview.snippet || (draftReplyPreview.has_image ? 'Изображение' : 'Сообщение') }}</span>
          </div>
          <button type="button" aria-label="Сбросить ответ" @click="chat.clearReplyTarget()">
            <img :src="iconClose" alt="" />
          </button>
        </div>

        <div v-if="draftImagePreviewUrl" class="image-preview">
          <div class="image-preview-div">
            <img :src="draftImagePreviewUrl" alt="Предпросмотр изображения" />
            <div class="image-preview-meta">
              <span>{{ draftImageName || 'Изображение' }}</span>
              <small>{{ draftImageUploaded ? 'Загружено' : (uploadingImage ? 'Загрузка…' : 'Изображение прикреплено') }}</small>
            </div>
          </div>
          <button type="button" @click="chat.clearDraftImage()">
            <img :src="iconClose" alt="" />
          </button>
        </div>

        <div class="composer-shell">
          <label class="tool-button tool-button--file" :class="{ 'tool-button--disabled': composerDisabled }">
            <input ref="fileInputEl" type="file" accept="image/png,image/jpeg" :disabled="composerDisabled" @change="onPickImage" >
            <img :src="iconPhoto" alt="" />
          </label>

          <textarea ref="textareaEl" v-model="draft" class="composer-input" :disabled="composerDisabled" rows="3"
                    maxlength="1000" placeholder="Введите текст..." @keydown="onComposerKeydown" />

          <button class="tool-button right" type="button" :disabled="composerDisabled" @pointerdown.stop @click="composerPickerOpen = !composerPickerOpen">
            <img :src="iconEmoji" alt="" />
          </button>
          <Transition name="emoji-picker-pop">
            <component :is="EmojiPicker" v-if="composerPickerOpen" mode="composer" @select="insertEmoji" @close="composerPickerOpen = false" />
          </Transition>

          <button class="send-button" type="button" :disabled="!canSendCurrentDraft" @click="onSend" >
            <img :src="iconSend" alt="" />
          </button>
        </div>
      </section>
    </Transition>

    <Transition name="deleted-preview-modal">
      <div v-if="deletedPreviewOpen && deletedPreview" class="deleted-preview-overlay" role="dialog" aria-modal="true" aria-label="Удаленное сообщение"
           @pointerdown.self="deletedPreviewArmed = true" @pointerup.self="deletedPreviewArmed && closeDeletedPreview()" @pointerleave.self="deletedPreviewArmed = false" @pointercancel.self="deletedPreviewArmed = false" >
        <div class="deleted-preview-modal">
          <header class="deleted-preview-header">
            <div class="deleted-preview-header-main">
              <span>Удаленное сообщение</span>
              <small v-if="deletedPreview.deleted_at">{{ formatMessageTime(deletedPreview.deleted_at) }}</small>
            </div>
            <button type="button" aria-label="Закрыть" @click="closeDeletedPreview()">
              <img :src="iconClose" alt="" />
            </button>
          </header>

          <div class="deleted-preview-body">
            <div class="deleted-preview-author">
              <img class="deleted-preview-avatar" v-minio-img="{ key: deletedPreview.author.avatar_name ? `avatars/${deletedPreview.author.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар автора" />
              <span>{{ deletedPreview.author.username || (`user${deletedPreview.author.id}`) }}</span>
            </div>

            <template v-if="deletedPreview.content_available">
              <p v-if="deletedPreview.text" class="deleted-preview-text">
                <template v-for="(segment, index) in buildTextSegments(deletedPreview.text)" :key="`deleted-preview-text-${index}`">
                  <a v-if="segment.kind === 'link'" class="message-link" :href="segment.href" target="_blank" rel="noopener noreferrer nofollow" @click.stop>{{ segment.text }}</a>
                  <span v-else>{{ segment.text }}</span>
                </template>
              </p>
              <img v-if="deletedPreview.image_object_key" class="deleted-preview-image" @click="onOpenImageLightbox($event, 'Удаленное вложение')" v-minio-img="{ key: deletedPreview.image_object_key, lazy: false }" alt="Удаленное вложение" />
            </template>
            <p v-else class="deleted-preview-empty">Содержимое сообщения уже удалено окончательно.</p>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="image-lightbox-transition">
      <div v-if="imageLightboxOpen && imageLightboxSrc" class="image-lightbox-overlay" role="dialog" aria-modal="true" :aria-label="imageLightboxAlt || 'Просмотр изображения'"
           @pointerdown.self="imageLightboxArmed = true" @pointerup.self="imageLightboxArmed && closeImageLightbox()" @pointerleave.self="imageLightboxArmed = false" @pointercancel.self="imageLightboxArmed = false">
        <button class="image-lightbox-close" type="button" aria-label="Закрыть" @click="closeImageLightbox()">
          <img :src="iconClose" alt="" />
        </button>
        <img class="image-lightbox-image" :src="imageLightboxSrc" :alt="imageLightboxAlt || 'Просмотр изображения'" />
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatChatTimestamp } from '@/services/datetime'
import { useAuthStore, useGlobalChatStore, useSettingsStore, useUserStore } from '@/store'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'
import iconEmoji from '@/assets/svg/emoji.svg'
import iconPhoto from '@/assets/svg/photo.svg'
import iconDelete from '@/assets/svg/delete.svg'
import iconInfo from '@/assets/svg/info.svg'
import iconSend from '@/assets/svg/send.svg'
import iconAddReaction from '@/assets/svg/add_reaction.svg'
import iconReplyMessage from '@/assets/svg/reply_message.svg'

import type {
  GlobalChatDeletedMessagePreview,
  GlobalChatMessage,
  GlobalChatReaction,
  GlobalChatReactionParticipant,
} from '@/store/modules/globalChat'

const EmojiPicker = defineAsyncComponent(() => import('@/components/GlobalChatEmojiPicker.vue'))
const auth = useAuthStore()
const user = useUserStore()
const settings = useSettingsStore()
const chat = useGlobalChatStore()
const route = useRoute()
const {
  messages,
  draft,
  hasMore,
  loadingInitial,
  loadingMore,
  sending,
  uploadingImage,
  reactionsAllowlist,
  connectionState,
  lastError,
  permissions,
  draftReplyPreview,
  draftImagePreviewUrl,
  draftImageName,
  draftImageUploaded,
  reactionParticipantsCache,
  canSendCurrentDraft,
  lastMutationToken,
  lastMutationKind,
  lastMutationMessageId,
  lastMutationForceScroll,
} = storeToRefs(chat)

const listEl = ref<HTMLElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const composerPickerOpen = ref(false)
const reactionPickerMessageId = ref<number | null>(null)
const highlightedMessageId = ref<number | null>(null)
const stickToBottom = ref(true)
const listAtTop = ref(false)
const deletedPreviewOpen = ref(false)
const deletedPreviewArmed = ref(false)
const deletedPreview = ref<GlobalChatDeletedMessagePreview | null>(null)
const deletedPreviewLoadingMessageId = ref<number | null>(null)
const imageLightboxOpen = ref(false)
const imageLightboxArmed = ref(false)
const imageLightboxSrc = ref('')
const imageLightboxAlt = ref('')
const reactionDetailsMessageId = ref<number | null>(null)
const reactionDetailsEmoji = ref('')
const reactionDetailsLoadingMessageId = ref<number | null>(null)
const reactionDetailsErrorMessageId = ref<number | null>(null)
let reactionDetailsRequestToken = 0
let highlightTimer: number | null = null
let scrollToBottomRaf: number | null = null
let scrollToBottomFramesRemaining = 0
const isAdmin = computed(() => String(user.user?.role || '').trim().toLowerCase() === 'admin')
const isRoomMode = computed(() => route.name === 'room')

const showLauncher = computed(() => {
  if (!auth.ready || !settings.ready || !auth.isAuthed) return false
  if (!settings.chatOpenEnabled) return false
  if (!user.user) return false
  if (user.banActive || user.timeoutActive || user.inActiveGameAsAlivePlayer) return false
  return !(settings.verificationRestrictions && !user.telegramVerified);
})
const canRender = computed(() => settings.chatOpenEnabled && (showLauncher.value || chat.open))

const statusText = computed(() => {
  if (loadingInitial.value) return 'Загрузка истории…'
  if (connectionState.value === 'connecting') return 'Подключение к общему чату…'
  if (connectionState.value === 'reconnecting') return 'Соединение потеряно. Переподключаемся…'
  if (connectionState.value === 'error') return lastError.value || 'Не удалось подключиться к общему чату'
  if (!permissions.value.can_send) return 'Отправка сообщений временно недоступна'
  return ''
})

const composerDisabled = computed(() => {
  return connectionState.value !== 'ready'
    || !permissions.value.can_send
    || sending.value
    || uploadingImage.value
})
const composerPlaceholder = computed(() => (
  permissions.value.can_send ? 'Введите текст...' : 'Чат временно отключен...'
))
const showLoadMore = computed(() => hasMore.value && (loadingMore.value || listAtTop.value))

type TextSegment = {
  kind: 'text' | 'link'
  text: string
  href?: string
}

const URL_RE = /((?:https?:\/\/|www\.)[^\s<]+)/gi
const TRAILING_URL_PUNCTUATION_RE = /[),.!?:;]+$/

function isNearTop(): boolean {
  const list = listEl.value
  if (!list) return true
  return list.scrollTop <= 40
}

function isNearBottom(): boolean {
  const list = listEl.value
  if (!list) return true
  return list.scrollHeight - list.scrollTop - list.clientHeight <= 72
}

function updateScrollState(): void {
  listAtTop.value = isNearTop()
  stickToBottom.value = isNearBottom()
}

function focusComposer(): void {
  textareaEl.value?.focus()
}

function syncComposerPlaceholder(): void {
  if (!textareaEl.value) return
  textareaEl.value.placeholder = composerPlaceholder.value
}

function formatMessageTime(value: string): string {
  return formatChatTimestamp(value)
}

function splitTrailingUrlPunctuation(rawUrl: string): { cleanUrl: string; trailing: string } {
  let cleanUrl = rawUrl
  let trailing = ''

  while (cleanUrl) {
    const match = cleanUrl.match(TRAILING_URL_PUNCTUATION_RE)
    if (!match) break
    const candidate = match[0] || ''
    if (!candidate) break

    if (candidate.startsWith(')')) {
      const opens = (cleanUrl.match(/\(/g) || []).length
      const closes = (cleanUrl.match(/\)/g) || []).length
      if (closes <= opens) break
    }

    cleanUrl = cleanUrl.slice(0, cleanUrl.length - candidate.length)
    trailing = candidate + trailing
  }

  return { cleanUrl, trailing }
}

function normalizeUrlHref(rawUrl: string): string | null {
  const value = String(rawUrl || '').trim()
  if (!value) return null
  if (/^https?:\/\//i.test(value)) return value
  if (/^www\./i.test(value)) return `https://${value}`
  return null
}

function buildTextSegments(value: string): TextSegment[] {
  const text = String(value || '')
  if (!text) return []

  const segments: TextSegment[] = []
  let lastIndex = 0

  for (const match of text.matchAll(URL_RE)) {
    const rawUrl = String(match[0] || '')
    const offset = Number(match.index ?? -1)
    if (!rawUrl || offset < 0) continue
    if (offset > lastIndex) {
      segments.push({ kind: 'text', text: text.slice(lastIndex, offset) })
    }
    const { cleanUrl, trailing } = splitTrailingUrlPunctuation(rawUrl)
    const href = normalizeUrlHref(cleanUrl)
    if (cleanUrl && href) {
      segments.push({ kind: 'link', text: cleanUrl, href })
    } else {
      segments.push({ kind: 'text', text: rawUrl })
    }
    if (trailing) {
      segments.push({ kind: 'text', text: trailing })
    }
    lastIndex = offset + rawUrl.length
  }
  if (lastIndex < text.length) {
    segments.push({ kind: 'text', text: text.slice(lastIndex) })
  }
  return segments.length ? segments : [{ kind: 'text', text }]
}

function orderedReactions(message: GlobalChatMessage): GlobalChatReaction[] {
  const order = new Map(reactionsAllowlist.value.map((emoji, index) => [emoji, index]))
  return [...message.reactions].sort((left, right) => {
    const leftOrder = order.has(left.emoji) ? Number(order.get(left.emoji)) : Number.MAX_SAFE_INTEGER
    const rightOrder = order.has(right.emoji) ? Number(order.get(right.emoji)) : Number.MAX_SAFE_INTEGER
    if (leftOrder !== rightOrder) return leftOrder - rightOrder
    return left.emoji.localeCompare(right.emoji)
  })
}

function reactionParticipantsFor(messageId: number, emoji?: string): GlobalChatReactionParticipant[] {
  const participants = reactionParticipantsCache.value[messageId] || []
  const normalizedEmoji = String(emoji || '').trim()
  if (!normalizedEmoji) return participants
  return participants.filter((participant) => participant.emoji === normalizedEmoji)
}

function closeImageLightbox(): void {
  imageLightboxArmed.value = false
  imageLightboxOpen.value = false
  imageLightboxSrc.value = ''
  imageLightboxAlt.value = ''
}

function onOpenImageLightbox(event: Event, alt: string): void {
  const image = event.currentTarget as HTMLImageElement | null
  const src = image?.currentSrc || image?.src || ''
  if (!src) return
  imageLightboxSrc.value = src
  imageLightboxAlt.value = alt
  imageLightboxArmed.value = false
  imageLightboxOpen.value = true
}

function closeReactionDetails(messageId?: number, emoji?: string): void {
  const normalizedMessageId = typeof messageId === 'number' ? messageId : null
  const normalizedEmoji = String(emoji || '').trim()
  if (normalizedMessageId !== null && reactionDetailsMessageId.value !== normalizedMessageId) return
  if (normalizedEmoji && reactionDetailsEmoji.value !== normalizedEmoji) return
  reactionDetailsMessageId.value = null
  reactionDetailsEmoji.value = ''
  reactionDetailsLoadingMessageId.value = null
  reactionDetailsErrorMessageId.value = null
}

async function openReactionDetails(messageId: number, emoji: string, options: { force?: boolean } = {}): Promise<void> {
  const normalizedEmoji = String(emoji || '').trim()
  if (!normalizedEmoji) return
  reactionDetailsMessageId.value = messageId
  reactionDetailsEmoji.value = normalizedEmoji
  reactionDetailsErrorMessageId.value = null
  const hasCached = Object.prototype.hasOwnProperty.call(reactionParticipantsCache.value, messageId)
  if (hasCached && !options.force) return

  const token = ++reactionDetailsRequestToken
  reactionDetailsLoadingMessageId.value = messageId
  const participants = await chat.loadReactionParticipants(messageId, options)
  if (token !== reactionDetailsRequestToken) return
  if (reactionDetailsLoadingMessageId.value === messageId) {
    reactionDetailsLoadingMessageId.value = null
  }
  if (reactionDetailsMessageId.value !== messageId || reactionDetailsEmoji.value !== normalizedEmoji) return
  if (participants === null) {
    reactionDetailsErrorMessageId.value = messageId
  }
}

function onReactionDetailsHover(messageId: number, emoji: string): void {
  void openReactionDetails(messageId, emoji)
}

function onReactionDetailsFocus(messageId: number, emoji: string): void {
  void openReactionDetails(messageId, emoji)
}

function onReactionDetailsFocusOut(event: FocusEvent, messageId: number, emoji: string): void {
  const current = event.currentTarget as HTMLElement | null
  const nextTarget = event.relatedTarget as Node | null
  if (current && nextTarget && current.contains(nextTarget)) return
  closeReactionDetails(messageId, emoji)
}

function onWindowKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return
  if (imageLightboxOpen.value) {
    closeImageLightbox()
    return
  }
  if (deletedPreviewOpen.value) {
    closeDeletedPreview()
    return
  }
  if (reactionDetailsMessageId.value !== null) {
    closeReactionDetails()
  }
}

function scrollToBottom(): void {
  const list = listEl.value
  if (!list) return
  list.scrollTop = list.scrollHeight
}

function cancelScheduledScrollToBottom(): void {
  if (scrollToBottomRaf !== null) {
    window.cancelAnimationFrame(scrollToBottomRaf)
    scrollToBottomRaf = null
  }
  scrollToBottomFramesRemaining = 0
}

function scheduleScrollToBottom(force = false, frames = 8): void {
  if (!force && !stickToBottom.value) return
  scrollToBottomFramesRemaining = Math.max(scrollToBottomFramesRemaining, frames)
  if (scrollToBottomRaf !== null) return

  const run = () => {
    scrollToBottomRaf = null
    if (!listEl.value) {
      scrollToBottomFramesRemaining = 0
      return
    }
    scrollToBottom()
    updateScrollState()
    scrollToBottomFramesRemaining -= 1
    if (scrollToBottomFramesRemaining > 0) {
      scrollToBottomRaf = window.requestAnimationFrame(run)
    }
  }

  scrollToBottomRaf = window.requestAnimationFrame(run)
}

function onMessageMediaLoad(): void {
  scheduleScrollToBottom()
}

function clearHighlightTimer(): void {
  if (highlightTimer !== null) {
    window.clearTimeout(highlightTimer)
    highlightTimer = null
  }
}

function highlightMessage(messageId: number): void {
  highlightedMessageId.value = messageId
  clearHighlightTimer()
  highlightTimer = window.setTimeout(() => {
    highlightedMessageId.value = null
    highlightTimer = null
  }, 1800)
}

function findMessageElement(messageId: number): HTMLElement | null {
  return listEl.value?.querySelector(`[data-chat-message-id="${messageId}"]`) as HTMLElement | null
}

function scrollToMessage(messageId: number, withHighlight = false): boolean {
  const element = findMessageElement(messageId)
  if (!element) return false
  element.scrollIntoView({ block: 'center', behavior: 'smooth' })
  if (withHighlight) highlightMessage(messageId)
  return true
}

function onListScroll(): void {
  updateScrollState()
}

async function onLoadMore(): Promise<void> {
  const list = listEl.value
  const previousHeight = list?.scrollHeight || 0
  const previousTop = list?.scrollTop || 0
  const changed = await chat.loadMore()
  if (!changed || !list) return
  await nextTick()
  list.scrollTop = previousTop + (list.scrollHeight - previousHeight)
  updateScrollState()
}

function onReply(messageId: number): void {
  const ok = chat.setReplyTarget(messageId)
  if (!ok) {
    void alertDialog('Не удалось подготовить ответ на это сообщение.')
    return
  }
  reactionPickerMessageId.value = null
  composerPickerOpen.value = false
  void nextTick(() => focusComposer())
}

function onToggleReaction(messageId: number, emoji: string): void {
  void chat.toggleReaction(messageId, emoji)
}

function toggleMessageReactionPicker(messageId: number): void {
  reactionPickerMessageId.value = reactionPickerMessageId.value === messageId ? null : messageId
}

function onSelectReaction(messageId: number, emoji: string): void {
  reactionPickerMessageId.value = null
  onToggleReaction(messageId, emoji)
}

async function onDeleteMessage(message: GlobalChatMessage): Promise<void> {
  if (message.deleted || !message.can_delete || chat.isDeleteBusy(message.id)) return

  const authorName = message.author.username || `user${message.author.id}`
  const confirmed = await confirmDialog({
    title: message.is_own ? 'Удаление сообщения' : 'Удаление сообщения пользователя',
    text: message.is_own
      ? 'Вы уверены, что хотите удалить это сообщение?'
      : isAdmin.value
        ? `Вы уверены, что хотите удалить сообщение пользователя ${authorName}?`
        : 'Вы уверены, что хотите удалить это сообщение?',
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!confirmed) return

  await chat.deleteMessage(message.id)
}

function showDeletedModerationActions(message: GlobalChatMessage): boolean {
  return isAdmin.value && message.deleted && message.deleted_content_available
}

function isDeletedPreviewBusy(messageId: number): boolean {
  return deletedPreviewLoadingMessageId.value === messageId
}

function closeDeletedPreview(): void {
  deletedPreviewArmed.value = false
  deletedPreviewOpen.value = false
  deletedPreview.value = null
}

async function onPreviewDeletedMessage(messageId: number): Promise<void> {
  if (deletedPreviewLoadingMessageId.value === messageId) return
  deletedPreviewLoadingMessageId.value = messageId
  try {
    const preview = await chat.previewDeletedMessage(messageId)
    if (!preview) return
    deletedPreview.value = preview
    deletedPreviewArmed.value = false
    deletedPreviewOpen.value = true
  } finally {
    if (deletedPreviewLoadingMessageId.value === messageId) {
      deletedPreviewLoadingMessageId.value = null
    }
  }
}

async function onPurgeDeletedMessage(message: GlobalChatMessage): Promise<void> {
  if (!showDeletedModerationActions(message) || chat.isPurgeBusy(message.id)) return
  const confirmed = await confirmDialog({
    title: 'Окончательное удаление',
    text: 'Вы уверены что хотите удалить сообщение навсегда?',
    confirmText: 'Удалить',
    cancelText: 'Отмена',
  })
  if (!confirmed) return

  const purged = await chat.purgeDeletedMessage(message.id)
  if (!purged) return

  if (deletedPreview.value?.message_id === message.id) {
    deletedPreview.value = {
      ...deletedPreview.value,
      content_available: false,
      text: '',
      image_object_key: null,
    }
  }
}

async function onJumpToReply(messageId: number): Promise<void> {
  if (scrollToMessage(messageId, true)) {
    updateScrollState()
    return
  }
  const ok = await chat.loadContext(messageId)
  if (!ok) {
    void alertDialog('Не удалось найти исходное сообщение.')
    return
  }
  await nextTick()
  if (!scrollToMessage(messageId, true)) {
    void alertDialog('Не удалось найти исходное сообщение.')
    return
  }
  updateScrollState()
}

function insertEmoji(emoji: string): void {
  const textarea = textareaEl.value
  const current = draft.value || ''
  if (!textarea) {
    draft.value = `${current}${emoji}`
    return
  }

  const start = textarea.selectionStart ?? current.length
  const end = textarea.selectionEnd ?? current.length
  draft.value = `${current.slice(0, start)}${emoji}${current.slice(end)}`
  void nextTick(() => {
    focusComposer()
    const nextPos = start + emoji.length
    textarea.setSelectionRange(nextPos, nextPos)
  })
}

function onComposerKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  if (!canSendCurrentDraft.value) return
  void onSend()
}

async function onSend(): Promise<void> {
  const sent = await chat.sendDraft()
  if (!sent) return
  stickToBottom.value = true
  reactionPickerMessageId.value = null
  composerPickerOpen.value = false
  await nextTick()
  scheduleScrollToBottom(true)
  focusComposer()
}

function onPickImage(event: Event): void {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0] || null
  if (!file) return
  chat.attachDraftImage(file)
  if (input) input.value = ''
  composerPickerOpen.value = false
  void nextTick(() => focusComposer())
}

watch(lastMutationToken, async () => {
  await nextTick()
  if (lastMutationKind.value === 'reset') {
    stickToBottom.value = true
    scheduleScrollToBottom(true)
    focusComposer()
    return
  }

  if (lastMutationKind.value === 'append') {
    if (lastMutationForceScroll.value) {
      stickToBottom.value = true
    }
    scheduleScrollToBottom(lastMutationForceScroll.value)
    return
  }

  if (lastMutationKind.value === 'context' && lastMutationMessageId.value) {
    scrollToMessage(lastMutationMessageId.value, true)
    updateScrollState()
  }
})

watch(showLauncher, (allowed) => {
  if (!allowed && chat.open) {
    chat.closePanel()
  }
}, { immediate: true })

watch(() => auth.isAuthed, (isAuthed) => {
  if (!isAuthed) {
    chat.hardReset()
  }
})

watch(messages, (items) => {
  if (!reactionPickerMessageId.value) return
  const active = items.find((item) => item.id === reactionPickerMessageId.value)
  if (!active || active.deleted) {
    reactionPickerMessageId.value = null
  }
})

watch(messages, (items) => {
  if (reactionDetailsMessageId.value === null) return
  const active = items.find((item) => item.id === reactionDetailsMessageId.value)
  if (!active || active.deleted || !orderedReactions(active).some((reaction) => reaction.emoji === reactionDetailsEmoji.value)) {
    closeReactionDetails()
  }
})

watch(messages, (items) => {
  if (!deletedPreview.value) return
  const active = items.find((item) => item.id === deletedPreview.value?.message_id)
  if (!active) {
    closeDeletedPreview()
    return
  }
  if (!active.deleted_content_available && deletedPreview.value.content_available) {
    deletedPreview.value = {
      ...deletedPreview.value,
      content_available: false,
      text: '',
      image_object_key: null,
    }
  }
})

watch(composerPlaceholder, () => {
  syncComposerPlaceholder()
})

watch(() => chat.open, (open) => {
  if (!open) {
    cancelScheduledScrollToBottom()
    composerPickerOpen.value = false
    reactionPickerMessageId.value = null
    closeReactionDetails()
    closeDeletedPreview()
    closeImageLightbox()
    return
  }
  void nextTick(() => {
    syncComposerPlaceholder()
    scheduleScrollToBottom(true)
  })
})

onMounted(() => {
  window.addEventListener('keydown', onWindowKeydown)
  stickToBottom.value = true
  void nextTick(() => {
    syncComposerPlaceholder()
    scheduleScrollToBottom(true)
    focusComposer()
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onWindowKeydown)
  cancelScheduledScrollToBottom()
  clearHighlightTimer()
  closeReactionDetails()
  closeDeletedPreview()
  closeImageLightbox()
})
</script>

<style scoped lang="scss">
.global-chat-dock {
  position: fixed;
  bottom: 10px;
  right: 10px;
  pointer-events: none;
  z-index: 70;
  &.room-mode {
    bottom: 60px;
    z-index: 25;
  }
  > * {
    pointer-events: auto;
  }
}
.global-chat-panel {
  display: flex;
  flex-direction: column;
  width: 400px;
  height: min(600px, calc(100dvh - 85px));
  border-radius: 10px;
  border: 3px solid $lead;
  background-color: $dark;
  box-shadow: 0 15px 30px rgba($black, 0.25);
  overflow: hidden;
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 10px;
    min-height: 25px;
    background-color: $lead;
    .panel-header-main {
      color: $white;
      font-size: 20px;
      font-family: Manrope-SemiBold;
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 25px;
      height: 25px;
      border: none;
      background: none;
      cursor: pointer;
      img {
        width: 25px;
        height: 25px;
      }
    }
  }
  .panel-list {
    display: flex;
    flex-direction: column;
    padding: 10px;
    gap: 10px;
    height: calc(100% - 107px);
    overflow-y: auto;
    scrollbar-width: none;
    .load-more {
      min-height: 30px;
      border: 1px solid $grey;
      border-radius: 5px;
      background-color: $dark;
      color: $fg;
      cursor: pointer;
      &:disabled {
        opacity: 0.5;
        cursor: default;
      }
    }
    .empty-state {
      margin: auto 0;
      color: $grey;
      text-align: center;
    }
    .global-chat-message {
      display: flex;
      padding: 5px 10px;
      width: calc(100% - 20px);
      border-radius: 10px;
      background-color: $graphite;
      border: 1px solid transparent;
      transition: border-color 0.25s ease-in-out;
      &--own {
        background-color: $graphite;
      }
      &--deleted {
        opacity: 0.5;
      }
      &--highlighted {
        border-color: $orange;
      }
      .message-main {
        display: flex;
        flex-direction: column;
        gap: 5px;
        width: 100%;
        .message-meta {
          display: flex;
          align-items: center;
          justify-content: space-between;
          .message-meta-author {
            display: flex;
            align-items: center;
            gap: 5px;
            .author-avatar {
              width: 20px;
              height: 20px;
              border-radius: 50%;
              object-fit: cover;
            }
            .author-name {
              min-width: 0;
              height: 18px;
              font-size: 16px;
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
            }
          }
          .message-time {
            color: $ashy;
            font-size: 12px;
          }
        }
        .reply-preview {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 5px;
          padding: 5px;
          border: none;
          border-left: 5px solid rgba($orange, 0.5);
          border-radius: 5px;
          background-color: $lead;
          text-align: left;
          color: $fg;
          cursor: pointer;
          .reply-preview-body {
            display: flex;
            gap: 5px;
            .reply-avatar {
              width: 20px;
              height: 20px;
              border-radius: 50%;
              object-fit: cover;
            }
            .reply-author {
              color: $fg;
              font-size: 14px;
              font-family: Manrope-Medium;
            }
          }
          .reply-snippet {
            width: 100%;
            color: $ashy;
            font-size: 12px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }
        .message-bubble {
          display: flex;
          flex-direction: column;
          gap: 5px;
          .message-text,
          .tombstone {
            margin: 0;
            padding: 5px 8px;
            border-radius: 5px;
            background-color: $dark;
            color: $fg;
            font-size: 16px;
            line-height: 1.2;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
          }
          .message-link {
            color: $white;
            font-family: Manrope-SemiBold;
            text-decoration: underline;
            text-decoration-thickness: 1px;
            text-underline-offset: 2px;
            word-break: break-word;
          }
          .tombstone {
            color: $ashy;
            font-style: italic;
          }
          .tombstone-actions {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 5px;
            .icon-action-button {
              display: flex;
              align-items: center;
              justify-content: center;
              max-height: 25px;
              padding: 5px 8px;
              border: none;
              border-radius: 999px;
              background-color: $dark;
              cursor: pointer;
              img {
                width: 16px;
                height: 16px;
              }
              &:disabled {
                opacity: 0.5;
                cursor: default;
              }
              &--danger {
                background-color: $red;
              }
            }
          }
          .message-image {
            width: 100%;
            max-height: 340px;
            border-radius: 5px;
            object-fit: cover;
            cursor: zoom-in;
          }
        }
        .reactions-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: flex-end;
          gap: 5px;
          .reaction-details-anchor {
            display: flex;
            position: relative;
            align-items: center;
            gap: 3px;
            .reaction-chip {
              display: flex;
              align-items: center;
              gap: 3px;
              padding: 3px 7px 3px 5px;
              border: 1px solid $grey;
              border-radius: 999px;
              background-color: $lead;
              color: $fg;
              font-size: 14px;
              font-weight: bold;
              line-height: 1.3;
              cursor: pointer;
              &:disabled {
                opacity: 0.5;
                cursor: default;
              }
              &--active {
                border-color: rgba($green, 0.25);
                background-color: rgba($green, 0.1);
              }
              &--picker {
                padding: 5px 8px;
                border: none;
                background-color: $dark;
                &.red {
                  background-color: rgba($red, 0.75);
                }
                img {
                  width: 16px;
                  height: 16px;
                }
              }
            }
            .reaction-details-popover {
              display: flex;
              position: absolute;
              flex-direction: column;
              top: calc(100% + 5px);
              right: 0;
              padding: 5px 8px;
              gap: 10px;
              width: max-content;
              height: max-content;
              border-radius: 5px;
              background-color: $lead;
              box-shadow: 0 15px 30px rgba($black, 0.25);
              z-index: 5;
              .reaction-details-item {
                display: flex;
                align-items: center;
                gap: 3px;
                .reaction-details-avatar {
                  width: 25px;
                  height: 25px;
                  border-radius: 50%;
                  object-fit: cover;
                }
                .reaction-details-meta {
                  display: flex;
                  flex-direction: column;
                  gap: 3px;
                  min-width: 0;
                  .reaction-details-name {
                    color: $fg;
                    font-size: 12px;
                    font-family: Manrope-Medium;
                  }
                  .reaction-details-time {
                    color: $grey;
                    font-size: 10px;
                  }
                }
              }
              .reaction-details-state {
                margin: 0;
                color: $ashy;
                font-size: 12px;
                line-height: 1.2;
                &--error {
                  color: $red;
                }
              }
            }
          }
        }
      }
    }
  }
  .panel-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 10px 0;
    gap: 10px;
    min-height: 30px;
    background-color: $graphite;
    color: $fg;
    font-size: 14px;
    font-weight: bold;
    &--error {
      color: $red;
    }
    button {
      padding: 0 10px;
      height: 30px;
      border: none;
      border-radius: 5px;
      background-color: $lead;
      color: $fg;
      cursor: pointer;
    }
  }
  .reply-bar {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 10px;
    gap: 10px;
    background-color: $lead;
    .reply-bar-text {
      display: flex;
      flex-direction: column;
      gap: 5px;
      min-width: 0;
      .reply-bar-label {
        color: $ashy;
        font-size: 12px;
        font-family: Manrope-Medium;
      }
      .reply-bar-snippet {
        color: $fg;
        font-size: 14px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      min-width: 20px;
      min-height: 20px;
      border: none;
      border-radius: 999px;
      background-color: $dark;
      cursor: pointer;
      img {
        width: 12px;
        height: 12px;
      }
    }
  }
  .image-preview {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 10px;
    background-color: $lead;
    .image-preview-div {
      display: flex;
      align-items: flex-start;
      gap: 5px;
      img {
        width: 40px;
        height: 40px;
        border-radius: 5px;
        object-fit: cover;
      }
      .image-preview-meta {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: space-between;
        height: 40px;
        span {
          color: $fg;
          font-size: 12px;
          line-height: 1.2;
          text-overflow: ellipsis;
          white-space: nowrap;
          overflow: hidden;
        }
        small {
          color: $ashy;
          font-size: 12px;
        }
      }
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      min-width: 20px;
      min-height: 20px;
      border: none;
      border-radius: 999px;
      background-color: $dark;
      cursor: pointer;
      img {
        width: 12px;
        height: 12px;
      }
    }
  }
  .composer-shell {
    display: flex;
    position: relative;
    gap: 10px;
    min-height: 52px;
    .tool-button {
      display: flex;
      position: absolute;
      left: 5px;
      bottom: 10px;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      border: none;
      border-radius: 999px;
      background-color: $dark;
      cursor: pointer;
      &--file {
        input {
          position: absolute;
          inset: 0;
          opacity: 0;
          cursor: pointer;
        }
      }
      &--disabled {
        cursor: default;
        img {
          opacity: 0.5;
        }
      }
      &.right {
        left: auto;
        right: 40px;
      }
      img {
        width: 16px;
        height: 16px;
      }
    }
    .composer-input {
      padding: 17px 80px 15px 45px;
      width: 100%;
      height: 20px;
      border: none;
      background-color: $lead;
      color: $fg;
      font-size: 16px;
      line-height: 1.2;
      font-family: Manrope-Medium;
      resize: none;
      outline: none;
      overflow: auto;
      scrollbar-width: none;
      &:disabled {
        opacity: 0.5;
        cursor: default;
      }
    }
    .send-button {
      display: flex;
      position: absolute;
      align-items: center;
      justify-content: center;
      right: 5px;
      bottom: 10px;
      width: 30px;
      height: 30px;
      border: none;
      border-radius: 999px;
      background-color: $dark;
      cursor: pointer;
      &:disabled {
        cursor: default;
        img {
          opacity: 0.5;
        }
      }
      img {
        width: 16px;
        height: 16px;
      }
    }
  }
}
.deleted-preview-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: $dark;
  z-index: 120;
  .deleted-preview-modal {
    display: flex;
    flex-direction: column;
    width: min(600px, 80vw);
    max-height: min(600px, 80dvh);
    border-radius: 20px;
    background-color: $graphite;
    box-shadow: 0 15px 30px rgba($black, 0.25);
    overflow: hidden;
    .deleted-preview-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 15px;
      background-color: $lead;
      .deleted-preview-header-main {
        display: flex;
        flex-direction: column;
        gap: 5px;
        span {
          color: $fg;
          font-size: 16px;
          font-family: Manrope-SemiBold;
        }
        small {
          color: $ashy;
          font-size: 12px;
        }
      }
      button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        padding: 0;
        border: none;
        background: none;
        cursor: pointer;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .deleted-preview-body {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 15px;
      overflow-y: auto;
      .deleted-preview-author {
        display: flex;
        align-items: center;
        gap: 5px;
        .deleted-preview-avatar {
          width: 30px;
          height: 30px;
          border-radius: 50%;
          object-fit: cover;
        }
        span {
          color: $fg;
          font-size: 16px;
          font-family: Manrope-Medium;
        }
      }
      .deleted-preview-text,
      .deleted-preview-empty {
        margin: 0;
        color: $fg;
        font-size: 16px;
        line-height: 1.2;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .message-link {
        color: $white;
        font-family: Manrope-SemiBold;
        text-decoration: underline;
        text-decoration-thickness: 1px;
        text-underline-offset: 2px;
        word-break: break-word;
      }
      .deleted-preview-empty {
        color: $ashy;
        font-style: italic;
      }
      .deleted-preview-image {
        width: 100%;
        max-height: 400px;
        border-radius: 10px;
        object-fit: contain;
        cursor: zoom-in;
      }
    }
  }
}
.image-lightbox-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: $dark;
  z-index: 130;
  .image-lightbox-close {
    position: absolute;
    top: 20px;
    right: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    padding: 0;
    border: none;
    border-radius: 999px;
    background-color: $graphite;
    cursor: pointer;
    img {
      width: 20px;
      height: 20px;
    }
  }
  .image-lightbox-image {
    max-width: min(80vw, 1440px);
    max-height: min(80vh, 960px);
    object-fit: contain;
    box-shadow: 0 15px 30px rgba($black, 0.25);
  }
}

.global-chat-panel-transition-enter-active,
.global-chat-panel-transition-leave-active,
.deleted-preview-modal-enter-active,
.image-lightbox-transition-enter-active,
.image-lightbox-transition-leave-active,
.deleted-preview-modal-leave-active,
.emoji-picker-pop-enter-active,
.emoji-picker-pop-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}

.global-chat-panel-transition-enter-from,
.global-chat-panel-transition-leave-to,
.deleted-preview-modal-enter-from,
.image-lightbox-transition-enter-from,
.image-lightbox-transition-leave-to,
.deleted-preview-modal-leave-to,
.emoji-picker-pop-enter-from,
.emoji-picker-pop-leave-to {
  opacity: 0;
}

.global-chat-panel-transition-enter-from,
.global-chat-panel-transition-leave-to,
.deleted-preview-modal-enter-from,
.image-lightbox-transition-enter-from,
.image-lightbox-transition-leave-to,
.deleted-preview-modal-leave-to {
  transform: translateY(-10px) scale(0.9);
}

.emoji-picker-pop-enter-from,
.emoji-picker-pop-leave-to {
  transform: translateY(10px) scale(0.9);
}

@media (max-width: 1280px) {
  .global-chat-dock {
    &.room-mode {
      bottom: 35px;
      right: 5px;
    }
  }
  .global-chat-panel {
    width: 300px;
    height: min(450px, calc(100dvh - 65px));
    border-radius: 5px;
    .panel-header {
      padding: 3px 8px;
      min-height: 20px;
      .panel-header-main {
        font-size: 16px;
      }
      button {
        width: 20px;
        height: 20px;
        img {
          width: 20px;
          height: 20px;
        }
      }
    }
    .panel-list {
      padding: 5px;
      gap: 5px;
      height: calc(100% - 68px);
      .load-more {
      }
      .empty-state {
        font-size: 12px;
      }
      .global-chat-message {
        padding: 3px 5px;
        width: calc(100% - 10px);
        border-radius: 5px;
        .message-main {
          gap: 3px;
          .message-meta {
            .message-meta-author {
              gap: 3px;
              .author-avatar {
                width: 16px;
                height: 16px;
              }
              .author-name {
                height: 14px;
                font-size: 12px;
              }
            }
            .message-time {
              font-size: 8px;
            }
          }
          .reply-preview {
            gap: 3px;
            padding: 3px;
            border-left: 3px solid rgba($orange, 0.5);
            .reply-preview-body {
              gap: 3px;
              .reply-avatar {
                width: 16px;
                height: 16px;
              }
              .reply-author {
                font-size: 11px;
              }
            }
            .reply-snippet {
              font-size: 10px;
            }
          }
          .message-bubble {
            gap: 3px;
            .message-text,
            .tombstone {
              padding: 3px 5px;
              font-size: 11px;
            }
            .tombstone {
            }
            .tombstone-actions {
              gap: 3px;
              .icon-action-button {
                max-height: 20px;
                padding: 3px 5px;
                img {
                  width: 12px;
                  height: 12px;
                }
              }
            }
            .message-image {
              max-height: 280px;
            }
          }
          .reactions-row {
            gap: 1px;
            .reaction-details-anchor {
              gap: 1px;
              .reaction-chip {
                gap: 1px;
                padding: 1px 5px 1px 3px;
                font-size: 10px;
                &--picker {
                  padding: 3px 5px;
                  img {
                    width: 12px;
                    height: 12px;
                  }
                }
              }
              .reaction-details-popover {
                padding: 3px 5px;
                gap: 5px;
                .reaction-details-item {
                  gap: 3px;
                  .reaction-details-avatar {
                    width: 20px;
                    height: 20px;
                  }
                  .reaction-details-meta {
                    gap: 3px;
                    .reaction-details-name {
                      font-size: 11px;
                    }
                    .reaction-details-time {
                      font-size: 9px;
                    }
                  }
                }
                .reaction-details-state {
                  font-size: 10px;
                  &--error {
                    color: $red;
                  }
                }
              }
            }
          }
        }
      }
    }
    .panel-status {
      padding: 5px 5px 0;
      gap: 5px;
      min-height: 20px;
      font-size: 11px;
      button {
        padding: 0 8px;
        height: 20px;
        font-size: 12px;
      }
    }
    .reply-bar {
      padding: 5px;
      gap: 5px;
      .reply-bar-text {
        gap: 3px;
        .reply-bar-label {
          font-size: 10px;
        }
        .reply-bar-snippet {
          font-size: 12px;
        }
      }
      button {
        min-width: 16px;
        min-height: 16px;
        img {
          width: 10px;
          height: 10px;
        }
      }
    }
    .image-preview {
      padding: 5px;
      .image-preview-div {
        gap: 3px;
        img {
          width: 30px;
          height: 30px;
        }
        .image-preview-meta {
          height: 30px;
          span {
            font-size: 10px;
          }
          small {
            font-size: 10px;
          }
        }
      }
      button {
        min-width: 16px;
        min-height: 16px;
        img {
          width: 10px;
          height: 10px;
        }
      }
    }
    .composer-shell {
      gap: 5px;
      min-height: 32px;
      .tool-button {
        left: 3px;
        bottom: 5px;
        width: 20px;
        height: 20px;
        &.right {
          right: 28px;
        }
        img {
          width: 12px;
          height: 12px;
        }
      }
      .composer-input {
        padding: 9px 53px 8px 28px;
        height: 15px;
        font-size: 12px;
      }
      .send-button {
        right: 3px;
        bottom: 5px;
        width: 20px;
        height: 20px;
        img {
          width: 12px;
          height: 12px;
        }
      }
    }
  }
  .deleted-preview-overlay {
    .deleted-preview-modal {
      border-radius: 10px;
      .deleted-preview-header {
        gap: 5px;
        padding: 5px 8px;
        .deleted-preview-header-main {
          gap: 3px;
          span {
            font-size: 14px;
          }
          small {
            font-size: 10px;
          }
        }
        button {
          width: 20px;
          height: 20px;
          img {
            width: 16px;
            height: 16px;
          }
        }
      }
      .deleted-preview-body {
        gap: 5px;
        padding: 10px;
        .deleted-preview-author {
          gap: 3px;
          .deleted-preview-avatar {
            width: 20px;
            height: 20px;
          }
          span {
            font-size: 14px;
          }
        }
        .deleted-preview-text,
        .deleted-preview-empty {
          font-size: 14px;
        }
        .deleted-preview-image {
          max-height: 300px;
        }
      }
    }
  }
  .image-lightbox-overlay {
    .image-lightbox-close {
      top: 10px;
      right: 10px;
      width: 30px;
      height: 30px;
      img {
        width: 16px;
        height: 16px;
      }
    }
    .image-lightbox-image {
    }
  }
}

</style>
