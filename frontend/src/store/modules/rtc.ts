import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { api } from '@/services/axios'
import { useAuthStore } from '@/store/modules/auth'

export type StateBool = 0 | 1
export interface UserState { mic: StateBool; cam: StateBool; speakers: StateBool; visibility: StateBool }

function to01(v: unknown, d: StateBool = 1 as StateBool): StateBool {
  if (typeof v === 'boolean') return (v ? 1 : 0) as StateBool
  if (v === '1' || v === 1) return 1
  if (v === '0' || v === 0) return 0
  return d
}

export const useRtcStore = defineStore('rtc', () => {
  const auth = useAuthStore()

  const roomId = ref<number | null>(null)
  const localId = ref<string>('')

  const statusMap = reactive<Record<string, UserState>>({})

  const micOn = ref(true)
  const camOn = ref(true)
  const speakersOn = ref(true)
  const visibilityOn = ref(true)

  const ws = ref<WebSocket | null>(null)
  let wsSeq = 0
  let reconnectT = 0

  let hbTimer: number | null = null

  function setLocalFromPref(pref: Record<string, string>) {
    micOn.value = to01(pref.mic, 1) === 1
    camOn.value = to01(pref.cam, 1) === 1
    speakersOn.value = to01(pref.speakers, 1) === 1
    visibilityOn.value = to01(pref.visibility, 1) === 1
  }

  async function httpPublishState() {
    if (!roomId.value) return
    const payload = { mic: micOn.value, cam: camOn.value, speakers: speakersOn.value, visibility: visibilityOn.value }
    await api.post(`/rooms/${roomId.value}/state`, payload)
  }
  async function httpHeartbeat() {
    if (!roomId.value) return
    await api.post(`/rooms/${roomId.value}/heartbeat`, {})
  }
  async function httpLeave(final?: Partial<UserState>) {
    if (!roomId.value) return
    const tok = auth.accessToken
    const url = `/api/rooms/${roomId.value}/leave`
    const body = final
      ? JSON.stringify({ mic: final.mic === 1, cam: final.cam === 1, speakers: final.speakers === 1, visibility: final.visibility === 1 })
      : '{}'
    try {
      await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(tok ? { Authorization: `Bearer ${tok}` } : {}) }, body, keepalive: true })
    } catch {}
  }

  function startHeartbeat() {
    stopHeartbeat()
    hbTimer = window.setInterval(() => { httpHeartbeat().catch(() => {}) }, 15000)
  }
  function stopHeartbeat() {
    if (hbTimer) {
      window.clearInterval(hbTimer)
      hbTimer = null
    }
  }

  function applySnapshot(snap: Record<string, Record<string, string>>) {
    Object.keys(statusMap).forEach(k => delete statusMap[k])
    for (const [uid, st] of Object.entries(snap || {})) {
      statusMap[uid] = {
        mic: to01(st.mic, 1), cam: to01(st.cam, 1), speakers: to01(st.speakers, 1), visibility: to01(st.visibility, 1),
      }
    }
  }

  function connectWS(wsUrl: string) {
    if (ws.value) { try { ws.value.close() } catch {} ws.value = null }

    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => { reconnectT = 0 }

    ws.value.onmessage = (ev) => {
      let msg: any
      try { msg = JSON.parse(ev.data) } catch { return }
      const t = msg?.type
      const p = msg?.payload || {}
      if (t === 'snapshot') {
        applySnapshot(p as Record<string, Record<string, string>>)
        return
      }
      if (t === 'state_changed') {
        const uid = String(p.user_id)
        const cur = statusMap[uid] || { mic: 1, cam: 1, speakers: 1, visibility: 1 }
        statusMap[uid] = {
          mic: to01(p.mic ?? cur.mic), cam: to01(p.cam ?? cur.cam),
          speakers: to01(p.speakers ?? cur.speakers), visibility: to01(p.visibility ?? cur.visibility),
        }
        return
      }
      if (t === 'member_left') {
        delete statusMap[String(p.user_id)]
        return
      }
      if (t === 'member_joined') {
        const uid = String(p.user_id)
        if (!statusMap[uid]) statusMap[uid] = { mic: 1, cam: 1, speakers: 1, visibility: 1 }
        return
      }
    }

    ws.value.onclose = () => {
      ws.value = null
      reconnectT = Math.min((reconnectT || 500) * 2, 5000)
      setTimeout(() => {
        if (!roomId.value) return
        connectWS(`wss://${location.host}/ws/room/${roomId.value}`)
        httpPublishState().catch(() => {})
      }, reconnectT || 500)
    }

    ws.value.onerror = () => {}
  }

  async function join(id: number): Promise<{ ws_url: string; token: string }> {
    const { data } = await api.post<{
      ws_url: string;
      token: string;
      room_id: number;
      state_ws: string;
      snapshot: Record<string, Record<string, string>>;
      self_pref: Record<string, string>
    }>(`/rooms/${id}/join`, {})
    roomId.value = id
    localId.value = String(auth.me?.id || '')
    setLocalFromPref(data.self_pref || {})
    applySnapshot(data.snapshot || {})
    await httpPublishState()
    connectWS(data.state_ws)
    startHeartbeat()
    return { ws_url: data.ws_url, token: data.token }
  }

  async function leave() {
    if (!roomId.value) return
    const final: UserState = {
      mic: micOn.value ? 1 : 0, cam: camOn.value ? 1 : 0, speakers: speakersOn.value ? 1 : 0, visibility: visibilityOn.value ? 1 : 0,
    }
    try { ws.value?.send(JSON.stringify({ type: 'goodbye', seq: ++wsSeq })) } catch {}
    await httpLeave(final)
    stopHeartbeat()
    if (ws.value) { try { ws.value.close() } catch {} ws.value = null }
    roomId.value = null
    Object.keys(statusMap).forEach(k => delete statusMap[k])
  }

  async function publishState() {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      await httpPublishState()
      return
    }
    const seq = ++wsSeq
    try {
      ws.value.send(JSON.stringify({
        type: 'state', seq,
        payload: { mic: micOn.value, cam: camOn.value, speakers: speakersOn.value, visibility: visibilityOn.value },
      }))
    } catch {
      await httpPublishState()
    }
  }

  async function toggleMic() {
    micOn.value = !micOn.value
    await publishState()
  }
  async function toggleCam() {
    camOn.value = !camOn.value
    await publishState()
  }
  async function toggleSpeakers() {
    speakersOn.value = !speakersOn.value
    await publishState()
  }
  async function toggleVisibility() {
    visibilityOn.value = !visibilityOn.value
    await publishState()
  }

  function installPageLeaveHandlers(router: any) {
    router.beforeEach(async (to: any, from: any) => {
      if (from.name === 'room' && to.name !== 'room') { try { await leave() } catch {} }
      return true
    })
    const onHide = () => {
      if (!roomId.value) return
      void httpLeave({
        mic: micOn.value ? 1 : 0, cam: camOn.value ? 1 : 0, speakers: speakersOn.value ? 1 : 0, visibility: visibilityOn.value ? 1 : 0,
      })
    }
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
    publishState,
    toggleMic,
    toggleCam,
    toggleSpeakers,
    toggleVisibility,
    installPageLeaveHandlers,
  }
})
