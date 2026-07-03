<template>
  <div v-if="canRender" :class="['global-chat-dock', { 'room-mode': isRoomMode }]">
    <Transition name="global-chat-panel-transition">
      <section v-if="chat.open" class="global-chat-panel" @click.stop>
        <header class="panel-header">
          <span class="panel-header-main">Общий чат</span>
          <div class="panel-header-actions">
            <button type="button" aria-label="Закрыть" @click="chat.closePanel()">
              <img :src="iconClose" alt="" />
            </button>
          </div>
        </header>

        <div ref="listEl" class="panel-list" @scroll="onListScroll" @wheel.passive="markUserScrollIntent" @touchstart.passive="markUserScrollIntent" @pointerdown="markUserScrollIntent">
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
            :style="messageCardStyle(message)"
          >
            <div class="message-main">
              <div class="message-meta">
                <button class="message-meta-author" :class="{ 'author-trigger': canOpenAuthorMiniProfile(message) }" type="button"
                        :disabled="!canOpenAuthorMiniProfile(message)" @click="openAuthorMiniProfile(message)">
                  <img class="author-avatar" v-minio-img="{ key: message.author.avatar_name ? `avatars/${message.author.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="Аватар автора" />
                  <div v-if="profileThemeIconSrcs(message.author.theme_icon, message.author.role).length" class="profile-theme-icons" aria-hidden="true">
                    <img v-for="badgeSrc in profileThemeIconSrcs(message.author.theme_icon, message.author.role)" :key="`${message.author.id}-${badgeSrc}`" class="profile-theme-icon" :src="badgeSrc" alt="" />
                  </div>
                  <span class="author-name">{{ message.author.username || (`user${message.author.id}`) }}</span>
                </button>
                <span class="message-time">{{ formatMessageTime(message.created_at) }}</span>
              </div>

              <button v-if="message.reply" class="reply-preview" type="button" @click="onJumpToReply(message.reply.message_id)">
                <div class="reply-preview-body">
                  <img class="reply-avatar" v-minio-img="{ key: message.reply.avatar_name ? `avatars/${message.reply.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="" />
                  <span class="reply-author">{{ message.reply.author_username }}</span>
                </div>
                <span class="reply-snippet">{{ message.reply.snippet || (message.reply.has_image ? 'Изображение' : 'Сообщение') }}</span>
              </button>

              <div class="message-bubble">
                <p v-if="message.deleted" class="tombstone">Сообщение удалено</p>
                <div v-if="showDeletedActions(message)" class="tombstone-actions">
                  <button class="icon-action-button" type="button" aria-label="Показать удаленное сообщение"
                          :disabled="isDeletedPreviewBusy(message.id)" @click="onPreviewDeletedMessage(message.id)" v-if="showDeletedPreviewAction(message)">
                    <img :src="iconInfo" alt="" />
                  </button>
                  <button class="icon-action-button icon-action-button--danger" type="button" aria-label="Удалить сообщение окончательно"
                          :disabled="chat.isPurgeBusy(message.id)" @click="onPurgeDeletedMessage(message)" v-if="showDeletedPurgeAction(message)">
                    <img :src="iconDelete" alt="" />
                  </button>
                </div>
                <template v-if="!message.deleted">
                  <img v-if="message.image_object_key" class="message-image" @click="onOpenImageLightbox($event, 'Вложение')" @load="onMessageMediaLoad" @error="onMessageMediaLoad" v-minio-img="{ key: message.image_object_key, lazy: true }" alt="Вложение" />
                  <p v-if="message.text" class="message-text">
                    <template v-for="(segment, index) in buildTextSegments(message.text, message.mentions)" :key="`${message.id}-text-${index}`">
                      <a v-if="segment.kind === 'link'" class="message-link" :href="segment.href" target="_blank" rel="noopener noreferrer nofollow" @click.stop>{{ segment.text }}</a>
                      <button v-else-if="segment.kind === 'mention' && segment.mention && canOpenMentionMiniProfile(segment.mention)"
                              class="message-mention message-mention-trigger" type="button" @click.stop="openMentionMiniProfile(segment.mention)">{{ segment.text }}</button>
                      <span v-else-if="segment.kind === 'mention'" class="message-mention">{{ segment.text }}</span>
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
                        <img class="reaction-details-avatar" v-minio-img="{ key: participant.user.avatar_name ? `avatars/${participant.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="Аватар" />
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
                    <div v-if="reactionPickerMessageId === message.id" class="emoji-picker emoji-picker--reactions" @click.stop>
                      <button v-for="emoji in reactionPickerItems" :key="emoji" class="emoji-button" type="button" @click="onSelectReaction(message.id, emoji)">
                        {{ emoji }}
                      </button>
                    </div>
                  </Transition>
                </div>
              </div>
            </div>
          </article>
        </div>

        <div v-if="hasUnreadTargets || showJumpToBottomButton" class="floating-chat-actions" :style="floatingChatActionsStyle">
          <button v-if="hasUnreadTargets" type="button" class="floating-chat-action-button" @click="onJumpToUnreadTarget">
            <img :src="iconDotMail" alt="" />
            <span>{{ unreadTargetsButtonLabel }}</span>
          </button>
          <button v-if="showJumpToBottomButton" type="button" class="floating-chat-action-button" @click="onJumpToBottom">
            <img :src="iconArrowDown" alt="" />
          </button>
        </div>

        <div v-if="statusText" ref="statusEl" class="panel-status" :class="{ 'panel-status--error': connectionState === 'error' }">
          <span>{{ statusText }}</span>
          <button v-if="connectionState === 'error'" type="button" @click="chat.openPanel()">Повторить</button>
        </div>

        <div v-if="draftReplyPreview" ref="replyBarEl" class="reply-bar">
          <div class="reply-bar-text">
            <span class="reply-bar-label">Ответ на сообщение {{ draftReplyPreview.author_username }}</span>
            <span class="reply-bar-snippet">{{ draftReplyPreview.snippet || (draftReplyPreview.has_image ? 'Изображение' : 'Сообщение') }}</span>
          </div>
          <button type="button" aria-label="Сбросить ответ" @click="chat.clearReplyTarget()">
            <img :src="iconClose" alt="" />
          </button>
        </div>

        <div v-if="draftImagePreviewUrl" ref="imagePreviewEl" class="image-preview">
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

        <div ref="composerShellEl" class="composer-shell">
          <label class="tool-button tool-button--file" :class="{ 'tool-button--disabled': composerDisabled }">
            <input type="file" accept="image/png,image/jpeg" :disabled="composerDisabled" @change="onPickImage" >
            <img :src="iconPhoto" alt="" />
          </label>

          <div class="composer-input-wrap">
            <div ref="composerMirrorEl" class="composer-highlight-overlay" aria-hidden="true">
              <p class="composer-highlight-content">
                <template v-for="(segment, index) in buildDraftTextSegments(draft)" :key="`draft-text-${index}`">
                  <span v-if="segment.kind === 'mention'" class="message-mention composer-mention">{{ segment.text }}</span>
                  <span v-else>{{ segment.text }}</span>
                </template>
              </p>
            </div>

          <textarea ref="textareaEl" v-model="draft" :class="['composer-input', { 'composer-input--mirrored': Boolean(draft) }]" :disabled="composerDisabled" @click="onComposerSelectionChange" @keyup="onComposerSelectionChange" @select="onComposerSelectionChange" @scroll="onComposerScroll" @blur="onComposerBlur" rows="3"
                    maxlength="1000" placeholder="Введите текст..." @keydown="onComposerKeydown" />

            <div v-if="mentionDropdownVisible" class="mention-suggestions" role="listbox" aria-label="Подсказки упоминаний">
              <p v-if="mentionLoading" class="mention-suggestions-state">Поиск…</p>
              <p v-else-if="mentionSuggestions.length === 0" class="mention-suggestions-state">Совпадений нет</p>
              <button v-for="(candidate, index) in mentionSuggestions" :key="candidate.id"
                      :class="['mention-suggestion', { 'mention-suggestion--active': mentionSelectedIndex === index }]"
                      type="button" role="option" :aria-selected="mentionSelectedIndex === index"
                      @pointerdown.prevent="selectMention(candidate)" @mouseenter="mentionSelectedIndex = index">
                <img class="mention-suggestion-avatar" v-minio-img="{ key: candidate.avatar_name ? `avatars/${candidate.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="" />
                <span class="mention-suggestion-name">@{{ candidate.username }}</span>
              </button>
            </div>
          </div>

          <button class="tool-button right" type="button" :disabled="composerDisabled" @pointerdown.stop @click="composerPickerOpen = !composerPickerOpen">
            <img :src="iconEmoji" alt="" />
          </button>
          <Transition name="emoji-picker-pop">
            <div v-if="composerPickerOpen" class="emoji-picker emoji-picker--composer" @click.stop>
              <div class="emoji-grid emoji-grid--composer">
                <button v-for="emoji in GLOBAL_CHAT_COMPOSER_EMOJIS" :key="emoji" class="emoji-button" type="button" @click="insertEmoji(emoji)">
                  {{ emoji }}
                </button>
              </div>
            </div>
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
              <img class="deleted-preview-avatar" v-minio-img="{ key: deletedPreview.author.avatar_name ? `avatars/${deletedPreview.author.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="Аватар автора" />
              <span>{{ deletedPreview.author.username || (`user${deletedPreview.author.id}`) }}</span>
            </div>

            <template v-if="deletedPreview.content_available">
              <p v-if="deletedPreview.text" class="deleted-preview-text">
                <template v-for="(segment, index) in buildTextSegments(deletedPreview.text, deletedPreview.mentions)" :key="`deleted-preview-text-${index}`">
                  <a v-if="segment.kind === 'link'" class="message-link" :href="segment.href" target="_blank" rel="noopener noreferrer nofollow" @click.stop>{{ segment.text }}</a>
                  <button v-else-if="segment.kind === 'mention' && segment.mention && canOpenMentionMiniProfile(segment.mention)"
                          class="message-mention message-mention-trigger" type="button" @click.stop="openMentionMiniProfile(segment.mention)">{{ segment.text }}</button>
                  <span v-else-if="segment.kind === 'mention'" class="message-mention">{{ segment.text }}</span>
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

    <MiniProfile
      v-model:open="miniProfileOpen"
      :user-id="miniProfileUserId"
      :initial-profile="miniProfileInitial"
      :stats-url="miniProfileStatsUrl"
      :show-stats-button="true"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { api } from '@/services/axios'
import { GLOBAL_CHAT_COMPOSER_EMOJIS } from '@/constants/chatEmojis'
import { buildProfileThemeBgStyle } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatChatTimestamp } from '@/services/datetime'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId, normalizeMiniProfileRole } from '@/services/miniProfile'
import { useAuthStore, useGlobalChatStore, useSettingsStore, useUserStore } from '@/store'
import MiniProfile from '@/components/MiniProfile.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatar.svg'
import iconClose from '@/assets/svg/iconClose.svg'
import iconEmoji from '@/assets/svg/iconEmoji.svg'
import iconPhoto from '@/assets/svg/photo.svg'
import iconDelete from '@/assets/svg/iconDelete.svg'
import iconInfo from '@/assets/svg/iconInfo.svg'
import iconSend from '@/assets/svg/send.svg'
import iconAddReaction from '@/assets/svg/addReaction.svg'
import iconReplyMessage from '@/assets/svg/replyMessage.svg'
import iconDotMail from '@/assets/svg/dotMail.svg'
import iconArrowDown from '@/assets/svg/iconArrow.svg'

import type {
  GlobalChatDeletedMessagePreview,
  GlobalChatMessage,
  GlobalChatMention,
  GlobalChatReaction,
  GlobalChatReactionParticipant,
} from '@/store/modules/globalChat'

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
  unreadTargetMessageIds,
  canSendCurrentDraft,
  lastMutationToken,
  lastMutationKind,
  lastMutationMessageId,
  lastMutationForceScroll,
} = storeToRefs(chat)

const listEl = ref<HTMLElement | null>(null)
const statusEl = ref<HTMLElement | null>(null)
const replyBarEl = ref<HTMLElement | null>(null)
const imagePreviewEl = ref<HTMLElement | null>(null)
const composerShellEl = ref<HTMLElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const composerMirrorEl = ref<HTMLElement | null>(null)
const composerPickerOpen = ref(false)
const knownMentionCandidates = ref<ChatMentionCandidate[]>([])
const mentionSuggestions = ref<ChatMentionCandidate[]>([])
const mentionLoading = ref(false)
const mentionHasSearched = ref(false)
const mentionSelectedIndex = ref(0)
const activeMentionRange = ref<{ start: number; end: number; query: string } | null>(null)
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
const miniProfileOpen = ref(false)
const miniProfileUserId = ref<number | null>(null)
const miniProfileInitial = ref<{
  id: number
  username?: string | null
  avatar_name?: string | null
  role?: string | null
  theme_color?: string | null
  theme_icon?: string | null
  deleted?: boolean | null
} | null>(null)
const reactionDetailsMessageId = ref<number | null>(null)
const reactionDetailsEmoji = ref('')
const reactionDetailsLoadingMessageId = ref<number | null>(null)
const reactionDetailsErrorMessageId = ref<number | null>(null)
let reactionDetailsRequestToken = 0
let mentionSearchToken = 0
let mentionSearchTimer: number | null = null
let highlightTimer: number | null = null
let scrollToBottomRaf: number | null = null
let scrollToBottomFramesRemaining = 0
let floatingChatActionsBottomRaf: number | null = null
let visibleUnreadTargetCheckRaf: number | null = null
let unreadTargetsOpenSettleToken = 0
let lastUserScrollIntentAt = 0
let visibleUnreadTargetAutoReadSuppressedUntil = 0
const floatingChatActionsBottom = ref(62)
const unreadTargetVisibilityTick = ref(0)
const unreadTargetsOpenSettlePending = ref(false)
const visibleUnreadTargetReadInFlightIds = new Set<number>()
const USER_SCROLL_INTENT_WINDOW_MS = 4000
const VISIBLE_UNREAD_TARGET_RATIO = 0.5
const VISIBLE_UNREAD_TARGET_MAX_PX = 120
const viewerMiniProfileRole = computed(() => normalizeMiniProfileRole(user.user?.role))
const isAdminUser = computed(() => viewerMiniProfileRole.value === 'admin')
const isChatModerator = computed(() => {
  return viewerMiniProfileRole.value === 'admin' || viewerMiniProfileRole.value === 'moder'
})
const miniProfileStatsUrl = computed(() => {
  const uid = Number(miniProfileUserId.value || 0)
  if (!Number.isFinite(uid) || uid <= 0) return null
  if (viewerMiniProfileRole.value === 'admin') return `/admin/users/${uid}/stats`
  if (viewerMiniProfileRole.value === 'moder') return `/moderation/users/${uid}/stats`
  return null
})
const isRoomMode = computed(() => route.name === 'room')

const showLauncher = computed(() => {
  if (!auth.ready || !settings.ready || !auth.isAuthed) return false
  if (!settings.chatOpenEnabled && !isAdminUser.value) return false
  if (!user.user) return false
  if (user.banActive || user.timeoutActive || user.inActiveGameAsPlayer) return false
  return !(settings.verificationRestrictions && !user.telegramVerified);
})
const canRender = computed(() => (settings.chatOpenEnabled || isAdminUser.value) && (showLauncher.value || chat.open))
const hiddenUnreadTargetMessageIds = computed(() => {
  unreadTargetVisibilityTick.value
  if (!chat.open) {
    return [...unreadTargetMessageIds.value]
  }
  return unreadTargetMessageIds.value.filter((messageId) => !isUnreadTargetVisible(messageId))
})
const hasUnreadTargets = computed(() => !unreadTargetsOpenSettlePending.value && hiddenUnreadTargetMessageIds.value.length > 0)
const nextUnreadTargetMessageId = computed(() => hiddenUnreadTargetMessageIds.value[hiddenUnreadTargetMessageIds.value.length - 1] || null)
const showJumpToBottomButton = computed(() => !stickToBottom.value)
const unreadTargetsButtonLabel = computed(() => hiddenUnreadTargetMessageIds.value.length)

const statusText = computed(() => {
  if (loadingInitial.value) return 'Загрузка истории…'
  if (connectionState.value === 'connecting') return 'Подключение к общему чату…'
  if (connectionState.value === 'reconnecting') return 'Соединение потеряно. Переподключаемся…'
  if (connectionState.value === 'error') return lastError.value || 'Не удалось подключиться к общему чату'
  if (!permissions.value.can_send) return 'Отправка сообщений временно недоступна'
  return ''
})

const floatingChatActionsStyle = computed(() => ({ bottom: `${floatingChatActionsBottom.value}px` }))

const composerDisabled = computed(() => {
  return connectionState.value !== 'ready'
    || !permissions.value.can_send
    || sending.value
    || uploadingImage.value
})
const reactionPickerItems = computed(() => reactionsAllowlist.value.filter((item, index, list) => Boolean(item) && list.indexOf(item) === index))
const composerPlaceholder = computed(() => (
  permissions.value.can_send ? 'Введите текст...' : 'Чат временно отключен...'
))
const showLoadMore = computed(() => hasMore.value && (loadingMore.value || listAtTop.value))
const mentionDropdownVisible = computed(() => Boolean(activeMentionRange.value?.query) && !composerDisabled.value && (mentionLoading.value || mentionHasSearched.value))
const messageCardStyle = (message: GlobalChatMessage) => buildProfileThemeBgStyle(message.author.theme_color)
const profileThemeIconSrcs = (icon: unknown, role?: unknown) => getProfileThemeBadgeSources(icon, role)

function canOpenAuthorMiniProfile(message: GlobalChatMessage): boolean {
  return canOpenMiniProfileTarget({
    targetId: message.author?.id,
    viewerId: normalizeMiniProfileUserId(user.user?.id),
    viewerRole: user.user?.role,
    targetRole: message.author?.role,
    targetDeletedAt: message.author?.deleted,
  })
}

function openAuthorMiniProfile(message: GlobalChatMessage) {
  if (!canOpenAuthorMiniProfile(message)) return
  const author = message.author
  const uid = Number(author?.id || 0)
  if (!Number.isFinite(uid) || uid <= 0) return
  miniProfileUserId.value = uid
  miniProfileInitial.value = {
    id: uid,
    username: author.username || null,
    avatar_name: author.avatar_name || null,
    role: author.role || null,
    theme_color: author.theme_color || null,
    theme_icon: author.theme_icon || null,
    deleted: Boolean(author.deleted),
  }
  miniProfileOpen.value = true
}

function canOpenMentionMiniProfile(mention: GlobalChatMention): boolean {
  if (!normalizeMiniProfileRole(mention?.role)) return false
  return canOpenMiniProfileTarget({
    targetId: mention?.id,
    viewerId: normalizeMiniProfileUserId(user.user?.id),
    viewerRole: user.user?.role,
    targetRole: mention?.role,
    targetDeletedAt: mention?.deleted,
  })
}

function openMentionMiniProfile(mention: GlobalChatMention): void {
  if (!canOpenMentionMiniProfile(mention)) return
  const uid = normalizeMiniProfileUserId(mention?.id)
  if (uid <= 0) return
  miniProfileUserId.value = uid
  miniProfileInitial.value = {
    id: uid,
    username: mention.username || null,
    avatar_name: mention.avatar_name || null,
    role: mention.role || null,
    theme_color: mention.theme_color || null,
    theme_icon: mention.theme_icon || null,
    deleted: Boolean(mention.deleted),
  }
  miniProfileOpen.value = true
}

type TextSegment = {
  kind: 'text' | 'link' | 'mention'
  text: string
  href?: string
  mention?: GlobalChatMention
}

type ChatMentionCandidate = {
  id: number
  username: string
  avatar_name: string | null
}

type ChatMentionSearchResponse = {
  items?: Array<{
    id?: number
    username?: string
    avatar_name?: string | null
  }>
}

const URL_RE = /((?:https?:\/\/|www\.)[^\s<]+)/gi
const TRAILING_URL_PUNCTUATION_RE = /[),.!?:;]+$/
const MENTION_CHAR_RE = /^[a-zA-Zа-яА-ЯёЁ0-9._\-()]$/
const MENTION_SEGMENT_RE = /(^|\s)@([a-zA-Zа-яА-ЯёЁ0-9._\-()]{2,20})(?![a-zA-Zа-яА-ЯёЁ0-9._\-()])/g

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
  unreadTargetVisibilityTick.value += 1
}

function readElementHeight(element: HTMLElement | null): number {
  return element?.offsetHeight || 0
}

function floatingChatActionsGap(): number {
  return window.innerWidth <= 1280 ? 8 : 10
}

function syncFloatingChatActionsBottom(): void {
  if (!chat.open) {
    floatingChatActionsBottom.value = 62
    return
  }

  floatingChatActionsBottom.value = floatingChatActionsGap()
    + readElementHeight(composerShellEl.value)
    + readElementHeight(imagePreviewEl.value)
    + readElementHeight(replyBarEl.value)
    + readElementHeight(statusEl.value)
}

function cancelScheduledFloatingChatActionsBottomSync(): void {
  if (floatingChatActionsBottomRaf !== null) {
    window.cancelAnimationFrame(floatingChatActionsBottomRaf)
    floatingChatActionsBottomRaf = null
  }
}

function scheduleFloatingChatActionsBottomSync(): void {
  cancelScheduledFloatingChatActionsBottomSync()
  floatingChatActionsBottomRaf = window.requestAnimationFrame(() => {
    floatingChatActionsBottomRaf = null
    syncFloatingChatActionsBottom()
  })
}

function markUserScrollIntent(): void {
  lastUserScrollIntentAt = Date.now()
}

function hasRecentUserScrollIntent(): boolean {
  return Date.now() - lastUserScrollIntentAt <= USER_SCROLL_INTENT_WINDOW_MS
}

function suppressVisibleUnreadTargetAutoRead(durationMs = 2000): void {
  visibleUnreadTargetAutoReadSuppressedUntil = Date.now() + Math.max(0, durationMs)
  lastUserScrollIntentAt = 0
}

function isVisibleUnreadTargetAutoReadSuppressed(): boolean {
  return Date.now() < visibleUnreadTargetAutoReadSuppressedUntil
}

function waitForAnimationFrame(): Promise<void> {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => resolve())
  })
}

function isUnreadTargetVisible(messageId: number): boolean {
  const list = listEl.value
  const element = findMessageElement(messageId)
  if (!list || !element) return false

  const listRect = list.getBoundingClientRect()
  const messageRect = element.getBoundingClientRect()
  const visibleHeight = Math.min(messageRect.bottom, listRect.bottom) - Math.max(messageRect.top, listRect.top)
  if (visibleHeight <= 0) return false

  const requiredVisibleHeight = Math.min(messageRect.height * VISIBLE_UNREAD_TARGET_RATIO, VISIBLE_UNREAD_TARGET_MAX_PX)
  return visibleHeight >= requiredVisibleHeight
}

function cancelScheduledVisibleUnreadTargetCheck(): void {
  if (visibleUnreadTargetCheckRaf !== null) {
    window.cancelAnimationFrame(visibleUnreadTargetCheckRaf)
    visibleUnreadTargetCheckRaf = null
  }
}

async function markVisibleUnreadTargetsRead(options: { requireUserScrollIntent?: boolean } = {}): Promise<void> {
  const requireUserScrollIntent = options.requireUserScrollIntent !== false
  if (!chat.open) return
  if (requireUserScrollIntent && (!hasRecentUserScrollIntent() || isVisibleUnreadTargetAutoReadSuppressed())) return

  const visibleMessageIds = unreadTargetMessageIds.value.filter((messageId) => (
    !visibleUnreadTargetReadInFlightIds.has(messageId) && isUnreadTargetVisible(messageId)
  ))
  if (visibleMessageIds.length === 0) return

  for (const messageId of visibleMessageIds) {
    visibleUnreadTargetReadInFlightIds.add(messageId)
  }

  for (const messageId of visibleMessageIds) {
    try {
      if (!chat.open) return
      await chat.markAlertRead(messageId)
    } finally {
      visibleUnreadTargetReadInFlightIds.delete(messageId)
    }
  }

  if (chat.open && unreadTargetMessageIds.value.length > 0 && (!requireUserScrollIntent || hasRecentUserScrollIntent())) {
    scheduleVisibleUnreadTargetReadCheck({ requireUserScrollIntent })
  }
}

function scheduleVisibleUnreadTargetReadCheck(options: { requireUserScrollIntent?: boolean } = {}): void {
  const requireUserScrollIntent = options.requireUserScrollIntent !== false
  if (!chat.open || unreadTargetMessageIds.value.length === 0) return
  if (requireUserScrollIntent && (!hasRecentUserScrollIntent() || isVisibleUnreadTargetAutoReadSuppressed())) return
  if (visibleUnreadTargetCheckRaf !== null) return

  visibleUnreadTargetCheckRaf = window.requestAnimationFrame(() => {
    visibleUnreadTargetCheckRaf = null
    void markVisibleUnreadTargetsRead({ requireUserScrollIntent })
  })
}

async function settleUnreadTargetsAfterOpen(): Promise<void> {
  const token = ++unreadTargetsOpenSettleToken
  unreadTargetsOpenSettlePending.value = chat.open && unreadTargetMessageIds.value.length > 0
  if (!unreadTargetsOpenSettlePending.value) {
    unreadTargetVisibilityTick.value += 1
    return
  }

  await nextTick()
  await waitForAnimationFrame()
  await waitForAnimationFrame()
  if (token !== unreadTargetsOpenSettleToken || !chat.open) return

  unreadTargetVisibilityTick.value += 1
  await markVisibleUnreadTargetsRead({ requireUserScrollIntent: false })
  if (token !== unreadTargetsOpenSettleToken || !chat.open) return

  unreadTargetVisibilityTick.value += 1
  unreadTargetsOpenSettlePending.value = false
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

function buildMentionLookup(mentions: GlobalChatMention[] = []): Map<string, GlobalChatMention> {
  const lookup = new Map<string, GlobalChatMention>()
  for (const mention of mentions) {
    const username = String(mention.username || '').trim()
    if (!username) continue
    const key = username.toLowerCase()
    if (!lookup.has(key)) {
      lookup.set(key, mention)
    }
  }
  return lookup
}

function buildKnownDraftMentions(): GlobalChatMention[] {
  const known = new Map<string, GlobalChatMention>()
  for (const message of messages.value) {
    const authorUsername = String(message.author.username || '').trim()
    if (authorUsername && !known.has(authorUsername.toLowerCase())) {
      known.set(authorUsername.toLowerCase(), {
        id: message.author.id,
        username: authorUsername,
        avatar_name: message.author.avatar_name || null,
        role: message.author.role,
        theme_color: message.author.theme_color || null,
        theme_icon: message.author.theme_icon || null,
        deleted: Boolean(message.author.deleted),
      })
    }
    for (const mention of message.mentions) {
      const mentionUsername = String(mention.username || '').trim()
      if (mentionUsername && !known.has(mentionUsername.toLowerCase())) {
        known.set(mentionUsername.toLowerCase(), mention)
      }
    }
  }
  for (const candidate of knownMentionCandidates.value) {
    const username = String(candidate.username || '').trim()
    if (!username || known.has(username.toLowerCase())) continue
    known.set(username.toLowerCase(), {
      id: candidate.id,
      username,
      avatar_name: candidate.avatar_name || null,
    })
  }
  return [...known.values()]
}

function rememberMentionCandidates(candidates: ChatMentionCandidate[]): void {
  if (!Array.isArray(candidates) || candidates.length === 0) return
  const known = new Map(knownMentionCandidates.value.map((candidate) => [candidate.username.toLowerCase(), candidate]))
  for (const candidate of candidates) {
    const username = String(candidate.username || '').trim()
    if (!username) continue
    known.set(username.toLowerCase(), {
      id: candidate.id,
      username,
      avatar_name: candidate.avatar_name || null,
    })
  }
  knownMentionCandidates.value = [...known.values()]
}

function buildNonLinkTextSegments(text: string, mentions: GlobalChatMention[] = []): TextSegment[] {
  if (!text) return []
  const mentionLookup = buildMentionLookup(mentions)
  if (mentionLookup.size === 0) {
    return [{ kind: 'text', text }]
  }

  const segments: TextSegment[] = []
  let lastIndex = 0

  for (const match of text.matchAll(MENTION_SEGMENT_RE)) {
    const prefix = String(match[1] || '')
    const username = String(match[2] || '').trim()
    const offset = Number(match.index ?? -1)
    const mention = mentionLookup.get(username.toLowerCase())
    if (!username || offset < 0 || !mention) continue
    const mentionStart = offset + prefix.length
    const mentionEnd = mentionStart + username.length + 1
    if (mentionStart > lastIndex) {
      segments.push({ kind: 'text', text: text.slice(lastIndex, mentionStart) })
    }
    segments.push({
      kind: 'mention',
      text: text.slice(mentionStart, mentionEnd),
      mention,
    })
    lastIndex = mentionEnd
  }

  if (lastIndex < text.length) {
    segments.push({ kind: 'text', text: text.slice(lastIndex) })
  }
  return segments.length ? segments : [{ kind: 'text', text }]
}

function buildTextSegments(value: string, mentions: GlobalChatMention[] = []): TextSegment[] {
  const text = String(value || '')
  if (!text) return []

  const segments: TextSegment[] = []
  let lastIndex = 0

  for (const match of text.matchAll(URL_RE)) {
    const rawUrl = String(match[0] || '')
    const offset = Number(match.index ?? -1)
    if (!rawUrl || offset < 0) continue
    if (offset > lastIndex) {
      segments.push(...buildNonLinkTextSegments(text.slice(lastIndex, offset), mentions))
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
    segments.push(...buildNonLinkTextSegments(text.slice(lastIndex), mentions))
  }
  return segments.length ? segments : [{ kind: 'text', text }]
}

function buildDraftTextSegments(value: string): TextSegment[] {
  return buildTextSegments(value, buildKnownDraftMentions())
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

function syncComposerMirrorScroll(): void {
  const textarea = textareaEl.value
  const mirror = composerMirrorEl.value
  if (!textarea || !mirror) return
  mirror.scrollTop = textarea.scrollTop
  mirror.scrollLeft = textarea.scrollLeft
}

function clearMentionSearchTimer(): void {
  if (mentionSearchTimer !== null) {
    window.clearTimeout(mentionSearchTimer)
    mentionSearchTimer = null
  }
}

function clearMentionSuggestions(): void {
  clearMentionSearchTimer()
  mentionSearchToken += 1
  mentionLoading.value = false
  mentionHasSearched.value = false
  mentionSuggestions.value = []
  mentionSelectedIndex.value = 0
  activeMentionRange.value = null
}

function isMentionChar(char: string): boolean {
  return MENTION_CHAR_RE.test(char)
}

function findActiveMentionRange(): { start: number; end: number; query: string } | null {
  const textarea = textareaEl.value
  const text = String(draft.value || '')
  if (!textarea) return null

  const selectionStart = Number(textarea.selectionStart ?? text.length)
  const selectionEnd = Number(textarea.selectionEnd ?? text.length)
  if (selectionStart !== selectionEnd) return null

  let start = selectionStart
  while (start > 0 && isMentionChar(text[start - 1] || '')) {
    start -= 1
  }
  if (start <= 0 || text[start - 1] !== '@') return null
  if (start > 1 && !/\s/.test(text[start - 2] || '')) return null

  let end = selectionStart
  while (end < text.length && isMentionChar(text[end] || '')) {
    end += 1
  }

  const query = text.slice(start, end)
  if (!query || query.length > 20) return null
  return {
    start: start - 1,
    end,
    query,
  }
}

async function fetchMentionSuggestions(query: string, token: number): Promise<void> {
  mentionLoading.value = true
  mentionHasSearched.value = false
  try {
    const { data } = await api.get<ChatMentionSearchResponse>('/users/chat/mentions', {
      params: {
        query,
        limit: 8,
      },
    })
    if (token !== mentionSearchToken) return
    mentionSuggestions.value = Array.isArray(data?.items)
      ? data.items
        .map((item) => {
          const id = Number(item?.id || 0)
          const username = String(item?.username || '').trim()
          if (id <= 0 || !username) return null
          return {
            id,
            username,
            avatar_name: String(item?.avatar_name || '') || null,
          } satisfies ChatMentionCandidate
        })
        .filter((item): item is ChatMentionCandidate => Boolean(item))
      : []
    rememberMentionCandidates(mentionSuggestions.value)
    mentionSelectedIndex.value = mentionSuggestions.value.length > 0 ? 0 : -1
  } catch {
    if (token !== mentionSearchToken) return
    mentionSuggestions.value = []
    mentionSelectedIndex.value = -1
  } finally {
    if (token === mentionSearchToken) {
      mentionLoading.value = false
      mentionHasSearched.value = true
    }
  }
}

function refreshMentionContext(): void {
  syncComposerMirrorScroll()
  if (composerDisabled.value) {
    clearMentionSuggestions()
    return
  }
  const nextRange = findActiveMentionRange()
  activeMentionRange.value = nextRange
  if (!nextRange?.query) {
    clearMentionSuggestions()
    return
  }
  clearMentionSearchTimer()
  mentionSuggestions.value = []
  mentionSelectedIndex.value = 0
  mentionHasSearched.value = false
  mentionLoading.value = true
  const token = ++mentionSearchToken
  mentionSearchTimer = window.setTimeout(() => {
    mentionSearchTimer = null
    void fetchMentionSuggestions(nextRange.query, token)
  }, 120)
}

function onComposerSelectionChange(): void {
  refreshMentionContext()
}

function onComposerScroll(): void {
  syncComposerMirrorScroll()
}

function onComposerBlur(): void {
  window.setTimeout(() => {
    if (document.activeElement === textareaEl.value) return
    clearMentionSuggestions()
  }, 0)
}

function selectMention(candidate: ChatMentionCandidate): void {
  const textarea = textareaEl.value
  const range = activeMentionRange.value
  const text = String(draft.value || '')
  if (!textarea || !range) return

  rememberMentionCandidates([candidate])
  const before = text.slice(0, range.start)
  const after = text.slice(range.end)
  const replacement = `@${candidate.username}${/^\s/.test(after) ? '' : ' '}`
  draft.value = `${before}${replacement}${after}`
  clearMentionSuggestions()
  void nextTick(() => {
    focusComposer()
    const nextPosition = before.length + replacement.length
    textarea.setSelectionRange(nextPosition, nextPosition)
    syncComposerMirrorScroll()
    refreshMentionContext()
  })
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
    return
  }
  if (activeMentionRange.value) {
    clearMentionSuggestions()
  }
}

function isPickerPointerTarget(target: EventTarget | null, pickerClass: string): boolean {
  return target instanceof Element && Boolean(target.closest(`.${pickerClass}`))
}

function onDocumentPointerDown(event: PointerEvent): void {
  if (composerPickerOpen.value && !isPickerPointerTarget(event.target, 'emoji-picker--composer')) {
    composerPickerOpen.value = false
  }
  if (reactionPickerMessageId.value !== null && !isPickerPointerTarget(event.target, 'emoji-picker--reactions')) {
    reactionPickerMessageId.value = null
  }
}

function scrollToBottom(behavior: ScrollBehavior = 'auto'): void {
  const list = listEl.value
  if (!list) return
  if (typeof list.scrollTo === 'function') {
    list.scrollTo({ top: list.scrollHeight, behavior })
    return
  }
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
  scheduleVisibleUnreadTargetReadCheck()
}

async function onLoadMore(): Promise<void> {
  markUserScrollIntent()
  const list = listEl.value
  const previousHeight = list?.scrollHeight || 0
  const previousTop = list?.scrollTop || 0
  const changed = await chat.loadMore()
  if (!changed || !list) return
  await nextTick()
  list.scrollTop = previousTop + (list.scrollHeight - previousHeight)
  updateScrollState()
  scheduleVisibleUnreadTargetReadCheck()
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
      : isChatModerator.value
        ? `Вы уверены, что хотите удалить сообщение пользователя ${authorName}?`
        : 'Вы уверены, что хотите удалить это сообщение?',
    confirmText: 'Подтвердить',
    cancelText: 'Отмена',
  })
  if (!confirmed) return

  await chat.deleteMessage(message.id)
}

function showDeletedPreviewAction(message: GlobalChatMessage): boolean {
  return Boolean(message.deleted && message.can_preview_deleted)
}

function showDeletedPurgeAction(message: GlobalChatMessage): boolean {
  return Boolean(message.deleted && message.can_purge_deleted)
}

function showDeletedActions(message: GlobalChatMessage): boolean {
  return showDeletedPreviewAction(message) || showDeletedPurgeAction(message)
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
  if (!showDeletedPurgeAction(message) || chat.isPurgeBusy(message.id)) return
  const confirmed = await confirmDialog({
    title: 'Окончательное удаление',
    text: 'Вы уверены, что хотите удалить сообщение навсегда?',
    confirmText: 'Подтвердить',
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

async function jumpToMessage(messageId: number, missingMessageText: string): Promise<boolean> {
  if (scrollToMessage(messageId, true)) {
    updateScrollState()
    return true
  }
  const ok = await chat.loadContext(messageId)
  if (!ok) {
    void alertDialog(missingMessageText)
    return false
  }
  await nextTick()
  if (!scrollToMessage(messageId, true)) {
    void alertDialog(missingMessageText)
    return false
  }
  updateScrollState()
  return true
}

async function onJumpToReply(messageId: number): Promise<void> {
  await jumpToMessage(messageId, 'Не удалось найти исходное сообщение.')
}

async function onJumpToUnreadTarget(): Promise<void> {
  const messageId = nextUnreadTargetMessageId.value
  if (!messageId) return
  suppressVisibleUnreadTargetAutoRead()
  const ok = await jumpToMessage(messageId, 'Не удалось найти сообщение с ответом, упоминанием или реакцией.')
  if (!ok) return
  await chat.markAlertRead(messageId)
}

function onJumpToBottom(): void {
  markUserScrollIntent()
  stickToBottom.value = true
  cancelScheduledScrollToBottom()
  scrollToBottom('smooth')
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
    syncComposerMirrorScroll()
    refreshMentionContext()
  })
}

function onComposerKeydown(event: KeyboardEvent): void {
  if (mentionDropdownVisible.value) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (mentionSuggestions.value.length > 0) {
        mentionSelectedIndex.value = (mentionSelectedIndex.value + 1 + mentionSuggestions.value.length) % mentionSuggestions.value.length
      }
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      if (mentionSuggestions.value.length > 0) {
        mentionSelectedIndex.value = (mentionSelectedIndex.value - 1 + mentionSuggestions.value.length) % mentionSuggestions.value.length
      }
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      clearMentionSuggestions()
      return
    }
    if ((event.key === 'Enter' || event.key === 'Tab') && mentionSuggestions.value.length > 0) {
      event.preventDefault()
      const fallbackIndex = mentionSelectedIndex.value >= 0 ? mentionSelectedIndex.value : 0
      const candidate = mentionSuggestions.value[fallbackIndex]
      if (candidate) {
        selectMention(candidate)
      }
      return
    }
  }
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
  clearMentionSuggestions()
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
    void settleUnreadTargetsAfterOpen()
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

watch(draft, () => {
  void nextTick(() => {
    syncComposerMirrorScroll()
    refreshMentionContext()
  })
})

watch(composerDisabled, (disabled) => {
  if (disabled) {
    clearMentionSuggestions()
    return
  }
  void nextTick(() => {
    syncComposerMirrorScroll()
    refreshMentionContext()
  })
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

watch(
  [() => chat.open, statusText, draftReplyPreview, draftImagePreviewUrl],
  ([open]) => {
    if (!open) return
    void nextTick(() => {
      scheduleFloatingChatActionsBottomSync()
    })
  },
  { immediate: true },
)

watch(() => chat.open, (open) => {
  if (!open) {
    unreadTargetsOpenSettleToken += 1
    cancelScheduledScrollToBottom()
    cancelScheduledFloatingChatActionsBottomSync()
    cancelScheduledVisibleUnreadTargetCheck()
    visibleUnreadTargetReadInFlightIds.clear()
    visibleUnreadTargetAutoReadSuppressedUntil = 0
    unreadTargetsOpenSettlePending.value = false
    lastUserScrollIntentAt = 0
    composerPickerOpen.value = false
    reactionPickerMessageId.value = null
    clearMentionSuggestions()
    closeReactionDetails()
    closeDeletedPreview()
    closeImageLightbox()
    return
  }
  void nextTick(() => {
    syncComposerPlaceholder()
    syncComposerMirrorScroll()
    refreshMentionContext()
    scheduleFloatingChatActionsBottomSync()
    scheduleScrollToBottom(true)
  })
})

function onWindowResize(): void {
  scheduleFloatingChatActionsBottomSync()
  unreadTargetVisibilityTick.value += 1
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('keydown', onWindowKeydown)
  window.addEventListener('resize', onWindowResize)
  stickToBottom.value = true
  void nextTick(() => {
    syncComposerPlaceholder()
    syncComposerMirrorScroll()
    refreshMentionContext()
    scheduleFloatingChatActionsBottomSync()
    scheduleScrollToBottom(true)
    focusComposer()
  })
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('keydown', onWindowKeydown)
  window.removeEventListener('resize', onWindowResize)
  cancelScheduledScrollToBottom()
  cancelScheduledFloatingChatActionsBottomSync()
  cancelScheduledVisibleUnreadTargetCheck()
  clearMentionSearchTimer()
  clearHighlightTimer()
  visibleUnreadTargetAutoReadSuppressedUntil = 0
  visibleUnreadTargetReadInFlightIds.clear()
  clearMentionSuggestions()
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
  .message-mention {
    color: $orange;
    font-family: Manrope-SemiBold;
  }
  .message-mention-trigger {
    display: inline;
    padding: 0;
    border: none;
    background: none;
    font: inherit;
    line-height: inherit;
    text-align: inherit;
    cursor: pointer;
  }
  &.room-mode {
    bottom: 60px;
    z-index: 25;
  }
  > * {
    pointer-events: auto;
  }
}
.global-chat-panel {
  position: relative;
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
    .panel-header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
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
  .floating-chat-actions {
    display: flex;
    position: absolute;
    flex-direction: column;
    right: 5px;
    gap: 10px;
    z-index: 10;
    pointer-events: none;
    .floating-chat-action-button {
      display: flex;
      position: relative;
      align-items: center;
      justify-content: center;
      padding: 0;
      width: 30px;
      height: 30px;
      border: 1px solid $dark;
      border-radius: 999px;
      background-color: $lead;
      box-shadow: 0 15px 30px rgba($black, 0.25);
      cursor: pointer;
      pointer-events: auto;
      img {
        width: 20px;
        height: 20px;
      }
      span {
        position: absolute;
        top: 3px;
        right: 3px;
        width: 12px;
        height: 12px;
        border-radius: 999px;
        background-color: $red;
        color: $fg;
        white-space: nowrap;
        font-family: Manrope-SemiBold;
        font-size: 10px;
        line-height: 1;
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
      align-self: center;
      padding: 0 15px;
      width: fit-content;
      min-height: 30px;
      border: none;
      border-radius: 999px;
      background-color: $lead;
      color: $fg;
      font-size: 14px;
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
      padding: 5px 8px;
      width: calc(100% - 20px);
      border-radius: 10px;
      background-color: var(--user-theme-bg, $graphite);
      border: 1px solid $lead;
      transition: border-color 0.25s ease-in-out;
      &--own {
        background-color: var(--user-theme-bg, $graphite);
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
            min-width: 0;
            padding: 0;
            gap: 3px;
            border: none;
            background: none;
            cursor: default;
            &:disabled {
              opacity: 1;
            }
            &.author-trigger {
              cursor: pointer;
            }
            .author-avatar {
              width: 20px;
              height: 20px;
              border-radius: 50%;
              object-fit: cover;
            }
            .profile-theme-icons {
              display: inline-flex;
              align-items: center;
              gap: 3px;
              flex: 0 0 auto;
              .profile-theme-icon {
                width: 20px;
                height: 20px;
                object-fit: contain;
              }
            }
            .author-name {
              min-width: 0;
              color: $fg;
              font-size: 16px;
              font-family: Manrope-Medium;
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
            user-select: text;
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
              bottom: calc(100% + 5px);
              left: 0;
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
    padding: 10px;
    gap: 10px;
    min-height: 30px;
    background-color: $lead;
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
      border-radius: 999px;
      background-color: $dark;
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
    .composer-input-wrap {
      width: 100%;
      background-color: $lead;
      overflow: hidden;
    }
    .composer-highlight-overlay {
      position: absolute;
      inset: 0;
      overflow: auto;
      pointer-events: none;
      scrollbar-width: none;
      &::-webkit-scrollbar {
        display: none;
      }
      .composer-highlight-content {
        margin: 0;
        padding: 18px 80px 14px 45px;
        width: calc(100% - 125px);
        height: 20px;
        color: $fg;
        font-size: 16px;
        line-height: 1.2;
        font-family: Manrope-Medium;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .composer-mention {
        font-family: inherit;
        font-weight: inherit;
      }
    }
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
      z-index: 5;
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
      position: relative;
      padding: 18px 80px 14px 45px;
      width: calc(100% - 125px);
      height: 20px;
      border: none;
      background-color: transparent;
      color: $fg;
      font-size: 16px;
      line-height: 1.2;
      font-family: Manrope-Medium;
      resize: none;
      outline: none;
      overflow: auto;
      scrollbar-width: none;
      caret-color: $fg;
      z-index: 1;
      &--mirrored {
        color: transparent;
      }
      &::selection {
        background-color: rgba($orange, 0.25);
        color: transparent;
      }
      &:disabled {
        opacity: 0.5;
        cursor: default;
      }
    }
    .mention-suggestions {
      display: flex;
      position: absolute;
      flex-direction: column;
      left: 0;
      right: 0;
      bottom: calc(100% - 1px);
      padding: 5px;
      gap: 5px;
      max-height: 150px;
      background-color: $lead;
      overflow-y: auto;
      scrollbar-width: thin;
      z-index: 10;
      .mention-suggestions-state {
        margin: 0;
        padding: 5px;
        color: $ashy;
        font-size: 14px;
      }
      .mention-suggestion {
        display: flex;
        align-items: center;
        gap: 3px;
        padding: 3px 5px;
        border: none;
        border-radius: 5px;
        background-color: transparent;
        color: $fg;
        cursor: pointer;
        &--active {
          background-color: rgba($orange, 0.25);
        }
        .mention-suggestion-avatar {
          width: 24px;
          height: 24px;
          border-radius: 50%;
          object-fit: cover;
        }
        .mention-suggestion-name {
          min-width: 0;
          font-size: 16px;
          font-family: Manrope-Medium;
          text-overflow: ellipsis;
          white-space: nowrap;
          overflow: hidden;
        }
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
      z-index: 5;
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
.emoji-picker {
  display: flex;
  position: absolute;
  transform-origin: bottom right;
  background-color: $lead;
  box-shadow: 0 15px 30px rgba($black, 0.25);
  overflow: hidden;
  z-index: 10;
  .emoji-button {
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    font-size: 18px;
    transition: transform 0.25s ease-in-out;
    cursor: pointer;
    &:hover {
      transform: translateY(-3px);
    }
  }
  &--reactions {
    bottom: calc(100% + 5px);
    right: 0;
    padding: 5px;
    border-radius: 999px;
    > .emoji-button {
      padding: 0;
      width: 30px;
      height: 30px;
    }
  }
  &--composer {
    flex-direction: column;
    bottom: calc(100% + 10px);
    right: 10px;
    padding: 10px;
    width: 250px;
    height: 200px;
    border-radius: 5px;
    overflow-y: auto;
    overflow-x: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    .emoji-grid--composer {
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 5px;
    }
  }
}
.deleted-preview-overlay {
  display: flex;
  position: fixed;
  align-items: center;
  justify-content: center;
  inset: 0;
  background-color: rgba($black, 0.5);
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
      .message-mention {
        color: $orange;
        font-family: Manrope-SemiBold;
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

</style>
