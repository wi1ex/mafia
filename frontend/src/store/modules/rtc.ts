import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { io, Socket } from 'socket.io-client'
import { api } from '@/services/axios'
import { useAuthStore } from '@/store/modules/auth'

export type State01 = 0 | 1
export interface UserState { mic: State01; cam: State01; speakers: State01; visibility: State01 }

function to01(v: unknown, d: State01 = 1 as State01): State01 {
  if (typeof v === 'boolean') return (v ? 1 : 0) as State01
  if (v === '1' || v === 1) return 1
  if (v === '0' || v === 0) return 0
  return d
}

export const useRtcStore = defineStore('rtc', () => {
  const auth = useAuthStore()

  const roomId = ref<number | null>(null)
  const localId = ref<string>('')  // string user id
  const socket = ref<Socket | null>(null)

  // authoritative badges
  const statusMap = reactive<Record<string, UserState>>({})

  // local toggles
  const micOn = ref(true)
  const camOn = ref(true)
  const speakersOn = ref(true)
  const visibilityOn = ref(true)

  function reset() {
    roomId.value = null
    Object.keys(statusMap).forEach(k => delete statusMap[k])
  }

  function connectSocket() {
    if (socket.value?.connected) return
    socket.value = io('/room', {
      path: '/ws/socket.io',
      transports: ['websocket'],
      auth: { token: auth.accessToken },
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
    })

    socket.value.on('connect', () => {
      if (roomId.value) socket.value?.emit('join', { room_id: roomId.value, state: curStatePayload() })
    })

    socket.value.on('connect_error', (e) => console.warn('rtc sio error', e?.message))

    socket.value.on('snapshot', (snap: Record<string, Record<string, string>>) => {
      Object.keys(statusMap).forEach(k => delete statusMap[k])
      for (const [uid, st] of Object.entries(snap || {})) {
        statusMap[uid] = {
          mic: to01(st.mic, 1), cam: to01(st.cam, 1), speakers: to01(st.speakers, 1), visibility: to01(st.visibility, 1)
        }
      }
    })

    socket.value.on('self_pref', (pref: Record<string, string>) => {
      micOn.value = to01(pref.mic, 1) === 1
      camOn.value = to01(pref.cam, 1) === 1
      speakersOn.value = to01(pref.speakers, 1) === 1
      visibilityOn.value = to01(pref.visibility, 1) === 1
    })

    socket.value.on('state_changed', (p: any) => {
      const uid = String(p.user_id)
      const cur = statusMap[uid] || { mic: 1, cam: 1, speakers: 1, visibility: 1 }
      statusMap[uid] = {
        mic: to01(p.mic ?? cur.mic), cam: to01(p.cam ?? cur.cam),
        speakers: to01(p.speakers ?? cur.speakers), visibility: to01(p.visibility ?? cur.visibility),
      }
    })

    socket.value.on('member_left', (p: any) => { delete statusMap[String(p.user_id)] })

    socket.value.on('member_joined', (p: any) => {
      const uid = String(p.user_id)
      const st = p.state || {}
      statusMap[uid] = {
        mic: to01(st.mic, 1), cam: to01(st.cam, 1),
        speakers: to01(st.speakers, 1), visibility: to01(st.visibility, 1),
      }
    })
  }

  function curStatePayload() {
    return { mic: micOn.value, cam: camOn.value, speakers: speakersOn.value, visibility: visibilityOn.value }
  }

async function join(id: number) {
  const { data } = await api.post<{
    token: string; room_id: number;
    snapshot: Record<string, Record<string, string>>;
    self_pref: Record<string, string>;
  }>(`/rooms/${id}/join`, {})

  Object.keys(statusMap).forEach(k => delete statusMap[k])
  for (const [uid, st] of Object.entries(data.snapshot || {})) {
    statusMap[uid] = {
      mic: to01(st.mic, 1), cam: to01(st.cam, 1),
      speakers: to01(st.speakers, 1), visibility: to01(st.visibility, 1),
    }
  }
  if (data.self_pref) {
    micOn.value        = to01(data.self_pref.mic, 1) === 1
    camOn.value        = to01(data.self_pref.cam, 1) === 1
    speakersOn.value   = to01(data.self_pref.speakers, 1) === 1
    visibilityOn.value = to01(data.self_pref.visibility, 1) === 1
  }

  localId.value = String(auth.me?.id || '')
  roomId.value  = id
  connectSocket()
  socket.value?.emit('join', { room_id: id, state: curStatePayload() })

  const ws_url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
  return { token: data.token, ws_url }
}

  async function leave() {
    if (!roomId.value) return
    try { socket.value?.emit('goodbye') } catch {}
    try { await api.post(`/rooms/${roomId.value}/leave`, {}, { keepalive: true as any }) } catch {}
    reset()
  }

  function emitWithAck(evt:string, payload:any, timeout=1500) {
    return new Promise<void>((resolve,reject)=>{
      let done=false
      const t=setTimeout(()=>{ if(!done){done=true; reject(new Error('ack timeout'))}}, timeout)
      socket.value?.emit(evt, payload, (_resp:any)=>{ if(!done){done=true; clearTimeout(t); resolve()} })
    })
  }
  async function publishState() {
    if (!roomId.value) return
    const payload = curStatePayload()
    try { await emitWithAck('state', payload) }
    catch { await api.post(`/rooms/${roomId.value}/state`, payload) }
  }

  async function setMic(next:boolean) {
    if (micOn.value!==next) {
      micOn.value=next
      await publishState()
    }
  }
  async function setCam(next:boolean) {
    if (camOn.value!==next) {
      camOn.value=next
      await publishState()
    }
  }
  async function setSpeakers(next:boolean) {
    if (speakersOn.value!==next) {
      speakersOn.value=next
      await publishState()
    }
  }
  async function setVisibility(next:boolean) {
    if (visibilityOn.value!==next) {
      visibilityOn.value=next
      await publishState()
    }
  }

  async function toggleMic() {
    await setMic(!micOn.value)
  }
  async function toggleCam() {
    await setCam(!camOn.value)
  }
  async function toggleSpeakers() {
    await setSpeakers(!speakersOn.value)
  }
  async function toggleVisibility() {
    await setVisibility(!visibilityOn.value)
  }

  function installPageLeaveHandlers(router: any) {
    router.beforeEach(async (to: any, from: any) => {
      if (from.name === 'room' && to.name !== 'room') { try { await leave() } catch {} }
      return true
    })
    const onHide = () => { if (roomId.value) { void api.post(`/rooms/${roomId.value}/leave`, {}, { keepalive: true as any }) } }
    window.addEventListener('pagehide', onHide)
    window.addEventListener('beforeunload', onHide)
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') onHide() })
  }

  return {
    roomId,
    localId,
    statusMap,
    micOn,
    camOn,
    speakersOn,
    visibilityOn,

    join,
    leave,
    setMic,
    setCam,
    setSpeakers,
    setVisibility,
    toggleMic,
    toggleCam,
    toggleSpeakers,
    toggleVisibility,
    installPageLeaveHandlers,
  }
})
