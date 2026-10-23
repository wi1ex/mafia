<template>
  <div v-if="canRender" :class="['global-chat-dock', { 'room-mode': isRoomMode }]">
    <Transition name="global-chat-panel-transition">
      <section v-if="chat.open" class="global-chat-panel" :style="chatPanelStyle" @click.stop>
        <header class="panel-header">
          <div class="panel-heading">
            <span class="panel-header-icon"><UiIcon :icon="iconChat" /></span>
            <span class="panel-header-main">Общий чат</span>
          </div>
          <div class="panel-header-actions">
            <button class="chat-icon-button" type="button" aria-label="Закрыть чат" title="Закрыть чат" @click="chat.closePanel()">
              <UiIcon :icon="iconClose" />
            </button>
          </div>
        </header>

        <div class="panel-list-shell" @pointerdown.capture="markUserScrollIntent">
          <div ref="listEl" class="panel-list" @scroll="onListScroll" @wheel.passive="markUserScrollIntent" @touchstart.passive="markUserScrollIntent">
            <button v-if="showLoadMore" class="load-more" type="button" :disabled="loadingMore" @click="onLoadMore">
              {{ loadingMore ? 'Загрузка…' : 'Загрузить еще сообщения' }}
            </button>

            <div v-if="loadingInitial" class="history-loading" role="status" aria-label="Загрузка сообщений">
              <div v-for="index in 3" :key="index" class="message-skeleton" aria-hidden="true">
                <div class="skeleton-author"><span></span><span></span></div>
                <div class="skeleton-line"></div>
                <div class="skeleton-line skeleton-line--short"></div>
              </div>
            </div>
            <div v-else-if="messages.length === 0" class="empty-state">
              <span class="empty-state-icon"><UiIcon :icon="iconChat" /></span>
              <span class="empty-state-title">Сообщений пока нет</span>
              <span class="empty-state-text">Начните разговор — отправьте первое сообщение.</span>
            </div>

            <article v-for="message in messages" :key="message.id" :data-chat-message-id="message.id"
              :class="[
                'global-chat-message',
                {
                  'global-chat-message--deleted': message.deleted,
                  'global-chat-message--highlighted': highlightedMessageId === message.id,
                },
              ]"
            >
              <div class="message-main">
                <div class="message-meta">
                  <button class="message-meta-author" :class="{ 'author-trigger': canOpenAuthorMiniProfile(message) }" type="button"
                          :disabled="!canOpenAuthorMiniProfile(message)" @click="openAuthorMiniProfile(message)">
                    <img class="author-avatar" v-minio-img="{ key: message.author.avatar_name ? `avatars/${message.author.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="Аватар автора" />
                    <div v-if="profileThemeIconSrcs(message.author.theme_icon, message.author.role, message.author.id).length" class="profile-theme-icons" aria-hidden="true">
                      <img v-for="badgeSrc in profileThemeIconSrcs(message.author.theme_icon, message.author.role, message.author.id)" :key="`${message.author.id}-${badgeSrc}`" class="profile-theme-icon" :src="badgeSrc" alt="" />
                    </div>
                    <span class="author-name" :class="{ 'author-name--themed': getProfileThemeOption(message.author.theme_color) }" :style="authorNameStyle(message)">{{ message.author.username || (`user${message.author.id}`) }}</span>
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
                      <UiIcon :icon="iconInfo" />
                    </button>
                    <button class="icon-action-button icon-action-button--danger" type="button" aria-label="Удалить сообщение окончательно"
                            :disabled="chat.isPurgeBusy(message.id)" @click="onPurgeDeletedMessage(message)" v-if="showDeletedPurgeAction(message)">
                      <UiIcon :icon="iconDelete" />
                    </button>
                  </div>
                  <template v-if="!message.deleted">
                    <div v-if="message.image_object_key" class="message-image-shell">
                      <div class="message-image-placeholder" role="status" aria-label="Загрузка изображения">
                        <UiIcon :icon="iconPhoto" aria-hidden="true" />
                      </div>
                      <img class="message-image" @click="onOpenImageLightbox($event, 'Вложение')" @load="onMessageMediaLoad" @error="onMessageMediaLoad" v-minio-img="{ key: message.image_object_key, lazy: true }" alt="Вложение" />
                      <span class="message-image-error" role="status">Не удалось загрузить изображение</span>
                    </div>
                    <p v-if="message.text" class="message-text">
                      <template v-for="(segment, index) in buildTextSegments(message.text, message.mentions)" :key="`${message.id}-text-${index}`">
                        <a v-if="segment.kind === 'link'" class="message-link" :href="segment.href" target="_blank" rel="noopener noreferrer nofollow" @click.stop>{{ segment.text }}</a>
                        <button v-else-if="segment.kind === 'mention' && segment.mention && canOpenMentionMiniProfile(segment.mention)"
                                class="message-mention message-mention-trigger" :class="roleMentionClass(segment.text)" type="button" @click.stop="openMentionMiniProfile(segment.mention)">{{ segment.text }}</button>
                        <span v-else-if="segment.kind === 'mention'" class="message-mention" :class="roleMentionClass(segment.text)">{{ segment.text }}</span>
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
                            type="button" :disabled="!permissions.can_react || user.timeoutActive || chat.isReactionBusy(message.id)" @click="onToggleReaction(message.id, reaction.emoji)">
                      <span>{{ reaction.emoji }}</span>
                      <span>{{ reaction.count }}</span>
                    </button>

                    <div v-if="reactionDetailsVisible && reactionDetailsMessageId === message.id && reactionDetailsEmoji === reaction.emoji" class="reaction-details-popover" role="tooltip">
                      <p v-if="reactionDetailsLoadingMessageId === message.id" class="reaction-details-state">Загрузка...</p>
                      <p v-else-if="reactionDetailsErrorMessageId === message.id" class="reaction-details-state reaction-details-state--error">
                        Не удалось загрузить список реакций.
                      </p>
                      <template v-else>
                        <div v-for="participant in reactionDetailsParticipants" :key="`${participant.user.id}-${participant.created_at}`" class="reaction-details-item">
                          <img class="reaction-details-avatar" v-minio-img="{ key: participant.user.avatar_name ? `avatars/${participant.user.avatar_name}` : '', placeholder: defaultAvatar, lazy: false, animated: true }" alt="Аватар" />
                          <div class="reaction-details-meta">
                            <span class="reaction-details-name">{{ participant.user.username || (`user${participant.user.id}`) }}</span>
                            <small class="reaction-details-time">{{ formatMessageTime(participant.created_at) }}</small>
                          </div>
                        </div>
                      </template>
                    </div>
                  </div>

                  <div v-if="reactionsAllowlist.length > 0" class="reaction-details-anchor">
                    <button class="reaction-chip reaction-chip--picker" type="button" aria-label="Добавить реакцию" title="Добавить реакцию" :disabled="!permissions.can_react || user.timeoutActive || chat.isReactionBusy(message.id)"
                            @pointerdown.stop @click="toggleMessageReactionPicker(message.id)">
                      <UiIcon :icon="iconAddReaction" />
                    </button>
                    <button v-if="!message.deleted" class="reaction-chip reaction-chip--picker" type="button" aria-label="Ответить" title="Ответить" @click="onReply(message.id)">
                      <UiIcon :icon="iconReplyMessage" />
                    </button>
                    <button v-if="message.can_delete" class="reaction-chip reaction-chip--picker red" type="button" aria-label="Удалить сообщение" title="Удалить сообщение"
                            :disabled="chat.isDeleteBusy(message.id)" @click="onDeleteMessage(message)">
                      <UiIcon :icon="iconDelete" />
                    </button>
                    <Transition name="emoji-picker-pop">
                      <div v-if="reactionPickerMessageId === message.id" class="emoji-picker emoji-picker--reactions" :style="reactionPickerStyle" @click.stop>
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
          <UiScrollbar :target="listEl" :active="chat.open" theme="light" :inset-top="16" :inset-bottom="composerHeight + 16" :right="-4" />
        </div>

        <div v-if="hasUnreadTargets || showJumpToBottomButton" class="floating-chat-actions" :style="floatingChatActionsStyle">
          <button v-if="hasUnreadTargets" type="button" class="floating-chat-action-button" aria-label="К непрочитанным упоминаниям и ответам" title="Непрочитанные упоминания и ответы" @click="onJumpToUnreadTarget">
            <UiIcon :icon="iconDotMail" />
            <span>{{ unreadTargetsButtonLabel }}</span>
          </button>
          <button v-if="showJumpToBottomButton" type="button" class="floating-chat-action-button" aria-label="К последним сообщениям" title="К последним сообщениям" @click="onJumpToBottom">
            <UiIcon :icon="iconArrowDown" />
          </button>
        </div>

        <div ref="composerShellEl" class="composer-shell" :aria-busy="sending || uploadingImage">
          <div v-if="statusText" class="panel-status" :class="{ 'panel-status--error': connectionState === 'error' }" role="status">
            <UiIcon :icon="iconInfo" />
            <span>{{ statusText }}</span>
            <button v-if="connectionState === 'error'" type="button" @click="chat.openPanel()">Повторить</button>
          </div>

          <div v-if="draftReplyPreview" class="reply-bar">
            <div class="reply-bar-text">
              <span class="reply-bar-label">Ответ на сообщение {{ draftReplyPreview.author_username }}</span>
              <span class="reply-bar-snippet">{{ draftReplyPreview.snippet || (draftReplyPreview.has_image ? 'Изображение' : 'Сообщение') }}</span>
            </div>
            <button class="chat-icon-button" type="button" aria-label="Сбросить ответ" @click="chat.clearReplyTarget()">
              <UiIcon :icon="iconClose" />
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
            <button class="chat-icon-button" type="button" aria-label="Убрать изображение" title="Убрать изображение" @click="chat.clearDraftImage()">
              <UiIcon :icon="iconClose" />
            </button>
          </div>

          <div class="composer-box" :class="{ 'composer-box--disabled': composerDisabled, 'composer-box--drag-active': composerDragActive }"
               @dragenter="onComposerDragEnter" @dragover="onComposerDragOver" @dragleave="onComposerDragLeave" @drop="onComposerDrop">
            <div class="composer-input-wrap">
              <div ref="composerMirrorEl" class="composer-highlight-overlay" aria-hidden="true">
                <p class="composer-highlight-content">
                  <template v-for="(segment, index) in buildDraftTextSegments(draft)" :key="`draft-text-${index}`">
                    <span v-if="segment.kind === 'mention'" class="message-mention composer-mention" :class="roleMentionClass(segment.text)">{{ segment.text }}</span>
                    <span v-else>{{ segment.text }}</span>
                  </template>
                </p>
              </div>

              <textarea ref="textareaEl" v-model="draft" :class="['composer-input', { 'composer-input--mirrored': Boolean(draft) }]" :disabled="composerDisabled" @click="onComposerSelectionChange" @keyup="onComposerSelectionChange" @select="onComposerSelectionChange" @scroll="onComposerScroll" @blur="onComposerBlur" @paste="onComposerPaste" rows="3"
                        maxlength="1000" aria-label="Сообщение в общий чат" :placeholder="composerPlaceholder" @keydown="onComposerKeydown" />

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
            <div class="composer-toolbar">
              <div class="composer-tools">
                <label class="tool-button tool-button--file" :class="{ 'tool-button--disabled': composerDisabled }" title="Прикрепить изображение">
                  <input type="file" accept="image/png,image/jpeg" aria-label="Прикрепить изображение" :disabled="composerDisabled" @change="onPickImage" >
                  <UiIcon :icon="iconPhoto" />
                </label>
                <button class="tool-button" type="button" aria-label="Выбрать эмодзи" title="Выбрать эмодзи" :aria-expanded="composerPickerOpen" :disabled="composerDisabled" @pointerdown.stop @click="composerPickerOpen = !composerPickerOpen">
                  <UiIcon :icon="iconEmoji" />
                </button>
              </div>
              <span class="composer-counter" :class="{ 'composer-counter--limit': draft.length >= 1000 }">{{ draft.length }} / 1000</span>
              <button class="send-button" type="button" :aria-label="sending ? 'Отправка сообщения' : 'Отправить сообщение'" :title="sending ? 'Отправка…' : 'Отправить сообщение'" :disabled="!canSendCurrentDraft" @click="onSend">
                <span v-if="sending" class="sending-spinner" aria-hidden="true"></span>
                <UiIcon v-else :icon="iconSend" />
              </button>
            </div>
          </div>
          <Transition name="emoji-picker-pop">
            <div v-if="composerPickerOpen" class="emoji-picker emoji-picker--composer" @click.stop>
              <div ref="composerEmojiGridEl" class="emoji-grid emoji-grid--composer">
                <button v-for="emoji in GLOBAL_CHAT_COMPOSER_EMOJIS" :key="emoji" class="emoji-button" type="button" :aria-label="emoji" @click="insertEmoji(emoji)">
                  {{ emoji }}
                </button>
              </div>
              <UiScrollbar :target="composerEmojiGridEl" :active="composerPickerOpen" theme="grey" :inset-top="8" :inset-bottom="8" :right="4" />
            </div>
          </Transition>
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
            <button class="chat-icon-button" type="button" aria-label="Закрыть" @click="closeDeletedPreview()">
              <UiIcon :icon="iconClose" />
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
                          class="message-mention message-mention-trigger" :class="roleMentionClass(segment.text)" type="button" @click.stop="openMentionMiniProfile(segment.mention)">{{ segment.text }}</button>
                  <span v-else-if="segment.kind === 'mention'" class="message-mention" :class="roleMentionClass(segment.text)">{{ segment.text }}</span>
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
          <UiIcon :icon="iconClose" />
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
import { getProfileThemeOption } from '@/constants/profileThemes'
import { getProfileThemeBadgeSources } from '@/constants/profileIcons'
import { alertDialog, confirmDialog } from '@/services/confirm'
import { formatChatTimestamp } from '@/services/datetime'
import { canOpenMiniProfileTarget, normalizeMiniProfileUserId, normalizeMiniProfileRole } from '@/services/miniProfile'
import { useAuthStore, useGlobalChatStore, useSettingsStore, useUserStore } from '@/store'
import MiniProfile from '@/views/MiniProfile.vue'
import UiIcon from '@/components/UiIcon.vue'
import UiScrollbar from '@/components/UiScrollbar.vue'

import defaultAvatar from '@/assets/svg/iconDefaultAvatarBlack.svg'
import iconClose from '@/assets/svg/iconClose.svg'
import iconChat from '@/assets/svg/iconChat.svg'
import iconEmoji from '@/assets/svg/iconEmoji.svg'
import iconPhoto from '@/assets/svg/iconPhoto.svg'
import iconDelete from '@/assets/svg/iconDelete.svg'
import iconInfo from '@/assets/svg/iconInfo.svg'
import iconSend from '@/assets/svg/iconSendMessage.svg'
import iconAddReaction from '@/assets/svg/iconAddReaction.svg'
import iconReplyMessage from '@/assets/svg/iconReplyMessage.svg'
import iconDotMail from '@/assets/svg/iconDotMail.svg'
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
const composerShellEl = ref<HTMLElement | null>(null)
const composerHeight = ref(140)
const composerPickerMaxHeight = ref(276)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const composerMirrorEl = ref<HTMLElement | null>(null)
const composerEmojiGridEl = ref<HTMLElement | null>(null)
const composerPickerOpen = ref(false)
const composerDragActive = ref(false)
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
let reactionPopoverPositionRaf: number | null = null
let visibleUnreadTargetCheckRaf: number | null = null
let unreadTargetsOpenSettleToken = 0
let lastUserScrollIntentAt = 0
let visibleUnreadTargetAutoReadSuppressedUntil = 0
let composerDragDepth = 0
let composerResizeObserver: ResizeObserver | null = null
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
  if (user.banActive || user.inActiveGameAsPlayer) return false
  return !user.accountRestricted
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
  if (user.timeoutActive) return 'Во время таймаута можно читать чат, но нельзя отправлять сообщения и ставить реакции'
  if (!permissions.value.can_send) return 'Отправка сообщений временно недоступна'
  return ''
})

const floatingChatActionsStyle = computed(() => ({ bottom: `${floatingChatActionsBottom.value}px` }))
const chatPanelStyle = computed(() => ({
  '--chat-composer-height': `${composerHeight.value}px`,
  '--chat-composer-picker-max-height': `${composerPickerMaxHeight.value}px`,
}))

const composerDisabled = computed(() => {
  return connectionState.value !== 'ready'
    || !permissions.value.can_send
    || user.timeoutActive
    || sending.value
    || uploadingImage.value
})
const reactionPickerItems = computed(() => reactionsAllowlist.value.filter((item, index, list) => Boolean(item) && list.indexOf(item) === index))
const reactionPickerStyle = computed(() => ({ '--reaction-picker-columns': Math.max(1, Math.ceil(reactionPickerItems.value.length / 2)) }))
const reactionDetailsParticipants = computed(() => (
  reactionDetailsMessageId.value === null ? [] : reactionParticipantsFor(reactionDetailsMessageId.value, reactionDetailsEmoji.value)
))
const reactionDetailsVisible = computed(() => reactionDetailsMessageId.value !== null && (
  reactionDetailsLoadingMessageId.value === reactionDetailsMessageId.value
  || reactionDetailsErrorMessageId.value === reactionDetailsMessageId.value
  || reactionDetailsParticipants.value.length > 0
))
const composerPlaceholder = computed(() => (
  user.timeoutActive ? 'Только чтение — действует таймаут' : permissions.value.can_send ? 'Введите текст...' : 'Чат временно отключен...'
))
const showLoadMore = computed(() => hasMore.value && (loadingMore.value || listAtTop.value))
const mentionDropdownVisible = computed(() => Boolean(activeMentionRange.value?.query) && !composerDisabled.value && (mentionLoading.value || mentionHasSearched.value))
const authorNameStyle = (message: GlobalChatMessage) => {
  const theme = getProfileThemeOption(message.author.theme_color)
  return theme ? { '--chat-author-theme': theme.bg } : {}
}
const profileThemeIconSrcs = (icon: unknown, role?: unknown, userId?: unknown) => getProfileThemeBadgeSources(icon, role, { roleBadgeVariant: 'black', userId })

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

function visibleListBottom(list: HTMLElement): number {
  const bounds = list.getBoundingClientRect()
  const composerTop = composerShellEl.value?.getBoundingClientRect().top ?? bounds.bottom
  return Math.max(bounds.top, Math.min(bounds.bottom, composerTop))
}

function floatingChatActionsGap(): number {
  return window.innerWidth <= 1280 ? 8 : 10
}

function syncFloatingChatActionsBottom(): void {
  if (!chat.open) {
    floatingChatActionsBottom.value = 62
    return
  }

  const height = composerShellEl.value?.offsetHeight ?? 0
  floatingChatActionsBottom.value = floatingChatActionsGap() + height
  composerPickerMaxHeight.value = Math.max(0, Math.min(276, (listEl.value?.clientHeight ?? 0) - height))
  if (height === composerHeight.value) return

  const keepAtBottom = stickToBottom.value
  composerHeight.value = height
  void nextTick(() => {
    if (!chat.open) return
    if (keepAtBottom) scrollToBottom()
    updateScrollState()
    scheduleReactionPopoverPositionSync()
    scheduleVisibleUnreadTargetReadCheck()
  })
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

function syncReactionPopoverPositions(): void {
  const list = listEl.value
  if (!chat.open || !list || !list.clientWidth || !list.clientHeight) return
  const bounds = list.getBoundingClientRect()
  const scaleX = bounds.width / list.offsetWidth
  const scaleY = bounds.height / list.offsetHeight
  const inset = 8
  const left = bounds.left + (list.clientLeft + inset) * scaleX
  const top = bounds.top + (list.clientTop + inset) * scaleY
  const width = Math.max(0, list.clientWidth - inset * 2)
  const height = Math.max(0, (visibleListBottom(list) - top) / scaleY - inset)

  for (const popover of list.querySelectorAll<HTMLElement>('.reaction-details-popover, .emoji-picker--reactions')) {
    popover.style.setProperty('--reaction-popover-max-width', `${width}px`)
    popover.style.setProperty('--reaction-popover-max-height', `${height}px`)
    popover.style.setProperty('--reaction-popover-x', '0px')
    popover.style.setProperty('--reaction-popover-y', '0px')
    const rect = popover.getBoundingClientRect()
    const transform = window.getComputedStyle(popover).transform
    const matrix = transform === 'none' ? null : new DOMMatrixReadOnly(transform)
    const x = rect.left - (matrix?.m41 || 0) * scaleX
    const y = rect.top - (matrix?.m42 || 0) * scaleY
    const offsetX = Math.max(left, Math.min(x, left + width * scaleX - rect.width)) - x
    const offsetY = Math.max(top, Math.min(y, top + height * scaleY - rect.height)) - y
    popover.style.setProperty('--reaction-popover-x', `${offsetX / scaleX}px`)
    popover.style.setProperty('--reaction-popover-y', `${offsetY / scaleY}px`)
  }
}

function cancelScheduledReactionPopoverPositionSync(): void {
  if (reactionPopoverPositionRaf !== null) {
    window.cancelAnimationFrame(reactionPopoverPositionRaf)
    reactionPopoverPositionRaf = null
  }
}

function scheduleReactionPopoverPositionSync(): void {
  if (reactionPopoverPositionRaf !== null) return
  reactionPopoverPositionRaf = window.requestAnimationFrame(() => {
    reactionPopoverPositionRaf = null
    syncReactionPopoverPositions()
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
  const visibleHeight = Math.min(messageRect.bottom, visibleListBottom(list)) - Math.max(messageRect.top, listRect.top)
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

function roleMentionClass(text: string): string {
  const name = text.toLowerCase()
  if (name === '@модератор' || name === '@admin') return 'message-mention--moderator'
  if (name === '@ведущий') return 'message-mention--head'
  return ''
}

function buildMentionLookup(mentions: GlobalChatMention[] = []): Map<string, GlobalChatMention> {
  const lookup = new Map<string, GlobalChatMention>()
  for (const username of ['Модератор', 'Ведущий']) {
    lookup.set(username.toLowerCase(), { id: 0, username, avatar_name: null })
  }
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
  return message.reactions.filter((reaction) => reaction.count > 0).sort((left, right) => {
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
    const roleCandidates = ['Модератор', 'Ведущий']
      .filter(name => name.toLowerCase().startsWith(query.toLowerCase()))
      .map((username, index) => ({ id: -index - 1, username, avatar_name: null }))
    mentionSuggestions.value = [...roleCandidates, ...mentionSuggestions.value.filter(
      candidate => !['модератор', 'ведущий'].includes(candidate.username.toLowerCase()),
    )].slice(0, 8)
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
  const currentRange = activeMentionRange.value
  if (nextRange && currentRange
    && nextRange.start === currentRange.start
    && nextRange.end === currentRange.end
    && nextRange.query === currentRange.query
    && (mentionLoading.value || mentionHasSearched.value)) return
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

function onComposerSelectionChange(event?: Event): void {
  if (event instanceof KeyboardEvent && event.key === 'Escape') return
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
  reactionDetailsRequestToken += 1
  reactionDetailsMessageId.value = null
  reactionDetailsEmoji.value = ''
  reactionDetailsLoadingMessageId.value = null
  reactionDetailsErrorMessageId.value = null
}

async function openReactionDetails(messageId: number, emoji: string, options: { force?: boolean } = {}): Promise<void> {
  const normalizedEmoji = String(emoji || '').trim()
  const message = messages.value.find((item) => item.id === messageId)
  if (!message || message.deleted || !orderedReactions(message).some((reaction) => reaction.emoji === normalizedEmoji)) return
  const token = ++reactionDetailsRequestToken
  reactionDetailsMessageId.value = messageId
  reactionDetailsEmoji.value = normalizedEmoji
  reactionDetailsLoadingMessageId.value = null
  reactionDetailsErrorMessageId.value = null
  const hasCached = Object.prototype.hasOwnProperty.call(reactionParticipantsCache.value, messageId)
  if (hasCached && !options.force && reactionDetailsParticipants.value.length > 0) return

  reactionDetailsLoadingMessageId.value = messageId
  const participants = await chat.loadReactionParticipants(messageId, { force: options.force || hasCached })
  if (token !== reactionDetailsRequestToken) return
  if (reactionDetailsLoadingMessageId.value === messageId) {
    reactionDetailsLoadingMessageId.value = null
  }
  if (reactionDetailsMessageId.value !== messageId || reactionDetailsEmoji.value !== normalizedEmoji) return
  if (participants === null) {
    reactionDetailsErrorMessageId.value = messageId
  } else if (!participants.some((participant) => participant.emoji === normalizedEmoji)) {
    closeReactionDetails(messageId, normalizedEmoji)
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
  if (reactionPickerMessageId.value !== null) {
    reactionPickerMessageId.value = null
    return
  }
  if (composerPickerOpen.value) {
    composerPickerOpen.value = false
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
  scheduleReactionPopoverPositionSync()
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
  if (!permissions.value.can_react || user.timeoutActive) return
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
  attachDraftImage(file)
  if (input) input.value = ''
}

function attachDraftImage(file: File): void {
  if (composerDisabled.value) return
  chat.attachDraftImage(file)
  composerPickerOpen.value = false
  void nextTick(() => focusComposer())
}

function isComposerFileDrag(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types || []).includes('Files')
}

function resetComposerDragState(): void {
  composerDragDepth = 0
  composerDragActive.value = false
}

function onComposerDragEnter(event: DragEvent): void {
  if (!isComposerFileDrag(event)) return
  event.preventDefault()
  composerDragDepth += 1
  composerDragActive.value = !composerDisabled.value
}

function onComposerDragOver(event: DragEvent): void {
  if (!isComposerFileDrag(event)) return
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = composerDisabled.value ? 'none' : 'copy'
  }
}

function onComposerDragLeave(event: DragEvent): void {
  if (!isComposerFileDrag(event)) return
  composerDragDepth = Math.max(0, composerDragDepth - 1)
  composerDragActive.value = composerDragDepth > 0 && !composerDisabled.value
}

function onComposerDrop(event: DragEvent): void {
  if (!isComposerFileDrag(event)) return
  event.preventDefault()
  const file = Array.from(event.dataTransfer?.files || []).find((candidate) => candidate.type.toLowerCase().startsWith('image/'))
  resetComposerDragState()
  if (!file) return
  attachDraftImage(file)
}

function clipboardImageFile(event: ClipboardEvent): File | null {
  for (const item of Array.from(event.clipboardData?.items || [])) {
    if (item.kind !== 'file' || !item.type.toLowerCase().startsWith('image/')) continue
    const file = item.getAsFile()
    if (file) return file
  }
  return null
}

function onComposerPaste(event: ClipboardEvent): void {
  if (composerDisabled.value) return
  const file = clipboardImageFile(event)
  if (!file) return
  event.preventDefault()
  attachDraftImage(file)
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
    reactionPickerMessageId.value = null
    composerPickerOpen.value = false
    resetComposerDragState()
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

watch(composerShellEl, (element) => {
  composerResizeObserver?.disconnect()
  composerResizeObserver = null
  if (!element) return

  composerResizeObserver = new ResizeObserver(scheduleFloatingChatActionsBottomSync)
  composerResizeObserver.observe(element)
  scheduleFloatingChatActionsBottomSync()
}, { flush: 'post' })

watch(
  [reactionDetailsVisible, reactionDetailsParticipants, reactionDetailsLoadingMessageId, reactionDetailsErrorMessageId, reactionPickerMessageId],
  scheduleReactionPopoverPositionSync,
  { flush: 'post' },
)

watch(
  [() => chat.open, statusText, draftReplyPreview, draftImagePreviewUrl],
  ([open]) => {
    if (!open) return
    void nextTick(() => {
      scheduleFloatingChatActionsBottomSync()
      scheduleReactionPopoverPositionSync()
    })
  },
  { immediate: true },
)

watch(() => chat.open, (open) => {
  if (!open) {
    unreadTargetsOpenSettleToken += 1
    cancelScheduledScrollToBottom()
    cancelScheduledFloatingChatActionsBottomSync()
    cancelScheduledReactionPopoverPositionSync()
    cancelScheduledVisibleUnreadTargetCheck()
    visibleUnreadTargetReadInFlightIds.clear()
    visibleUnreadTargetAutoReadSuppressedUntil = 0
    unreadTargetsOpenSettlePending.value = false
    lastUserScrollIntentAt = 0
    composerPickerOpen.value = false
    resetComposerDragState()
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
  scheduleScrollToBottom()
  scheduleReactionPopoverPositionSync()
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
  composerResizeObserver?.disconnect()
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('keydown', onWindowKeydown)
  window.removeEventListener('resize', onWindowResize)
  cancelScheduledScrollToBottom()
  cancelScheduledFloatingChatActionsBottomSync()
  cancelScheduledReactionPopoverPositionSync()
  cancelScheduledVisibleUnreadTargetCheck()
  clearMentionSearchTimer()
  clearHighlightTimer()
  visibleUnreadTargetAutoReadSuppressedUntil = 0
  visibleUnreadTargetReadInFlightIds.clear()
  clearMentionSuggestions()
  closeReactionDetails()
  closeDeletedPreview()
  closeImageLightbox()
  resetComposerDragState()
})

watch(() => user.timeoutActive, () => {
  if (chat.open) void chat.refreshPermissions(false)
})
</script>

<style scoped lang="scss">
.global-chat-dock {
  position: fixed;
  right: 40px;
  bottom: 10px;
  color: $neutral-900;
  font-family: Hauora-Regular;
  font-size: 14px;
  line-height: 20px;
  pointer-events: none;
  z-index: 70;
  &.room-mode {
    right: 10px;
    bottom: 58px;
    z-index: 25;
  }
  > * {
    pointer-events: auto;
  }
  button,
  label {
    -webkit-tap-highlight-color: transparent;
  }
  button {
    font: inherit;
    transition: background-color 0.25s ease-in-out, color 0.25s ease-in-out, border-color 0.25s ease-in-out;
    &:focus-visible {
      outline: 2px solid $green-500;
      outline-offset: 2px;
    }
    &:disabled {
      cursor: not-allowed;
    }
  }
  .chat-icon-button {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 0;
    border: none;
    border-radius: 12px;
    background-color: $soft-purple-100;
    color: $neutral-black;
    cursor: pointer;
    --ui-icon-width: 20px;
    --ui-icon-height: 20px;
    &:hover {
      background-color: $soft-purple-200;
      color: $green-700;
    }
  }
  .message-link {
    color: $green-700;
    text-decoration: underline;
    text-decoration-thickness: 1px;
    text-underline-offset: 3px;
    word-break: break-word;
    &:hover {
      color: $green-800;
    }
  }
  .message-mention {
    color: var(--mention-color, #{$orange-700});
    font-family: Hauora-SemiBold;
    &--moderator {
      --mention-color: #{$red-600};
    }
    &--head {
      --mention-color: #{$green-700};
    }
  }
  .message-mention-trigger {
    display: inline;
    padding: 0;
    border: none;
    border-radius: 4px;
    background: none;
    font: inherit;
    text-align: inherit;
    cursor: pointer;
    &:hover {
      text-decoration: underline;
      text-underline-offset: 3px;
    }
  }
  .emoji-picker {
    position: absolute;
    box-sizing: border-box;
    padding: 8px 12px;
    border: 1px solid $neutral-200;
    border-radius: 24px;
    background-color: $neutral-white;
    box-shadow: 0 12px 32px rgba($neutral-black, 0.16);
    transform-origin: bottom right;
    z-index: 15;
    .emoji-button {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 34px;
      height: 34px;
      padding: 0;
      border: none;
      border-radius: 12px;
      background: none;
      font-family: 'Segoe UI Emoji', sans-serif;
      font-size: 22px;
      line-height: 1;
      cursor: pointer;
      &:hover {
        background-color: $soft-purple-100;
      }
    }
  }
  .global-chat-panel {
    display: flex;
    position: relative;
    flex-direction: column;
    box-sizing: border-box;
    padding: 0 8px;
    width: 510px;
    height: min(720px, calc(var(--app-viewport-height, 100dvh) - 112px));
    border: 1px solid transparent;
    border-radius: 24px;
    background-color: $neutral-100;
    box-shadow: 0 0 16px rgba($neutral-black, 0.16);
    overflow: hidden;
    .panel-header {
      display: flex;
      flex: 0 0 auto;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      gap: 16px;
      border-bottom: 1px solid $neutral-200;
      .panel-heading {
        display: flex;
        align-items: center;
        min-width: 0;
        gap: 12px;
        .panel-header-icon {
          display: flex;
          flex: 0 0 auto;
          align-items: center;
          justify-content: center;
          width: 44px;
          height: 44px;
          border-radius: 16px;
          background-color: $green-100;
          color: $green-700;
        }
        .panel-header-main {
          min-width: 0;
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 24px;
          line-height: 26px;
          letter-spacing: -0.48px;
        }
      }
      .panel-header-actions {
        display: flex;
        align-items: center;
      }
    }
    .panel-list-shell {
      display: flex;
      position: relative;
      flex: 1 1 0;
      flex-direction: column;
      min-height: 0;
    }
    .panel-list {
      display: flex;
      flex: 1 1 0;
      flex-direction: column;
      min-height: 0;
      padding: 16px 16px calc(var(--chat-composer-height, 140px) + 0px);
      scroll-padding-bottom: calc(var(--chat-composer-height, 140px) + 0px);
      gap: 8px;
      overflow: auto;
      overscroll-behavior: contain;
      scrollbar-width: none;
      &::-webkit-scrollbar {
        display: none;
        width: 0;
        height: 0;
      }
      > * {
        flex-shrink: 0;
      }
      .load-more {
        align-self: center;
        padding: 9px 16px;
        border: 1px solid $neutral-200;
        border-radius: 12px;
        background-color: $neutral-white;
        color: $neutral-600;
        cursor: pointer;
        &:hover:not(:disabled) {
          border-color: $green-500;
          color: $green-700;
        }
        &:disabled {
          opacity: 0.5;
        }
      }
      .history-loading {
        display: flex;
        flex-direction: column;
        gap: 12px;
        .message-skeleton {
          padding: 16px;
          border-radius: 24px;
          background-color: $neutral-white;
          .skeleton-author {
            display: flex;
            align-items: center;
            margin-bottom: 14px;
            gap: 10px;
            span {
              height: 12px;
              border-radius: 8px;
              background-color: $soft-purple-100;
              &:first-child {
                width: 28px;
                height: 28px;
                border-radius: 50%;
              }
              &:last-child {
                width: 110px;
              }
            }
          }
          .skeleton-line {
            width: 100%;
            height: 10px;
            margin-top: 10px;
            border-radius: 8px;
            background-color: $soft-purple-100;
            &--short {
              width: 65%;
            }
          }
        }
      }
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin: auto;
        padding: 32px 20px;
        gap: 12px;
        text-align: center;
        .empty-state-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 72px;
          height: 72px;
          margin-bottom: 8px;
          border-radius: 24px;
          background-color: $neutral-white;
          color: $green-500;
          --ui-icon-width: 32px;
          --ui-icon-height: 32px;
        }
        .empty-state-title {
          color: $neutral-black;
          font-family: Involve-Medium;
          font-size: 20px;
          line-height: 24px;
          letter-spacing: -0.4px;
        }
        .empty-state-text {
          max-width: 260px;
          color: $neutral-500;
          line-height: 20px;
        }
      }
      .global-chat-message {
        box-sizing: border-box;
        width: 100%;
        padding: 12px;
        border: 1px solid transparent;
        border-radius: 24px;
        background-color: $neutral-white;
        transition: border-color 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
        &--highlighted {
          border-color: $green-500;
          box-shadow: 0 0 0 2px rgba($green-500, 0.18);
        }
        .message-main {
          display: flex;
          flex-direction: column;
          min-width: 0;
          gap: 8px;
          .message-meta {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            gap: 12px;
            border-radius: 12px;
            background-color: $neutral-50;
            .message-meta-author {
              display: flex;
              align-items: center;
              min-width: 0;
              padding: 0;
              gap: 2px;
              border: none;
              border-radius: 8px;
              background: none;
              cursor: default;
              &:disabled {
                opacity: 1;
              }
              &.author-trigger {
                cursor: pointer;
              }
              .author-avatar {
                flex: 0 0 auto;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                object-fit: cover;
              }
              .profile-theme-icons {
                display: inline-flex;
                flex: 0 0 auto;
                align-items: center;
                gap: 2px;
                .profile-theme-icon {
                  width: 24px;
                  height: 24px;
                  object-fit: contain;
                }
              }
              .author-name {
                margin-left: 2px;
                min-width: 0;
                color: $neutral-black;
                font-family: Hauora-SemiBold;
                font-size: 16px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                &--themed {
                  background-image: var(--chat-author-theme, none);
                  background-clip: text;
                  -webkit-background-clip: text;
                  color: transparent;
                  -webkit-text-fill-color: transparent;
                }
              }
            }
            .message-time {
              flex-shrink: 0;
              color: $neutral-500;
              font-size: 12px;
              line-height: 16px;
            }
          }
          .reply-preview {
            display: flex;
            flex-direction: column;
            padding: 8px 12px;
            gap: 4px;
            border: none;
            border-left: 4px solid $green-500;
            border-radius: 12px;
            background-color: $neutral-50;
            text-align: left;
            cursor: pointer;
            &:hover {
              background-color: $green-100;
            }
            .reply-preview-body {
              display: flex;
              align-items: center;
              min-width: 0;
              gap: 6px;
              .reply-avatar {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                object-fit: cover;
              }
              .reply-author {
                color: $green-700;
                font-family: Hauora-Medium;
                font-size: 12px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
              }
            }
            .reply-snippet {
              color: $neutral-600;
              font-size: 12px;
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
            }
          }
          .message-bubble {
            display: flex;
            flex-direction: column;
            min-width: 0;
            gap: 8px;
            .message-text,
            .tombstone {
              margin: 0;
              padding: 4px;
              color: $neutral-900;
              font-size: 16px;
              line-height: 22px;
              user-select: text;
              white-space: pre-wrap;
              overflow-wrap: anywhere;
            }
            .tombstone {
              color: $neutral-500;
              font-size: 14px;
              font-style: italic;
            }
            .tombstone-actions {
              display: flex;
              justify-content: flex-end;
              gap: 4px;
              .icon-action-button {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 30px;
                height: 30px;
                padding: 0;
                border: none;
                border-radius: 12px;
                background-color: $soft-purple-100;
                color: $neutral-black;
                cursor: pointer;
                --ui-icon-width: 20px;
                --ui-icon-height: 20px;
                &:hover:not(:disabled) {
                  background-color: $soft-purple-200;
                }
                &--danger {
                  background-color: $red-100;
                  color: $red-600;
                  &:hover:not(:disabled) {
                    background-color: $red-200;
                  }
                }
                &:disabled {
                  opacity: 0.4;
                }
              }
            }
            .message-image-shell {
              position: relative;
              width: 100%;
              aspect-ratio: 4 / 3;
              max-height: 260px;
              border-radius: 12px;
              background-color: $neutral-50;
              overflow: hidden;
              .message-image-placeholder,
              .message-image-error,
              .message-image {
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
              }
              .message-image-placeholder,
              .message-image-error {
                display: flex;
                align-items: center;
                justify-content: center;
                transition: opacity 0.25s ease-in-out, visibility 0.25s ease-in-out;
              }
              .message-image-placeholder {
                background-color: $soft-purple-100;
                color: $soft-purple-400;
                --ui-icon-width: 36px;
                --ui-icon-height: 36px;
                &::after {
                  position: absolute;
                  inset: 0;
                  background: linear-gradient(90deg, transparent, rgba($neutral-white, 0.55), transparent);
                  animation: chat-image-shimmer 1.5s ease-in-out infinite;
                  content: '';
                }
              }
              .message-image {
                display: block;
                object-fit: contain;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.25s ease-in-out;
                cursor: zoom-in;
              }
              .message-image-error {
                box-sizing: border-box;
                padding: 16px;
                color: $neutral-500;
                font-size: 14px;
                text-align: center;
                opacity: 0;
                visibility: hidden;
                pointer-events: none;
              }
              &:has(.message-image[data-minio-state='loaded']),
              &:has(.message-image[data-minio-state='error']) {
                .message-image-placeholder {
                  opacity: 0;
                  visibility: hidden;
                  &::after {
                    animation: none;
                  }
                }
              }
              &:has(.message-image[data-minio-state='loaded']) .message-image {
                opacity: 1;
                pointer-events: auto;
              }
              &:has(.message-image[data-minio-state='error']) .message-image-error {
                opacity: 1;
                visibility: visible;
              }
            }
          }
          .reactions-row {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            .reaction-details-anchor {
              display: flex;
              position: relative;
              align-items: center;
              gap: 4px;
              &:last-child {
                margin-left: auto;
              }
              .reaction-chip {
                display: flex;
                align-items: center;
                justify-content: center;
                box-sizing: border-box;
                padding: 0 6px;
                height: 30px;
                border: 1px solid $neutral-100;
                border-radius: 12px;
                background-color: $neutral-50;
                color: $neutral-600;
                font-weight: bold;
                font-size: 14px;
                line-height: 16px;
                cursor: pointer;
                --ui-icon-width: 20px;
                --ui-icon-height: 20px;
                &:hover:not(:disabled) {
                  border-color: $green-500;
                  background-color: $green-100;
                  color: $green-700;
                }
                &--active {
                  gap: 2px;
                  width: auto;
                  border-color: $green-400;
                  background-color: $green-100;
                  color: $green-700;
                }
                &--picker {
                  border-color: transparent;
                  background-color: $soft-purple-100;
                  color: $neutral-black;
                  &.red {
                    background-color: $red-100;
                    color: $red-600;
                    &:hover:not(:disabled) {
                      border-color: $red-400;
                      background-color: $red-200;
                      color: $red-700;
                    }
                  }
                }
                &:disabled {
                  opacity: 0.4;
                }
              }
              .reaction-details-popover,
              .emoji-picker--reactions {
                max-width: var(--reaction-popover-max-width, none);
                translate: var(--reaction-popover-x, 0px) var(--reaction-popover-y, 0px);
              }
              .reaction-details-popover {
                display: flex;
                position: absolute;
                flex-direction: column;
                box-sizing: border-box;
                bottom: calc(100% + 8px);
                left: 0;
                width: 220px;
                max-height: min(220px, var(--reaction-popover-max-height, 220px));
                padding: 8px 12px;
                gap: 4px;
                border: 1px solid $neutral-200;
                border-radius: 16px;
                background-color: $neutral-white;
                box-shadow: 0 8px 24px rgba($neutral-black, 0.16);
                overflow: auto;
                scrollbar-width: thin;
                scrollbar-color: $neutral-200 transparent;
                z-index: 12;
                .reaction-details-item {
                  display: flex;
                  flex-shrink: 0;
                  align-items: center;
                  min-width: 0;
                  gap: 4px;
                  .reaction-details-avatar {
                    flex-shrink: 0;
                    width: 24px;
                    height: 24px;
                    border-radius: 50%;
                    object-fit: cover;
                  }
                  .reaction-details-meta {
                    display: flex;
                    flex-direction: column;
                    min-width: 0;
                    .reaction-details-name {
                      color: $neutral-black;
                      font-size: 12px;
                      overflow: hidden;
                      text-overflow: ellipsis;
                      white-space: nowrap;
                    }
                    .reaction-details-time {
                      color: $neutral-500;
                      font-size: 10px;
                      line-height: 10px;
                    }
                  }
                }
                .reaction-details-state {
                  margin: 0;
                  color: $neutral-500;
                  font-size: 13px;
                  line-height: 18px;
                  &--error {
                    color: $red-600;
                  }
                }
              }
              .emoji-picker--reactions {
                display: grid;
                grid-template-columns: repeat(var(--reaction-picker-columns), 34px);
                right: 0;
                bottom: calc(100% + 8px);
                width: max-content;
                max-height: min(200px, var(--reaction-popover-max-height, 200px));
                gap: 4px;
                overflow: auto;
                scrollbar-width: thin;
                scrollbar-color: $neutral-200 transparent;
              }
            }
          }
        }
      }
    }
    .floating-chat-actions {
      display: flex;
      position: absolute;
      flex-direction: column;
      right: 24px;
      gap: 8px;
      z-index: 10;
      pointer-events: none;
      .floating-chat-action-button {
        display: flex;
        position: relative;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        padding: 0;
        border: 1px solid $neutral-200;
        border-radius: 12px;
        background-color: $neutral-white;
        color: $neutral-black;
        box-shadow: 0 4px 16px rgba($neutral-black, 0.16);
        cursor: pointer;
        pointer-events: auto;
        &:hover {
          border-color: $green-500;
          color: $green-700;
        }
        span {
          display: flex;
          position: absolute;
          align-items: center;
          justify-content: center;
          top: -5px;
          right: -5px;
          min-width: 18px;
          height: 18px;
          padding: 0 3px;
          box-sizing: border-box;
          border: 2px solid $neutral-100;
          border-radius: 12px;
          background-color: $green-500;
          color: $neutral-black;
          font-family: Hauora-SemiBold;
          font-size: 10px;
          line-height: 14px;
        }
      }
    }
    .panel-status {
      display: flex;
      flex: 0 0 auto;
      align-items: center;
      margin: 0;
      padding: 8px 12px;
      gap: 4px;
      border: 1px solid $neutral-200;
      border-radius: 12px;
      background-color: $neutral-white;
      color: $neutral-600;
      font-size: 16px;
      line-height: 18px;
      --ui-icon-width: 24px;
      --ui-icon-height: 24px;
      span {
        flex: 1;
      }
      button {
        flex-shrink: 0;
        padding: 7px 10px;
        border: none;
        border-radius: 12px;
        background-color: $soft-purple-100;
        color: $neutral-black;
        font-size: 12px;
        line-height: 16px;
        cursor: pointer;
        &:hover {
          background-color: $neutral-200;
        }
      }
      &--error {
        border-color: $red-200;
        background-color: $red-100;
        color: $red-700;
        button {
          background-color: $neutral-white;
          color: $red-700;
          &:hover {
            background-color: $red-200;
          }
        }
      }
    }
    .reply-bar,
    .image-preview {
      display: flex;
      flex: 0 0 auto;
      align-items: center;
      justify-content: space-between;
      margin: 0;
      padding: 8px 12px;
      gap: 12px;
      border-left: 4px solid $green-500;
      border-radius: 12px;
      background-color: $neutral-white;
      .chat-icon-button {
        width: 28px;
        height: 28px;
        border-radius: 12px;
        --ui-icon-width: 16px;
        --ui-icon-height: 16px;
      }
    }
    .reply-bar {
      .reply-bar-text {
        display: flex;
        flex-direction: column;
        min-width: 0;
        gap: 4px;
        .reply-bar-label {
          color: $green-700;
          font-size: 12px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .reply-bar-snippet {
          color: $neutral-600;
          font-size: 13px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }
    .image-preview {
      border-left-color: $neutral-200;
      .image-preview-div {
        display: flex;
        align-items: center;
        min-width: 0;
        gap: 10px;
        img {
          flex-shrink: 0;
          width: 44px;
          height: 44px;
          border-radius: 12px;
          object-fit: cover;
        }
        .image-preview-meta {
          display: flex;
          flex-direction: column;
          min-width: 0;
          gap: 4px;
          span {
            color: $neutral-black;
            font-size: 13px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          small {
            color: $neutral-500;
            font-size: 12px;
            line-height: 16px;
          }
        }
      }
    }
    .composer-shell {
      display: flex;
      position: absolute;
      flex-direction: column;
      box-sizing: border-box;
      width: 100%;
      bottom: 0;
      left: 0;
      padding: 16px 22px;
      gap: 8px;
      background: linear-gradient(360deg, #00000033, #00000000);
      z-index: 3;
      .composer-box {
        border: 1px solid $neutral-200;
        border-radius: 24px;
        background-color: $neutral-white;
        transition: border-color 0.25s ease-in-out;
        &:focus-within:not(.composer-box--disabled) {
          border-color: $green-500;
        }
        &--drag-active {
          border-color: $green-500;
          background-color: rgba($green-500, 0.1);
          box-shadow: inset 0 0 0 2px $green-500;
        }
        .composer-input-wrap {
          position: relative;
          border-radius: 24px 24px 0 0;
          .composer-input,
          .composer-highlight-content {
            box-sizing: border-box;
            width: 100%;
            margin: 0;
            padding: 12px 14px;
            border: none;
            color: $neutral-900;
            font-family: Hauora-Regular;
            font-size: 16px;
            line-height: 22px;
            letter-spacing: normal;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
          }
          .composer-highlight-overlay {
            position: absolute;
            inset: 0;
            overflow: auto;
            scrollbar-width: none;
            pointer-events: none;
            .composer-highlight-content {
              min-height: 100%;
              .composer-mention {
                font-family: inherit;
                font-weight: inherit;
              }
            }
          }
          .composer-input {
            display: block;
            position: relative;
            height: 68px;
            border-radius: inherit;
            background: none;
            caret-color: $neutral-black;
            outline: none;
            resize: none;
            overflow: auto;
            scrollbar-width: none;
            z-index: 1;
            &--mirrored {
              color: transparent;
            }
            &::placeholder {
              color: $neutral-500;
            }
            &::selection {
              background-color: rgba($green-500, 0.25);
              color: transparent;
            }
            &:disabled {
              cursor: not-allowed;
            }
          }
          .mention-suggestions {
            display: flex;
            position: absolute;
            flex-direction: column;
            box-sizing: border-box;
            left: -1px;
            right: -1px;
            bottom: calc(100% + 8px);
            max-height: 230px;
            padding: 8px;
            gap: 4px;
            border: 1px solid $neutral-200;
            border-radius: 16px;
            background-color: $neutral-white;
            box-shadow: 0 8px 24px rgba($neutral-black, 0.16);
            overflow: auto;
            scrollbar-width: thin;
            scrollbar-color: $neutral-200 transparent;
            z-index: 15;
            .mention-suggestions-state {
              margin: 0;
              padding: 10px;
              color: $neutral-500;
              font-size: 13px;
            }
            .mention-suggestion {
              display: flex;
              flex-shrink: 0;
              align-items: center;
              min-width: 0;
              padding: 8px 10px;
              gap: 10px;
              border: none;
              border-radius: 12px;
              background: none;
              color: $neutral-900;
              text-align: left;
              cursor: pointer;
              &--active,
              &:hover {
                background-color: $green-100;
                color: $green-700;
              }
              .mention-suggestion-avatar {
                flex-shrink: 0;
                width: 28px;
                height: 28px;
                border-radius: 50%;
                object-fit: cover;
              }
              .mention-suggestion-name {
                min-width: 0;
                font-size: 14px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
              }
            }
          }
        }
        .composer-toolbar {
          display: flex;
          align-items: center;
          padding: 0 10px 10px;
          gap: 10px;
          .composer-tools {
            display: flex;
            align-items: center;
            gap: 4px;
            .tool-button {
              display: flex;
              position: relative;
              align-items: center;
              justify-content: center;
              width: 36px;
              height: 36px;
              padding: 0;
              border: none;
              border-radius: 12px;
              background: none;
              color: $neutral-500;
              cursor: pointer;
              --ui-icon-width: 24px;
              --ui-icon-height: 24px;
              &:hover:not(:disabled):not(.tool-button--disabled),
              &[aria-expanded="true"] {
                color: $green-700;
              }
              &:focus-within {
                outline: 2px solid $green-500;
              }
              &--disabled,
              &:disabled {
                opacity: 0.4;
                cursor: not-allowed;
              }
              input {
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                opacity: 0;
                cursor: inherit;
              }
            }
          }
          .composer-counter {
            margin-left: auto;
            color: $neutral-500;
            font-size: 11px;
            line-height: 16px;
            &--limit {
              color: $yellow-700;
            }
          }
          .send-button {
            display: flex;
            flex-shrink: 0;
            align-items: center;
            justify-content: center;
            width: 36px;
            height: 36px;
            padding: 0;
            border: none;
            border-radius: 12px;
            background-color: $green-500;
            color: $neutral-black;
            cursor: pointer;
            --ui-icon-width: 20px;
            --ui-icon-height: 20px;
            &:hover:not(:disabled) {
              background-color: $green-400;
            }
            &:disabled {
              background-color: $neutral-200;
              color: $neutral-400;
            }
            .sending-spinner {
              width: 16px;
              height: 16px;
              border: 2px solid $neutral-white;
              border-top-color: $green-700;
              border-radius: 50%;
              animation: chat-spin 0.8s linear infinite;
            }
          }
        }
      }
      .emoji-picker--composer {
        display: flex;
        flex-direction: column;
        right: 16px;
        bottom: calc(100% - 8px);
        width: 336px;
        max-height: var(--chat-composer-picker-max-height, 276px);
        overflow: hidden;
        .emoji-grid--composer {
          display: grid;
          grid-template-columns: repeat(8, 34px);
          min-height: 0;
          gap: 4px;
          overflow-y: auto;
          overscroll-behavior: contain;
          scrollbar-width: none;
          &::-webkit-scrollbar {
            display: none;
            width: 0;
            height: 0;
          }
        }
      }
    }
  }
  .deleted-preview-overlay,
  .image-lightbox-overlay {
    display: flex;
    position: fixed;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    inset: 0;
    padding: 40px;
    background-color: rgba($neutral-black, 0.65);
    backdrop-filter: blur(12px);
  }
  .deleted-preview-overlay {
    background-color: rgba($neutral-800, 0.2);
    z-index: 120;
    .deleted-preview-modal {
      display: flex;
      flex-direction: column;
      box-sizing: border-box;
      width: 600px;
      max-height: 80%;
      padding: 16px 24px;
      gap: 12px;
      border: 1px solid $neutral-200;
      border-radius: 24px;
      background-color: $neutral-100;
      box-shadow: 0 2px 16px rgba($neutral-black, 0.2);
      .deleted-preview-header {
        display: flex;
        flex-shrink: 0;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        .deleted-preview-header-main {
          display: flex;
          flex-direction: column;
          gap: 8px;
          span {
            color: $neutral-black;
            font-family: Involve-Medium;
            font-size: 24px;
            line-height: 26px;
            letter-spacing: -0.48px;
          }
          small {
            color: $neutral-500;
            font-size: 12px;
            line-height: 16px;
          }
        }
      }
      .deleted-preview-body {
        display: flex;
        flex-direction: column;
        min-height: 0;
        padding: 12px 16px;
        gap: 12px;
        border-radius: 24px;
        background-color: $neutral-white;
        overflow: auto;
        scrollbar-width: thin;
        scrollbar-color: $neutral-200 transparent;
        .deleted-preview-author {
          display: flex;
          align-items: center;
          min-width: 0;
          gap: 8px;
          .deleted-preview-avatar {
            flex-shrink: 0;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            object-fit: cover;
          }
          span {
            color: $neutral-black;
            font-family: Hauora-SemiBold;
            font-size: 16px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }
        .deleted-preview-text,
        .deleted-preview-empty {
          margin: 0;
          color: $neutral-900;
          font-size: 16px;
          line-height: 22px;
          user-select: text;
          white-space: pre-wrap;
          overflow-wrap: anywhere;
        }
        .deleted-preview-empty {
          color: $neutral-500;
        }
        .deleted-preview-image {
          width: 100%;
          max-height: 360px;
          border-radius: 12px;
          object-fit: contain;
          cursor: zoom-in;
        }
      }
    }
  }
  .image-lightbox-overlay {
    z-index: 130;
    .image-lightbox-close {
      display: flex;
      position: absolute;
      align-items: center;
      justify-content: center;
      top: 24px;
      right: 24px;
      width: 40px;
      height: 40px;
      padding: 0;
      border: 1px solid $soft-purple-100;
      border-radius: 12px;
      background-color: $neutral-white;
      color: $neutral-black;
      cursor: pointer;
      &:hover {
        background-color: $soft-purple-100;
        color: $green-700;
      }
    }
    .image-lightbox-image {
      max-width: min(90%, 1440px);
      max-height: 90%;
      border-radius: 16px;
      object-fit: contain;
      box-shadow: 0 16px 56px rgba($neutral-black, 0.4);
    }
  }
}

.global-chat-panel-transition-enter-active,
.global-chat-panel-transition-leave-active,
.deleted-preview-modal-enter-active,
.deleted-preview-modal-leave-active,
.image-lightbox-transition-enter-active,
.image-lightbox-transition-leave-active,
.emoji-picker-pop-enter-active,
.emoji-picker-pop-leave-active {
  transition: opacity 0.25s ease-in-out, transform 0.25s ease-in-out;
}
.global-chat-panel-transition-enter-from,
.global-chat-panel-transition-leave-to,
.deleted-preview-modal-enter-from,
.deleted-preview-modal-leave-to,
.image-lightbox-transition-enter-from,
.image-lightbox-transition-leave-to,
.emoji-picker-pop-enter-from,
.emoji-picker-pop-leave-to {
  opacity: 0;
}
.global-chat-panel-transition-enter-from,
.global-chat-panel-transition-leave-to,
.emoji-picker-pop-enter-from,
.emoji-picker-pop-leave-to {
  transform: translateY(10px);
}
@keyframes chat-spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes chat-image-shimmer {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(100%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .global-chat-dock .sending-spinner {
    animation: none;
  }
  .global-chat-dock .message-image-shell {
    .message-image-placeholder,
    .message-image-error,
    .message-image {
      transition: none;
    }
    .message-image-placeholder::after {
      animation: none;
    }
  }
}
</style>
