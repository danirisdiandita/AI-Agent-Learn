// Drives the Agents chat's tool approval card in Chrome over the DevTools protocol. Run it through
// scripts/e2e-dashboard.sh, which seeds the user's chats (scripts/e2e/seed-chats.py) and runs the backend with the
// scripted model (AGENTS_SCRIPTED_MODEL=1), so nothing reaches a model or Google.
//   node scripts/e2e/calendar.mjs <chrome-debug-port> <dashboard-url> <screenshot-dir> <email> <password>
// Set COLOR_SCHEME=light or COLOR_SCHEME=dark to emulate the OS theme, so the screenshots show that theme.
const [port, base, out, email, password] = process.argv.slice(2)
const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json()
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((r) => ws.addEventListener('open', r, { once: true }))
let id = 0
const pending = new Map()
ws.addEventListener('message', (e) => {
  const m = JSON.parse(e.data)
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
})
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const js = async (expr) => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); (await import('node:fs')).writeFileSync(`${out}/${name}.png`, Buffer.from(r.result.data, 'base64')) }
// Polls until an expression is truthy. The server's response time varies, so fixed sleeps race it.
const until = async (expr, ms = 10000) => {
  for (const end = Date.now() + ms; Date.now() < end; await sleep(50)) if (await js(expr)) return true
  return false
}
const go = async (url) => { await send('Page.navigate', { url }); await sleep(300); await until('document.querySelector("form, [data-slot=sidebar-wrapper]")') }
const reload = async () => { await send('Page.reload'); await sleep(300); await until('document.querySelector("[data-slot=sidebar-wrapper]")') }
const clickAt = async (expr) => {
  const at = await js(`(() => { const r = (${expr})?.getBoundingClientRect(); return r && { x: r.x + r.width / 2, y: r.y + r.height / 2 } })()`)
  if (!at) return false
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, ...at, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 0, y: 0 })
  return true
}
const desktop = () => send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false })
const phone = () => send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true })
const shotBoth = async (name) => {
  await shot(name)
  await phone(); await sleep(400)
  check(`${name}: no horizontal scroll at 390px`, !(await js('document.documentElement.scrollWidth > innerWidth')))
  await js(`document.querySelector('main [role=group]:last-of-type')?.scrollIntoView({ block: 'center' }), true`)
  await shot(`${name}-phone`)
  await desktop(); await sleep(400)
}
const cards = `[...document.querySelectorAll('main [role=group][aria-label="Create calendar event"]')]`
const card = (n) => `${cards}.at(${n})`
const cardText = (n) => js(`${card(n)}?.innerText.replace(/\\s+/g, ' ')`)
const cardButton = (n, label) => `[...(${card(n)}?.querySelectorAll('button') ?? [])].find((b) => b.textContent.trim() === ${JSON.stringify(label)})`
const composer = `document.querySelector('textarea[aria-label=Message]')`
const transcript = () => js(`document.querySelector('main ol')?.innerText ?? ''`)
const sendMessage = (text) => js(`(() => {
  const t = ${composer}
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(t, ${JSON.stringify(text)})
  t.dispatchEvent(new Event('input', { bubbles: true }))
  t.form.requestSubmit()
  return true
})()`)
const alertText = () => js(`document.querySelector('main ol [role=alert]')?.innerText.replace(/\\s+/g, ' ')`)
let failed = 0
const check = (label, cond, detail) => {
  if (!cond) failed++
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${cond || !detail ? '' : `  [${detail}]`}`)
}

await send('Page.enable'); await send('Runtime.enable')
if (process.env.COLOR_SCHEME) await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: process.env.COLOR_SCHEME }] })
// The browser's zone decides when the card names the event's zone, and the server reads it as the user's zone.
await send('Emulation.setTimezoneOverride', { timezoneId: 'Asia/Jakarta' })
await desktop()
await go(base)
await js(`localStorage.clear(), true`); await go(base)
await js(`(() => { const f = document.querySelector('form'); f.email.value = ${JSON.stringify(email)}; f.password.value = ${JSON.stringify(password)}; f.requestSubmit(); return true })()`)
await until(`location.pathname === '/agents' && document.querySelector('aside nav[aria-label=Chats] li a')`)
await clickAt(`document.querySelector('aside nav[aria-label=Chats] li a')`)
await until(`${cards}.length === 1`)

// The seeded chat ends with an event that waits for approval.
let t = await cardText(0)
check('the card names the event and its time in its own zone', t?.includes('Design review') && t.includes('Mon, Dec 7, 2026') && /3:00\s*–\s*3:45\sPM/.test(t) && t.includes('(Europe/Berlin)'), t)
check('the card shows the description and Approve and Decline', t?.includes('Walk through the new onboarding screens.') && (await js(`!!${cardButton(0, 'Approve')} && !!${cardButton(0, 'Decline')}`)), t)
const blocked = await js(`(() => { const c = ${composer}; return { disabled: c.disabled, placeholder: c.placeholder } })()`)
check('while the event waits, the composer is off and says why', blocked.disabled && blocked.placeholder === 'Approve or decline the event first', JSON.stringify(blocked))
await shotBoth('calendar-pending')

await clickAt(cardButton(0, 'Decline'))
await until(`${card(0)}?.innerText.includes('Declined') && document.querySelector('main ol').innerText.includes('Okay, I did not add it to your calendar.')`)
t = await cardText(0)
check('declining marks the card declined and the model follows up', t?.includes('Declined') && !(await js(`!!${cardButton(0, 'Approve')}`)) && (await transcript()).includes('Okay, I did not add it to your calendar.'), t)
check('after the decision the composer is on again', await js(`!${composer}.disabled`))
await shotBoth('calendar-declined')

await reload(); await until(`${cards}.length === 1`); await until(`document.querySelector('main ol').innerText.includes('Okay, I did not add it')`)
t = await cardText(0)
check('a reload shows the declined card and the follow-up from the saved rows', t?.includes('Declined') && (await transcript()).includes('Okay, I did not add it to your calendar.') && (await js(`!${composer}.disabled`)), t)

// The scripted model asks for an event, which arrives in the stream and waits like the saved one.
await sendMessage('Schedule a design review')
await until(`${cards}.length === 2 && !!${cardButton(-1, 'Approve')}`)
t = await cardText(-1)
check('a requested event streams in as a card in the browser zone, without a zone label', t?.includes('Tue, Dec 1, 2026') && /3:00\s*–\s*3:30\sPM/.test(t) && !t.includes('('), t)
check('the streamed card blocks the composer too', await js(`${composer}.disabled`))
await clickAt(cardButton(-1, 'Decline'))
// The send button stays off while the follow-up streams, so wait for it to be saved before sending again.
const replying = `[...document.querySelectorAll('main ol > li')].some((li) => li.innerText.startsWith('Replying'))`
await until(`${card(-1)}?.innerText.includes('Declined') && document.querySelector('main ol').innerText.split('Okay, I did not add it').length === 3 && !${replying}`)
check('the streamed card can be declined', (await cardText(-1))?.includes('Declined') && !(await js(`${composer}.disabled`)), await cardText(-1))

// A reply shows its words as they arrive, then is saved under the model's name.
const before = (await transcript()).length
await sendMessage('Hello')
await until(replying, 5000)
const partial = await js(`[...document.querySelectorAll('main ol > li')].find((li) => li.innerText.startsWith('Replying'))?.innerText.replace('Replying', '').trim()`)
const full = 'This reply comes from the scripted e2e model, word by word.'
await until(`document.querySelector('main ol').innerText.includes(${JSON.stringify(full)}) && !${replying}`)
check('a reply streams in before it is saved', !!partial && full.startsWith(partial) && partial.length < full.length, partial)
check('the finished reply is saved under the model id', /e2e\/scripted-model\s+This reply comes/.test((await transcript()).slice(before)), (await transcript()).slice(before))

// A reply that breaks off keeps the message and offers to try again, also after a reload.
await sendMessage('Fail this reply')
await until(`document.querySelector('main ol [role=alert]')`)
let alert = await alertText()
check('a reply that breaks off says why and offers to try again', alert?.includes('broke off on purpose') && alert.includes('Try again') && (await transcript()).includes('Fail this reply'), alert)
await reload(); await until(`document.querySelector('main ol [role=alert]')`)
alert = await alertText()
check('after a reload the unanswered message still offers to try again', alert?.includes('The reply stopped before it finished.'), alert)
await shot('calendar-retry')
await clickAt(`[...document.querySelectorAll('main ol [role=alert] button')].find((b) => b.textContent.trim() === 'Try again')`)
await until(`!document.querySelector('main ol [role=alert]') && document.querySelector('main ol').innerText.split(${JSON.stringify(full)}).length === 3`)
check('trying again streams the answer', !(await alertText()) && (await transcript()).split(full).length === 3, await transcript())


// A new chat moves to its own address once its first message is saved, and the reply keeps streaming there.
await clickAt(`[...document.querySelectorAll('aside nav[aria-label=Chats] a')].find((a) => a.textContent.trim() === 'New chat')`)
await until(`location.pathname === '/agents' && !!${composer}`)
await sendMessage('Hello from a new chat')
await until(`/^\\/agents\\/\\d+$/.test(location.pathname) && document.querySelector('main ol')?.innerText.includes(${JSON.stringify(full)}) && !${replying}`)
const titles = await js(`[...document.querySelectorAll('aside nav[aria-label=Chats] li a')].map((a) => a.querySelector('span').textContent)`)
check(
  'a new chat moves to its own address, and its reply streams there',
  /^\/agents\/\d+$/.test(await js('location.pathname')) && (await transcript()).includes('Hello from a new chat') && titles?.[0] === 'Hello from a new chat',
  `${await js('location.pathname')} ${JSON.stringify(titles)}`,
)

ws.close()
process.exit(failed ? 1 : 0)
