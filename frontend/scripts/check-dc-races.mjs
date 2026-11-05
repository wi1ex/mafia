// Run from frontend with node scripts/check-dc-races.mjs.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
import { ref, computed, reactive, watch } from 'vue'

function moduleFrom(path, dependencies = {}) {
  const source = fs.readFileSync(path, 'utf8').replace(/^import .*\r?\n/gm, '')
  const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText
  const exports = {}
  const bindings = { defineStore: (_name, setup) => setup, ref, computed, watch, ...dependencies }
  new Function('exports', ...Object.keys(bindings), code)(exports, ...Object.values(bindings))
  return exports
}
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const response = data => ({ data })
const auth = reactive({ sessionId: 'session-a' })
const listeners = new Map()
const timers = new Map()
let timerId = 0
globalThis.window = {
  setInterval: () => ++timerId, clearInterval() {},
  setTimeout(fn) { const id = ++timerId; timers.set(id, fn); return id },
  clearTimeout(id) { timers.delete(id) },
  addEventListener(name, fn) { listeners.set(name, fn) },
  removeEventListener(name) { listeners.delete(name) },
}
const storage = new Map()
globalThis.sessionStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }

try {
  const gets = []
  const user = moduleFrom('src/store/modules/user.ts', {
    api: { get() { const next = deferred(); gets.push(next); return next.promise } },
    useSettingsStore: () => ({ verificationRestrictions: true }), useAuthStore: () => auth,
  }).useUserStore()
  const profile = (id, dc_balance, extra = {}) => ({ id, role: 'user', dc_balance, subscription_until: null, ...extra })
  user.applyProfile(profile(17, 30))
  let request = user.fetchMe()
  user.clear(); auth.sessionId = 'session-b'; user.applyProfile(profile(18, 100))
  gets.shift().resolve(response(profile(17, 30))); await request
  assert.equal(user.user.value.id, 18)
  auth.sessionId = 'session-c'; user.applyProfile(profile(17, 30))
  request = user.fetchMe()
  user.setWalletState({ dc_balance: 3, subscription_until: '2027-01-01T23:00:00Z' })
  gets.shift().resolve(response(profile(17, 30))); await request
  assert.equal(user.user.value.dc_balance, 3)
  assert.equal(user.user.value.subscription_until, '2027-01-01T23:00:00Z')
  request = user.fetchMe(); user.setUsername('new-name')
  gets.shift().resolve(response(profile(17, 3, { username: 'old-name' }))); await request
  assert.equal(user.user.value.username, 'new-name')
  const older = user.fetchMe(), newer = user.fetchMe()
  const first = gets.shift(), last = gets.shift()
  last.resolve(response(profile(17, 40))); await newer
  first.resolve(response(profile(17, 20))); await older
  assert.equal(user.user.value.dc_balance, 40)
  console.log('PASS user: account/session ownership, newer wallet/local mutations, latest invocation')

  const invoiceGets = [], posts = []
  const actor = reactive({ user: profile(17, 0), setWalletState(state) { Object.assign(this.user, state) } })
  const dc = moduleFrom('src/services/dc.ts')
  const wallet = moduleFrom('src/store/modules/wallet.ts', {
    ...dc, useUserStore: () => actor, useAuthStore: () => auth,
    api: {
      get(url) { if (url === '/payments/wallet') return Promise.resolve(response({ dc_balance: actor.user.dc_balance, subscription_until: actor.user.subscription_until, subscription_active: false })); const next = deferred(); invoiceGets.push(next); return next.promise },
      post() { const next = deferred(); posts.push(next); return next.promise },
    },
  }).useWalletStore()
  const invoice = (order_id, status, request_id = undefined) => ({ order_id, status, quantity: 30, unit_price: null, amount: '500.00', currency: 'RUB', dc_balance: 0, request_id })
  let list = wallet.loadInvoices()
  const check = wallet.checkInvoice(1)
  posts.shift().resolve(response(invoice(1, 'processed'))); await check
  invoiceGets.shift().resolve(response({ items: [invoice(1, 'pending')] })); await list
  assert.equal(wallet.invoices.value[0].status, 'processed')
  const olderList = wallet.loadInvoices(), newerList = wallet.loadInvoices()
  const oldPage = invoiceGets.shift(), newPage = invoiceGets.shift()
  newPage.resolve(response({ items: [invoice(1, 'processed')] })); await newerList
  oldPage.resolve(response({ items: [invoice(1, 'pending')] })); await olderList
  assert.equal(wallet.invoices.value[0].status, 'processed')
  const oldCreate = wallet.createInvoice({ quantity: 30, currency: 'RUB', email: 'a@example.org', expected_amount: '500.00' })
  const oldPost = posts.shift()
  auth.sessionId = 'new-session-same-user'; wallet.ensureOwner()
  const newCreate = wallet.createInvoice({ quantity: 100, currency: 'RUB', email: 'a@example.org', expected_amount: '1500.00' })
  const newPost = posts.shift(), newRequestId = wallet.pending.value.invoice.request_id
  oldPost.resolve(response(invoice(2, 'pending'))); await oldCreate
  assert.equal(wallet.invoiceBusy.value, true)
  assert.equal(wallet.pending.value.invoice.request_id, newRequestId)
  assert.equal(wallet.invoices.value.length, 0)
  newPost.resolve(response(invoice(3, 'pending', newRequestId))); await newCreate
  assert.equal(wallet.invoiceBusy.value, false)
  assert.equal(wallet.pending.value.invoice, undefined)
  assert.equal(wallet.invoices.value[0].order_id, 3)
  console.log('PASS wallet: stale pending list after processed check, latest list, same-user reauthentication')

  const notifGets = []
  const notifs = moduleFrom('src/store/modules/notif.ts', {
    useAuthStore: () => auth,
    api: { get(url, options) { const next = deferred(); notifGets.push({ ...next, options }); return next.promise }, post: () => Promise.resolve({}) },
  }).useNotifStore()
  const notes = (from, to) => Array.from({ length: from - to + 1 }, (_, i) => ({ id: from - i, title: 'Notice', date: '', read: false }))
  async function page(run, from, to, more, cursor) {
    const promise = run()
    const request = notifGets.shift()
    request.resolve(response({ items: notes(from, to), unread_count: from, has_more: more, next_before_id: cursor }))
    await promise
    return request.options.params
  }
  await page(() => notifs.fetchAll(), 200, 151, true, 151)
  await page(() => notifs.loadMore(), 150, 101, true, 101)
  await page(() => notifs.fetchAll(), 201, 152, true, 152)
  assert.equal(notifs.items.value.length, 101)
  let params = await page(() => notifs.loadMore(), 100, 51, true, 51)
  assert.equal(params.before_id, 101)
  await page(() => notifs.loadMore(), 50, 1, false, null)
  await page(() => notifs.fetchAll(), 202, 153, true, 153)
  assert.equal(notifs.hasMore.value, false)
  assert.equal(notifs.items.value.length, 202)
  await page(() => notifs.fetchAll(), 400, 351, true, 351)
  await page(() => notifs.loadMore(), 350, 301, true, 301)
  await page(() => notifs.loadMore(), 300, 251, true, 251)
  await page(() => notifs.loadMore(), 250, 201, true, 201)
  const skip = notifs.loadMore()
  let duplicates = notifGets.shift()
  assert.equal(duplicates.options.params.before_id, 201)
  duplicates.resolve(response({ items: notes(200, 151), unread_count: 400, has_more: true, next_before_id: 151 }))
  await Promise.resolve(); await Promise.resolve()
  duplicates = notifGets.shift()
  assert.equal(duplicates.options.params.before_id, 151)
  duplicates.resolve(response({ items: notes(150, 101), unread_count: 400, has_more: true, next_before_id: 101 }))
  await Promise.resolve(); await Promise.resolve()
  duplicates = notifGets.shift()
  assert.equal(duplicates.options.params.before_id, 101)
  duplicates.resolve(response({ items: notes(100, 51), unread_count: 400, has_more: true, next_before_id: 51 }))
  await Promise.resolve(); await Promise.resolve()
  duplicates = notifGets.shift()
  assert.equal(duplicates.options.params.before_id, 51)
  duplicates.resolve(response({ items: notes(50, 1), unread_count: 400, has_more: false, next_before_id: null }))
  await skip
  assert.equal(notifs.items.value.length, 400)
  assert.equal(notifs.hasMore.value, false)
  console.log('PASS notifications: head refresh retains deep cursor/exhaustion; reconnect gap and duplicate pages reach end')
} catch (error) {
  console.error(error.name + ': ' + error.message)
  console.error(error.stack?.split('\n').slice(1, 3).join('\n'))
  process.exitCode = 1
}
