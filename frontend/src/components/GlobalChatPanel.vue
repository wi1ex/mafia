<template>
  <div v-if="canRender" class="global-chat-dock">
    <Transition name="global-chat-launcher">
      <button v-if="showLauncher && !chat.open" class="chat-launcher" type="button" @click="chat.openPanel()">
        <img :src="iconChat" alt="" />
      </button>
    </Transition>

    <Transition name="global-chat-panel-transition">
      <section v-if="chat.open" class="global-chat-panel" @click.stop>
        <header class="panel-header">
          <div class="panel-header-main">
            <span>Общий чат</span>
            <small>{{ headerStatus }}</small>
          </div>
          <button type="button" aria-label="Закрыть" @click="chat.closePanel()">
            <img :src="iconClose" alt="" />
          </button>
        </header>

        <div v-if="statusText" class="panel-status" :class="{ 'panel-status--error': connectionState === 'error' }">
          <span>{{ statusText }}</span>
          <button v-if="connectionState === 'error'" type="button" @click="chat.openPanel()">Повторить</button>
        </div>

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
            <img class="author-avatar" v-minio-img="{ key: message.author.avatar_name ? `avatars/${message.author.avatar_name}` : '', placeholder: defaultAvatar, lazy: false }" alt="Аватар автора" />

            <div class="message-main">
              <div class="message-meta">
                <span class="author-name">{{ message.author.username || (`user${message.author.id}`) }}</span>
                <span class="message-time">{{ formatMessageTime(message.created_at) }}</span>
              </div>

              <button v-if="message.reply" class="reply-preview" type="button" @click="onJumpToReply(message.reply.message_id)">
                <span class="reply-author">{{ message.reply.author_username }}</span>
                <span class="reply-snippet">{{ message.reply.snippet || (message.reply.has_image ? 'Изображение' : 'Сообщение') }}</span>
              </button>

              <div class="message-bubble">
                <p v-if="message.deleted" class="tombstone">Сообщение удалено</p>
                <template v-else>
                  <p v-if="message.text" class="message-text">{{ message.text }}</p>
                  <img v-if="message.image_object_key" class="message-image" v-minio-img="{ key: message.image_object_key, lazy: true }" alt="Вложение" />
                </template>
              </div>

              <div v-if="!message.deleted && orderedReactions(message).length > 0" class="reactions-row">
                <button v-for="reaction in orderedReactions(message)" :key="reaction.emoji" :class="['reaction-chip', { 'reaction-chip--active': reaction.reacted_by_me }]"
                        type="button" :disabled="chat.isReactionBusy(message.id)" @click="onToggleReaction(message.id, reaction.emoji)">
                  <span>{{ reaction.emoji }}</span>
                  <span>{{ reaction.count }}</span>
                </button>
              </div>

              <div class="message-actions">
                <button v-if="!message.deleted" class="action-button" type="button" @click="onReply(message.id)">
                  Ответить
                </button>

                <div v-if="!message.deleted && reactionsAllowlist.length > 0" class="reaction-picker-anchor">
                  <button class="action-button" type="button" :disabled="chat.isReactionBusy(message.id)" @click="toggleMessageReactionPicker(message.id)">
                    Реакция
                  </button>
                  <component
                    :is="EmojiPicker"
                    v-if="reactionPickerMessageId === message.id"
                    mode="reactions"
                    :reactions="reactionsAllowlist"
                    @select="onSelectReaction(message.id, $event)"
                    @close="reactionPickerMessageId = null"
                  />
                </div>

                <button v-if="message.can_delete" class="action-button action-button--danger" type="button"
                        :disabled="chat.isDeleteBusy(message.id)" @click="onDeleteMessage(message.id)">
                  Удалить
                </button>
              </div>
            </div>
          </article>
        </div>

        <div v-if="draftReplyPreview" class="reply-bar">
          <div class="reply-bar-text">
            <span class="reply-bar-label">Ответ на {{ draftReplyPreview.author_username }}</span>
            <span class="reply-bar-snippet">{{ draftReplyPreview.snippet || (draftReplyPreview.has_image ? 'Изображение' : 'Сообщение') }}</span>
          </div>
          <button type="button" aria-label="Сбросить ответ" @click="chat.clearReplyTarget()">×</button>
        </div>

        <div v-if="draftImagePreviewUrl" class="image-preview">
          <img :src="draftImagePreviewUrl" alt="Предпросмотр изображения" />
          <div class="image-preview-meta">
            <span>{{ draftImageName || 'Изображение' }}</span>
            <small>{{ draftImageUploaded ? 'Загружено' : (uploadingImage ? 'Загрузка…' : 'Будет отправлено вместе с сообщением') }}</small>
          </div>
          <button type="button" @click="chat.clearDraftImage()">Убрать</button>
        </div>

        <div class="composer-tools">
          <div class="picker-anchor">
            <button class="tool-button" type="button" :disabled="composerDisabled" @click="composerPickerOpen = !composerPickerOpen">
              😀
            </button>
            <component
              :is="EmojiPicker"
              v-if="composerPickerOpen"
              mode="composer"
              @select="insertEmoji"
              @close="composerPickerOpen = false"
            />
          </div>

          <label class="tool-button tool-button--file" :class="{ 'tool-button--disabled': composerDisabled }">
            <input ref="fileInputEl" type="file" accept="image/png,image/jpeg" :disabled="composerDisabled" @change="onPickImage" >
            PNG/JPG
          </label>

          <span class="composer-hint">Enter отправляет, Shift+Enter переносит строку</span>
        </div>

        <div class="composer-shell">
          <textarea
            ref="textareaEl"
            v-model="draft"
            class="composer-input"
            :disabled="composerDisabled"
            rows="3"
            maxlength="1000"
            placeholder="Напишите сообщение"
            @keydown="onComposerKeydown"
          />

          <button class="send-button" type="button" :disabled="!canSendCurrentDraft" @click="onSend" >
            <img :src="sendButtonImg" alt="" />
          </button>
        </div>
      </section>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { alertDialog } from '@/services/confirm'
import { formatChatTimestamp } from '@/services/datetime'
import { useAuthStore, useGlobalChatStore, useSettingsStore, useUserStore } from '@/store'

import defaultAvatar from '@/assets/svg/defaultAvatar.svg'
import iconClose from '@/assets/svg/close.svg'
import iconChat from '@/assets/svg/chat.svg'
import iconSend from '@/assets/svg/send.svg'
import iconSending from '@/assets/svg/sending.svg'

import type { GlobalChatMessage, GlobalChatReaction } from '@/store/modules/globalChat'

const EmojiPicker = defineAsyncComponent(() => import('@/components/GlobalChatEmojiPicker.vue'))
const auth = useAuthStore()
const user = useUserStore()
const settings = useSettingsStore()
const chat = useGlobalChatStore()
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
  canSendCurrentDraft,
  lastMutationToken,
  lastMutationKind,
  lastMutationMessageId,
} = storeToRefs(chat)

const listEl = ref<HTMLElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const fileInputEl = ref<HTMLInputElement | null>(null)
const composerPickerOpen = ref(false)
const reactionPickerMessageId = ref<number | null>(null)
const highlightedMessageId = ref<number | null>(null)
const stickToBottom = ref(true)
const listAtTop = ref(false)
let highlightTimer: number | null = null

const showLauncher = computed(() => {
  if (!auth.ready || !settings.ready || !auth.isAuthed) return false
  if (user.banActive || user.timeoutActive || user.inActiveGameAsAlivePlayer) return false
  return !(settings.verificationRestrictions && !user.telegramVerified);
})
const canRender = computed(() => showLauncher.value || chat.open)
const headerStatus = computed(() => {
  if (connectionState.value === 'reconnecting') return 'переподключение'
  if (sending.value) return 'отправка'
  if (uploadingImage.value) return 'загрузка изображения'
  return `${messages.value.length} сообщений`
})

const statusText = computed(() => {
  if (loadingInitial.value) return 'Загрузка истории…'
  if (connectionState.value === 'connecting') return 'Подключение к общему чату…'
  if (connectionState.value === 'reconnecting') return 'Соединение потеряно. Переподключаемся…'
  if (connectionState.value === 'error') return lastError.value || 'Не удалось подключить общий чат.'
  if (!permissions.value.can_send) return 'Отправка сообщений сейчас недоступна.'
  return ''
})

const composerDisabled = computed(() => {
  return connectionState.value !== 'ready'
    || !permissions.value.can_send
    || sending.value
    || uploadingImage.value
})
const showLoadMore = computed(() => hasMore.value && (loadingMore.value || listAtTop.value))
const sendButtonImg = computed(() => {
  if (uploadingImage.value || sending.value) return iconSending
  return iconSend
})

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

function formatMessageTime(value: string): string {
  return formatChatTimestamp(value)
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

function scrollToBottom(): void {
  const list = listEl.value
  if (!list) return
  list.scrollTop = list.scrollHeight
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

function onDeleteMessage(messageId: number): void {
  void chat.deleteMessage(messageId)
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
    composerPickerOpen.value = false
    return
  }

  const start = textarea.selectionStart ?? current.length
  const end = textarea.selectionEnd ?? current.length
  draft.value = `${current.slice(0, start)}${emoji}${current.slice(end)}`
  composerPickerOpen.value = false
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
  scrollToBottom()
  updateScrollState()
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
    scrollToBottom()
    updateScrollState()
    focusComposer()
    return
  }

  if (lastMutationKind.value === 'append') {
    scrollToBottom()
    updateScrollState()
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

watch(() => chat.open, (open) => {
  if (!open) {
    composerPickerOpen.value = false
    reactionPickerMessageId.value = null
  }
})

onMounted(() => {
  stickToBottom.value = true
  void nextTick(() => {
    scrollToBottom()
    updateScrollState()
    focusComposer()
  })
})

onBeforeUnmount(() => {
  clearHighlightTimer()
})
</script>

<style scoped lang="scss">
.global-chat-dock {
  position: fixed;
  top: 70px;
  right: 20px;
  pointer-events: none;
  z-index: 70;
  > * {
    pointer-events: auto;
  }
  .chat-launcher {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0 10px;
    height: 40px;
    border-radius: 999px;
    border: 1px solid $lead;
    background-color: $graphite;
    box-shadow: 0 15px 30px rgba($black, 0.25);
    cursor: pointer;
    img {
      width: 24px;
      height: 24px;
    }
  }
}

.global-chat-launcher-enter-active,
.global-chat-launcher-leave-active,
.global-chat-panel-transition-enter-active,
.global-chat-panel-transition-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}

.global-chat-launcher-enter-from,
.global-chat-launcher-leave-to,
.global-chat-panel-transition-enter-from,
.global-chat-panel-transition-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.9);
}

.global-chat-panel {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto auto auto;
  width: min(400px, calc(100vw - 25px));
  height: min(600px, calc(100dvh - 25px));
  border: 1px solid rgba($white, 0.1);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba($graphite, 0.9) 0%, rgba($dark, 0.9) 100%);
  box-shadow: 0 15px 30px rgba($black, 0.5);
  overflow: hidden;
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 15px;
    background-color: rgba($lead, 0.9);
    box-shadow: 0 3px 5px rgba($black, 0.25);
    .panel-header-main {
      display: flex;
      flex-direction: column;
      gap: 5px;
      span {
        color: $white;
        font-size: 18px;
        font-family: Manrope-SemiBold;
      }
      small {
        color: $ashy;
        font-size: 12px;
        text-transform: uppercase;
      }
    }
    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      border: none;
      border-radius: 5px;
      background: transparent;
      cursor: pointer;
      img {
        width: 20px;
        height: 20px;
      }
    }
  }
  .panel-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 15px;
    background-color: rgba($dark, 0.9);
    color: $ashy;
    font-size: 12px;
    &--error {
      color: rgba($red, 0.9);
    }
    button {
      min-height: 30px;
      padding: 0 10px;
      border: none;
      border-radius: 5px;
      background-color: rgba($lead, 0.9);
      color: $fg;
      cursor: pointer;
    }
  }
  .panel-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-height: 0;
    padding: 10px;
    overflow-y: auto;
    scrollbar-width: none;
  }
  .load-more {
    min-height: 30px;
    border: 1px solid rgba($white, 0.1);
    border-radius: 5px;
    background-color: rgba($dark, 0.9);
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
    display: grid;
    grid-template-columns: 35px minmax(0, 1fr);
    gap: 10px;
    padding: 10px;
    border-radius: 5px;
    background-color: rgba($lead, 0.5);
    border: 1px solid transparent;
    transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
    &--own {
      background-color: rgba($graphite, 0.9);
    }
    &--deleted {
      opacity: 0.5;
    }
    &--highlighted {
      border-color: rgba($yellow, 0.8);
      box-shadow: 0 0 0 1px rgba($yellow, 0.25), 0 15px 30px rgba($black, 0.25);
    }
    .author-avatar {
      width: 35px;
      height: 35px;
      border-radius: 50%;
      object-fit: cover;
    }
    .message-main {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-width: 0;
    }
    .message-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      .author-name {
        min-width: 0;
        color: $white;
        font-size: 14px;
        font-family: Manrope-SemiBold;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .message-time {
        flex-shrink: 0;
        color: $ashy;
        font-size: 12px;
        line-height: 1.2;
      }
    }
    .reply-preview {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 5px;
      padding: 5px 10px;
      border: none;
      border-left: 3px solid rgba($yellow, 0.5);
      border-radius: 5px;
      background-color: rgba($dark, 0.5);
      color: $fg;
      cursor: pointer;
      text-align: left;
      .reply-author {
        color: $white;
        font-size: 12px;
        font-family: Manrope-Medium;
      }
      .reply-snippet {
        color: $ashy;
        font-size: 12px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        width: 100%;
      }
    }
    .message-bubble {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 10px 15px;
      border-radius: 5px;
      background-color: rgba($dark, 0.9);
      .message-text,
      .tombstone {
        margin: 0;
        color: $fg;
        font-size: 14px;
        line-height: 1.5;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .tombstone {
        color: $ashy;
        font-style: italic;
      }
      .message-image {
        width: 100%;
        max-height: 300px;
        border-radius: 5px;
        object-fit: cover;
        background-color: rgba($lead, 0.5);
      }
    }
    .reactions-row {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }
    .reaction-chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 5px 10px;
      border: 1px solid rgba($white, 0.1);
      border-radius: 999px;
      background-color: rgba($dark, 0.75);
      color: $fg;
      cursor: pointer;
      font-size: 12px;
      transition: background-color 0.25s ease-in-out, border-color 0.25s ease-in-out;
      &:hover:enabled {
        background-color: rgba($graphite, 0.9);
      }
      &:disabled {
        opacity: 0.5;
        cursor: default;
      }
      &--active {
        border-color: rgba($green, 0.5);
        background-color: rgba($green, 0.1);
      }
    }
    .message-actions {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .reaction-picker-anchor {
      position: relative;
    }
    .action-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 30px;
      padding: 0 10px;
      border: none;
      border-radius: 5px;
      background-color: rgba($dark, 0.9);
      color: $fg;
      cursor: pointer;
      font-size: 12px;
      transition: background-color 0.2s ease-in-out;
      &:hover:enabled {
        background-color: rgba($graphite, 1);
      }
      &:disabled {
        opacity: 0.5;
        cursor: default;
      }
      &--danger {
        color: rgba($red, 0.9);
      }
    }
  }
  .reply-bar,
  .image-preview {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px;
    align-items: center;
    margin: 0 10px 10px;
    padding: 10px;
    border-radius: 5px;
    background-color: rgba($dark, 0.9);
  }
  .reply-bar {
    .reply-bar-text {
      display: flex;
      flex-direction: column;
      gap: 5px;
      min-width: 0;
    }
    .reply-bar-label {
      color: $white;
      font-size: 12px;
      font-family: Manrope-Medium;
    }
    .reply-bar-snippet {
      color: $ashy;
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    button {
      width: 30px;
      height: 30px;
      border: none;
      border-radius: 5px;
      background-color: rgba($lead, 0.9);
      color: $fg;
      cursor: pointer;
      font-size: 18px;
    }
  }
  .image-preview {
    grid-template-columns: 50px minmax(0, 1fr) auto;
    img {
      width: 50px;
      height: 50px;
      border-radius: 5px;
      object-fit: cover;
      background-color: rgba($lead, 0.5);
    }
    .image-preview-meta {
      display: flex;
      flex-direction: column;
      gap: 5px;
      min-width: 0;
      span,
      small {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      span {
        color: $white;
        font-size: 12px;
      }
      small {
        color: $ashy;
        font-size: 12px;
      }
    }
    button {
      min-height: 30px;
      padding: 0 10px;
      border: none;
      border-radius: 5px;
      background-color: rgba($lead, 0.9);
      color: $fg;
      cursor: pointer;
    }
  }
  .composer-tools {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 0 10px 10px;
    .picker-anchor {
      position: relative;
    }
    .tool-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 30px;
      min-height: 30px;
      padding: 0 10px;
      border: none;
      border-radius: 5px;
      background-color: rgba($lead, 0.9);
      color: $fg;
      cursor: pointer;
      font-size: 16px;
      &--file {
        position: relative;
        overflow: hidden;
        input {
          position: absolute;
          inset: 0;
          opacity: 0;
          cursor: pointer;
        }
      }
      &--disabled {
        opacity: 0.5;
        cursor: default;
      }
    }
    .composer-hint {
      min-width: 0;
      color: $grey;
      font-size: 12px;
      line-height: 1.2;
    }
  }
  .composer-shell {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px;
    padding: 0 10px 10px;
  }
  .composer-input {
    min-height: 80px;
    max-height: 180px;
    padding: 10px 15px;
    border: 1px solid rgba($white, 0.1);
    border-radius: 5px;
    background-color: rgba($dark, 0.9);
    color: $fg;
    resize: vertical;
    outline: none;
    font: inherit;
    &:disabled {
      opacity: 0.5;
    }
  }
  .send-button {
    min-width: 100px;
    border: none;
    border-radius: 5px;
    background-color: rgba($green, 0.9);
    color: $bg;
    cursor: pointer;
    font-family: Manrope-SemiBold;
    &:disabled {
      opacity: 0.5;
      cursor: default;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .global-chat-launcher-enter-active,
  .global-chat-launcher-leave-active,
  .global-chat-panel-transition-enter-active,
  .global-chat-panel-transition-leave-active {
    transition: none;
  }
  .global-chat-panel {
    .global-chat-message {
      transition: none;
      .reaction-chip,
      .action-button {
        transition: none;
      }
    }
  }
}

@media (max-width: 1280px) {
  .global-chat-dock {
    top: 60px;
    .chat-launcher {
      min-height: 35px;
      padding: 0 10px;
      font-size: 12px;
    }
  }
  .global-chat-panel {
    width: min(100vw - 15px, 400px);
    height: min(100dvh - 15px, 600px);
    .panel-header {
      padding: 5px 10px;
      .panel-header-main {
        span {
          font-size: 16px;
        }
        small {
          font-size: 10px;
        }
      }
    }
    .panel-status,
    .panel-list {
      padding-left: 10px;
      padding-right: 10px;
    }
    .global-chat-message {
      grid-template-columns: 30px minmax(0, 1fr);
      gap: 10px;
      padding: 10px;
      .author-avatar {
        width: 30px;
        height: 30px;
      }
      .message-meta {
        .author-name {
          font-size: 12px;
        }
        .message-time {
          font-size: 10px;
        }
      }
      .reply-preview {
        padding: 5px 10px;
        .reply-author,
        .reply-snippet {
          font-size: 12px;
        }
      }
      .message-bubble {
        padding: 5px 10px;
        .message-text,
        .tombstone {
          font-size: 12px;
        }
        .message-image {
          max-height: 200px;
        }
      }
      .reaction-chip,
      .action-button {
        min-height: 25px;
        font-size: 12px;
      }
    }
    .reply-bar,
    .image-preview,
    .composer-tools,
    .composer-shell {
      margin-left: 10px;
      margin-right: 10px;
      padding-left: 0;
      padding-right: 0;
    }
    .composer-shell {
      grid-template-columns: 1fr;
    }
    .send-button {
      min-height: 40px;
    }
  }
}
</style>
