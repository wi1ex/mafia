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
const deferred = () => { let resolve, reject; const promise = new Promise((done, fail) => { resolve = done; reject = fail }); return { promise, resolve, reject } }
const response = data => ({ data })
const auth = reactive({ sessionId: 'session-a' })
const listeners = new Map()
const timers = new Map()
const events = []
let timerId = 0
globalThis.window = {
  setInterval: () => ++timerId, clearInterval() {},
  setTimeout(fn) { const id = ++timerId; timers.set(id, fn); return id },
  clearTimeout(id) { timers.delete(id) },
  addEventListener(name, fn) { listeners.set(name, fn) },
  removeEventListener(name) { listeners.delete(name) },
  dispatchEvent(event) { events.push(event); return true },
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

  const walletGets = [], posts = []
  const actor = reactive({ user: profile(17, 0), setWalletState(state) { Object.assign(this.user, state) } })
  const dc = moduleFrom('src/services/dc.ts')
  const wallet = moduleFrom('src/store/modules/wallet.ts', {
    ...dc, useUserStore: () => actor, useAuthStore: () => auth,
    api: {
      get(url) { assert.equal(url, '/payments/wallet'); const next = deferred(); walletGets.push(next); return next.promise },
      post(url, input) { const next = deferred(); posts.push({ ...next, url, input: JSON.parse(JSON.stringify(input)) }); return next.promise },
    },
  }).useWalletStore()
  const invoice = (order_id, status, request_id = undefined) => ({ order_id, status, quantity: 30, unit_price: null, amount: '500.00', currency: 'RUB', dc_balance: 0, request_id })
  const firstInput = { quantity: 30, currency: 'RUB', payment_method: 'sbp', email: 'a@example.org', expected_amount: '500.00' }
  const nextInput = { quantity: 100, currency: 'USD', payment_method: 'paypal', email: 'b@example.org', expected_amount: '21.00' }
  storage.set('dc:requests:v2:17', JSON.stringify({ invoice: { ...firstInput, request_id: dc.newDcRequestId() } }))
  let creation = wallet.createInvoice(firstInput)
  let created = posts.shift()
  assert.equal(created.url, '/payments/coins/invoices')
  const firstRequestId = created.input.request_id
  assert.deepEqual(created.input, { ...firstInput, request_id: firstRequestId })
  assert.match(firstRequestId, /^[a-f0-9-]{36}$/i)
  await assert.rejects(wallet.createInvoice(nextInput), /operation_busy/)
  assert.equal(posts.length, 0)
  created.resolve(response(invoice(1, 'pending', firstRequestId))); await creation
  creation = wallet.createInvoice(nextInput)
  created = posts.shift()
  const nextRequestId = created.input.request_id
  assert.notEqual(nextRequestId, firstRequestId)
  assert.deepEqual(created.input, { ...nextInput, request_id: nextRequestId })
  created.reject(new Error('connection lost'))
  await assert.rejects(creation, /connection lost/)
  creation = wallet.createInvoice(nextInput)
  created = posts.shift()
  assert.notEqual(created.input.request_id, nextRequestId)
  assert.deepEqual(created.input, { ...nextInput, request_id: created.input.request_id })
  created.resolve(response(invoice(2, 'pending', created.input.request_id))); await creation
  assert.equal(wallet.invoiceBusy.value, false)
  console.log('PASS wallet invoices: fresh UUID and current input on each click, busy guard, no replay after uncertain failure or old stored invoice')

  const oldCreate = wallet.createInvoice(firstInput)
  const oldPost = posts.shift()
  auth.sessionId = 'new-session-same-user'; wallet.ensureOwner()
  const newCreate = wallet.createInvoice(nextInput)
  const newPost = posts.shift()
  oldPost.resolve(response(invoice(3, 'processed'))); await oldCreate
  assert.equal(wallet.invoiceBusy.value, true)
  assert.equal(walletGets.length, 0)
  assert.equal(actor.user.dc_balance, 0)
  newPost.resolve(response(invoice(4, 'pending', newPost.input.request_id))); await newCreate
  assert.equal(wallet.invoiceBusy.value, false)

  creation = wallet.createInvoice(firstInput)
  posts.shift().resolve(response({ ...invoice(5, 'processed'), dc_balance: 999 })); await creation
  assert.equal(walletGets.length, 1)
  assert.equal(actor.user.dc_balance, 0)
  actor.setWalletState({ dc_balance: 70, subscription_until: '2027-01-01T23:00:00Z' })
  walletGets.shift().resolve(response({ dc_balance: 30, subscription_until: null, subscription_active: false }))
  await Promise.resolve(); await Promise.resolve()
  assert.equal(actor.user.dc_balance, 70)
  assert.equal(actor.user.subscription_until, '2027-01-01T23:00:00Z')
  console.log('PASS wallet invoices: same-user reauthentication isolates busy/refresh; processed invoice refresh cannot overwrite newer wallet state')

  const oldRefresh = wallet.refreshWallet(), newRefresh = wallet.refreshWallet()
  const oldWallet = walletGets.shift(), newWallet = walletGets.shift()
  newWallet.resolve(response({ dc_balance: 80, subscription_until: null, subscription_active: false })); await newRefresh
  oldWallet.resolve(response({ dc_balance: 20, subscription_until: null, subscription_active: false })); await oldRefresh
  assert.equal(actor.user.dc_balance, 80)
  const previousSessionRefresh = wallet.refreshWallet()
  const previousSessionWallet = walletGets.shift()
  auth.sessionId = 'another-session-same-user'; wallet.ensureOwner()
  const currentSessionRefresh = wallet.refreshWallet()
  previousSessionWallet.resolve(response({ dc_balance: 10, subscription_until: null, subscription_active: false })); await previousSessionRefresh
  assert.equal(wallet.loading.value, true)
  assert.equal(actor.user.dc_balance, 80)
  walletGets.shift().resolve(response({ dc_balance: 90, subscription_until: null, subscription_active: false })); await currentSessionRefresh
  assert.equal(wallet.loading.value, false)
  const previousAccountRefresh = wallet.refreshWallet()
  actor.user = profile(18, 400); auth.sessionId = 'different-account'; wallet.ensureOwner()
  walletGets.shift().resolve(response({ dc_balance: 5, subscription_until: null, subscription_active: false })); await previousAccountRefresh
  assert.equal(actor.user.dc_balance, 400)
  console.log('PASS wallet refresh: latest invocation wins; old session/account cannot replace wallet state or clear current loading')

  const storedRequestsKey = 'dc:requests:v2:17'
  const storedSubscriptionId = dc.newDcRequestId()
  const storedGiftId = dc.newDcRequestId()
  storage.set(storedRequestsKey, JSON.stringify({
    subscription: { plan: 'year', request_id: storedSubscriptionId, recipient_id: 20 },
    gift: { gift_id: 4, expected_dc_cost: 50, request_id: storedGiftId },
  }))
  actor.user = profile(17, 100); auth.sessionId = 'subscription-session'; wallet.ensureOwner()
  assert.equal(posts.length, 0)
  let purchase = wallet.buySubscription('week')
  const uncertainPurchase = posts.shift()
  assert.equal(uncertainPurchase.url, '/payments/subscriptions')
  assert.deepEqual(uncertainPurchase.input, { plan: 'week', request_id: uncertainPurchase.input.request_id })
  assert.notEqual(uncertainPurchase.input.request_id, storedSubscriptionId)
  await assert.rejects(wallet.buySubscription('month'), /operation_busy/)
  uncertainPurchase.reject(new Error('connection lost'))
  await assert.rejects(purchase, /connection lost/)
  assert.equal(posts.length, 0)
  assert.equal(wallet.subscriptionBusy.value, false)
  purchase = wallet.buySubscription('month', 18)
  const nextPurchase = posts.shift()
  assert.deepEqual(nextPurchase.input, { plan: 'month', request_id: nextPurchase.input.request_id, recipient_id: 18 })
  assert.notEqual(nextPurchase.input.request_id, uncertainPurchase.input.request_id)
  actor.setWalletState({ dc_balance: 150 })
  nextPurchase.resolve(response({ purchase_id: 1, recipient_id: 18, dc_balance: 73, subscription_until: '2027-01-01T23:00:00Z', subscription_active: true })); await purchase
  assert.equal(actor.user.dc_balance, 150)
  assert.equal(actor.user.subscription_until, null)
  walletGets.shift().resolve(response({ dc_balance: 150, subscription_until: '2027-02-01T23:00:00Z', subscription_active: true }))
  await Promise.resolve(); await Promise.resolve()
  assert.equal(actor.user.subscription_until, '2027-02-01T23:00:00Z')

  const oldPurchase = wallet.buySubscription('month')
  const oldPurchasePost = posts.shift()
  auth.sessionId = 'subscription-reauthenticated'; wallet.ensureOwner()
  const currentPurchase = wallet.buySubscription('month')
  const currentPurchasePost = posts.shift()
  assert.notEqual(currentPurchasePost.input.request_id, oldPurchasePost.input.request_id)
  oldPurchasePost.resolve(response({ purchase_id: 2, dc_balance: 123, subscription_until: '2027-03-01T23:00:00Z', subscription_active: true })); await oldPurchase
  assert.equal(wallet.subscriptionBusy.value, true)
  assert.equal(walletGets.length, 0)
  currentPurchasePost.resolve(response({ purchase_id: 3, dc_balance: 96, subscription_until: '2027-04-01T23:00:00Z', subscription_active: true })); await currentPurchase
  assert.equal(wallet.subscriptionBusy.value, false)
  assert.equal(actor.user.dc_balance, 96)
  walletGets.shift().resolve(response({ dc_balance: 96, subscription_until: '2027-04-01T23:00:00Z', subscription_active: true }))
  await Promise.resolve(); await Promise.resolve()
  assert.equal(actor.user.subscription_until, '2027-04-01T23:00:00Z')
  assert.equal(events.filter(event => event.type === 'dc-wallet-changed').length, 2)
  console.log('PASS wallet subscriptions: fresh UUID and current input after uncertain failure; stale receipt and session guards')

  const uncertainGift = wallet.buyGift({ gift_id: 1, expected_dc_cost: 10 })
  const uncertainGiftPost = posts.shift()
  assert.equal(uncertainGiftPost.url, '/gifts/purchases')
  assert.notEqual(uncertainGiftPost.input.request_id, storedGiftId)
  uncertainGiftPost.reject(new Error('connection lost'))
  await assert.rejects(uncertainGift, /connection lost/)
  assert.equal(posts.length, 0)
  assert.equal(wallet.giftBusy.value, false)
  const giftInput = { gift_id: 2, expected_dc_cost: 25, recipient_id: 18, anonymous: true }
  const giftPurchase = wallet.buyGift(giftInput)
  const giftPurchasePost = posts.shift()
  assert.deepEqual(giftPurchasePost.input, { ...giftInput, request_id: giftPurchasePost.input.request_id })
  assert.notEqual(giftPurchasePost.input.request_id, uncertainGiftPost.input.request_id)
  giftPurchasePost.resolve(response({ dc_balance: 71, recipient_id: 18 })); await giftPurchase
  assert.equal(actor.user.dc_balance, 71)
  walletGets.shift().resolve(response({ dc_balance: 71, subscription_until: '2027-04-01T23:00:00Z', subscription_active: true }))
  await Promise.resolve(); await Promise.resolve()
  assert.equal(JSON.parse(storage.get(storedRequestsKey)).subscription.request_id, storedSubscriptionId)
  assert.equal(JSON.parse(storage.get(storedRequestsKey)).gift.request_id, storedGiftId)
  console.log('PASS wallet gifts: uncertain failure leaves no replay, next purchase uses a fresh UUID and current recipient')

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
