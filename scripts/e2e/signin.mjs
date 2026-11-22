// Drives the dashboard sign-in flow in Chrome over the DevTools protocol. Run it through scripts/e2e-dashboard.sh.
//   node scripts/e2e/signin.mjs <chrome-debug-port> <dashboard-url> <screenshot-dir> <email> <password>
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
const text = () => js('document.body.innerText.replace(/\\s+/g, " ").trim()')
const submit = (email, pw) => js(`(() => { const f = document.querySelector('form'); f.email.value = ${JSON.stringify(email)}; f.password.value = ${JSON.stringify(pw)}; f.requestSubmit(); return true })()`)
// Polls until an expression is truthy. The server's response time varies, so fixed sleeps race it.
const until = async (expr, ms = 10000) => {
  for (const end = Date.now() + ms; Date.now() < end; await sleep(100)) if (await js(expr)) return true
  return false
}
// Waits until the session check settles on the sign-in form or the signed-in shell.
const go = async (url) => { await send('Page.navigate', { url }); await sleep(300); await until('document.querySelector("form, [data-slot=sidebar-wrapper]")') }
const centerOf = (expr) => js(`(() => { const r = (${expr})?.getBoundingClientRect(); return r && { x: r.x + r.width / 2, y: r.y + r.height / 2 } })()`)
const hoverAt = async (expr) => { const at = await centerOf(expr); if (at) await send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...at }) }
// Clicks the element an expression returns with real mouse events, then moves the pointer off so no tooltip lingers.
const clickAt = async (expr) => {
  const at = await centerOf(expr)
  if (!at) return
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...at })
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', ...at, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', ...at, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 0, y: 0 })
}
const pressCtrlB = async () => {
  for (const type of ['keyDown', 'keyUp']) await send('Input.dispatchKeyEvent', { type, key: 'b', code: 'KeyB', windowsVirtualKeyCode: 66, modifiers: 2 })
  await sleep(500)
}
const navButton = (label, scope = '[data-slot=sidebar]') =>
  `[...document.querySelectorAll('${scope} [data-sidebar=menu-button]')].find((b) => b.textContent === ${JSON.stringify(label)})`
const sidebar = () => js(`(() => {
  const s = document.querySelector('[data-slot=sidebar]')
  const box = s?.querySelector('[data-slot=sidebar-container]')?.getBoundingClientRect()
  const label = [...document.querySelectorAll('[data-slot=sidebar] [data-sidebar=menu-button] span')].find((e) => e.textContent === 'Agents')
  return s && { state: s.dataset.state, width: Math.round(box.width), agentsLabelVisible: !!label?.checkVisibility({ opacityProperty: true }) }
})()`)
const heading = () => js('document.querySelector("main h1")?.textContent')
// The path and query string the address bar shows, such as /sign-in?redirect=%2Ftools.
const url = () => js('location.pathname + location.search')
const atUrl = (path) => until(`location.pathname + location.search === ${JSON.stringify(path)}`)
const back = async () => { await js('history.back(), true') }
const RAISED = { light: 'rgb(245, 246, 247)', dark: 'rgb(14, 15, 16)' }
const sidebarBg = () => js('getComputedStyle(document.querySelector("[data-slot=sidebar-inner]")).backgroundColor')
const pressedTheme = () => js(`document.querySelector('[aria-label$=" theme"][aria-pressed="true"]')?.getAttribute('aria-label')`)
const confirmDialog = () => js('document.querySelector("[role=alertdialog]")?.textContent')
const dialogButton = (label) => `[...document.querySelectorAll('[role=alertdialog] button')].find((b) => b.textContent.trim() === ${JSON.stringify(label)})`
// The Agents chat. scripts/e2e/seed-chats.py saves two chats with these titles, the newer one second.
const OLDER = 'What is a tool call?'
const NEWER = 'Write a system prompt for a support agent'
const chatLinks = (scope) => `[...document.querySelectorAll('${scope} nav[aria-label=Chats] li a')]`
const chatTitles = (scope = 'aside') => js(`${chatLinks(scope)}.map((a) => a.querySelector('span').textContent)`)
const chatLink = (title, scope = 'aside') => `${chatLinks(scope)}.find((a) => a.querySelector('span').textContent === ${JSON.stringify(title)})`
const deleteButton = (title) => `${chatLink(title)}?.parentElement.querySelector('button[aria-label^="Delete"]')`
const transcript = () => js(`[...document.querySelectorAll('main ol > li')].map((li) => li.innerText)`)
const transcriptHas = (n) => until(`document.querySelectorAll('main ol > li').length === ${n}`)
const composer = `document.querySelector('textarea[aria-label=Message]')`
// Types into the composer the way React sees typing, then submits it.
const sendMessage = (text) => js(`(() => {
  const t = ${composer}
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(t, ${JSON.stringify(text)})
  t.dispatchEvent(new Event('input', { bubbles: true }))
  t.form.requestSubmit()
  return true
})()`)
const currentSection = () => js(`document.querySelector('[data-slot=sidebar] [aria-current=page]')?.textContent`)
const reload = async () => { await send('Page.reload'); await sleep(300); await until('document.querySelector("form, [data-slot=sidebar-wrapper]")') }
let failed = 0
const check = (label, cond, detail) => {
  if (!cond) failed++
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${cond || !detail ? '' : `  [${detail}]`}`)
}

await send('Page.enable'); await send('Runtime.enable')
if (process.env.COLOR_SCHEME) await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: process.env.COLOR_SCHEME }] })
await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false })
await go(base)
await js(`localStorage.clear(); document.cookie = 'sidebar_state=; path=/; max-age=0'`); await go(base)
check('opens on sign-in, no landing page', (await text()).startsWith('Sign in to Nextsci'), await text())
check('the sign-in page has its own document title', (await js('document.title')) === 'Sign in · Nextsci', await js('document.title'))
await shot('dash-signin')

await go(`${base}tools`)
check('signed-out visit to /tools goes to sign-in and keeps the path', (await url()) === '/sign-in?redirect=%2Ftools' && (await text()).startsWith('Sign in to Nextsci'), await url())
await shot('dash-signin-redirect')

await submit(email, 'wrong-password'); await until('document.querySelector("[role=alert]")')
const err = await js('document.querySelector("[role=alert]")?.textContent')
check('wrong password shows error', err === 'The email or password is incorrect.', err)
await shot('dash-error')

await submit(email, password); await until('document.querySelector("[data-slot=sidebar-wrapper]")')
let t = await text()
check('right password signs in and shows email', t.includes(email), t)
await atUrl('/tools')
check('signing in returns to the page that asked for it', (await url()) === '/tools' && (await heading()) === 'Tools', `${await url()} ${await heading()}`)
check('each screen has its own document title', (await js('document.title')) === 'Tools · Nextsci', await js('document.title'))

let bar = await sidebar()
check('sidebar starts expanded with the Agents label showing', bar?.state === 'expanded' && bar.width > 200 && bar.agentsLabelVisible, JSON.stringify(bar))
await go(base); await atUrl('/agents'); t = await text()
check('/ opens on Agents when signed in', (await url()) === '/agents' && (await heading()) === 'Agents' && t.includes('Chat with a model'), `${await url()} ${await heading()}`)
await shot('dash-home')

await until(`${chatLinks('aside')}.length === 2`)
check('the chat list shows the saved chats, latest first', JSON.stringify(await chatTitles()) === JSON.stringify([NEWER, OLDER]), JSON.stringify(await chatTitles()))
await clickAt(chatLink(OLDER)); await until('/^\\/agents\\/\\d+$/.test(location.pathname)'); await transcriptHas(4)
const olderUrl = await url()
let said = await transcript()
check('opening a chat shows its messages at its own address', said.length === 4 && said[0].includes(OLDER) && said[1].startsWith('e2e/seeded-model'), `${olderUrl} ${JSON.stringify(said)}`)
check(
  'Agents stays the current section on a chat address, and the list marks the chat',
  (await heading()) === 'Agents' && (await currentSection()) === 'Agents' && (await js(`${chatLink(OLDER)}.getAttribute('aria-current')`)) === 'page',
  `${await heading()} ${await currentSection()}`,
)
await reload(); await transcriptHas(4)
said = await transcript()
check('a chat survives a reload', (await url()) === olderUrl && said.length === 4 && said[3].includes('The backend runs it.'), `${await url()} ${JSON.stringify(said)}`)
await shot('dash-agents-chat')

await sendMessage('Is this saved?'); await until(`document.querySelector('main [role=alert]')`)
const sendError = await js(`document.querySelector('main [role=alert]')?.textContent`)
check('with no model key, sending says how to set one and keeps the draft', sendError?.includes('OPENROUTER_API_KEY') && (await js(`${composer}.value`)) === 'Is this saved?', sendError)
await reload(); await transcriptHas(4)
check('a failed send saves nothing', (await transcript()).length === 4, JSON.stringify(await transcript()))

await clickAt(`[...document.querySelectorAll('aside nav[aria-label=Chats] a')].find((a) => a.textContent.trim() === 'New chat')`); await atUrl('/agents')
await sendMessage('Start a new chat'); await until(`document.querySelector('main [role=alert]')`)
check('a failed first message stays on /agents and keeps the draft', (await url()) === '/agents' && (await js(`${composer}.value`)) === 'Start a new chat', await url())
await reload(); await until(`${chatLinks('aside')}.length >= 2`); await sleep(300)
check('a failed first message leaves no empty chat behind', (await chatTitles()).length === 2, JSON.stringify(await chatTitles()))

await go(`${base}agents/999999`); await until(`document.body.innerText.includes('Chat not found')`)
check('an unknown chat id says so inside Agents', (await text()).includes('Chat not found') && (await currentSection()) === 'Agents', await text())

await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true })
// A touch screen has no hover, so the delete buttons show without it.
await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 })
await go(new URL(olderUrl, base).href); await transcriptHas(4)
const chatTitle = await js(`document.querySelector('main h2')?.textContent`)
check('on a phone, a chat fits the width and its title sits above it', !(await js('document.documentElement.scrollWidth > innerWidth')) && chatTitle === OLDER, chatTitle)
await shot('dash-agents-chat-phone')
await clickAt(`[...document.querySelectorAll('main button')].find((b) => b.textContent.trim() === 'Chats')`); await sleep(500)
const sheetTitles = await chatTitles('[data-slot=sheet-content]')
check('on a phone, the Chats button opens the list in a sheet', JSON.stringify(sheetTitles) === JSON.stringify([NEWER, OLDER]), JSON.stringify(sheetTitles))
const deleteOpacity = await js(`[...document.querySelectorAll('[data-slot=sheet-content] button[aria-label^="Delete"]')].map((b) => getComputedStyle(b).opacity)`)
check('on a touch screen, every chat shows its delete button', JSON.stringify(deleteOpacity) === '["1","1"]', JSON.stringify(deleteOpacity))
await shot('dash-agents-chats-phone')
await clickAt(chatLink(NEWER, '[data-slot=sheet-content]')); await transcriptHas(2); await sleep(500)
const newerUrl = await url()
check('choosing a chat in the sheet opens it and closes the sheet', newerUrl !== olderUrl && /^\/agents\/\d+$/.test(newerUrl) && !(await js('!!document.querySelector("[data-slot=sheet-content]")')), newerUrl)
await send('Emulation.setTouchEmulationEnabled', { enabled: false })
await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false })
await sleep(500)
check('with a mouse, delete buttons stay hidden until hover', (await js(`getComputedStyle(${deleteButton(OLDER)}).opacity`)) === '0')

await clickAt(deleteButton(NEWER)); await sleep(400)
check('deleting a chat asks first', (await confirmDialog())?.startsWith('Delete this chat?'), await confirmDialog())
await shot('dash-agents-delete-confirm')
await clickAt(dialogButton('Cancel')); await sleep(400)
check('cancel keeps the chat', !(await confirmDialog()) && (await chatTitles()).length === 2 && (await url()) === newerUrl, await url())
await clickAt(deleteButton(NEWER)); await sleep(400); await clickAt(dialogButton('Delete')); await atUrl('/agents')
await until(`${chatLinks('aside')}.length === 1`)
check('deleting the open chat removes it and opens a new chat', (await url()) === '/agents' && JSON.stringify(await chatTitles()) === JSON.stringify([OLDER]), `${await url()} ${JSON.stringify(await chatTitles())}`)
await reload(); await until(`${chatLinks('aside')}.length >= 1`); await sleep(300)
check('a deleted chat stays deleted after a reload', JSON.stringify(await chatTitles()) === JSON.stringify([OLDER]), JSON.stringify(await chatTitles()))

for (const theme of ['light', 'dark']) {
  const label = `${theme[0].toUpperCase()}${theme.slice(1)} theme`
  await clickAt(`document.querySelector('header [aria-label="${label}"]')`); await sleep(200)
  const bg = await sidebarBg()
  check(`the header switch turns the sidebar ${theme}`, bg === RAISED[theme] && (await pressedTheme()) === label, bg)
}
await clickAt(`document.querySelector('header [aria-label="System theme"]')`); await sleep(200)
check('the header switch returns to the system theme', (await pressedTheme()) === 'System theme' && !(await js('document.documentElement.dataset.theme')))

const runsLink = await js(`(() => { const a = ${navButton('Runs')}; return a && { tag: a.tagName, href: a.getAttribute('href') } })()`)
check('sidebar items are links, so they open in a new tab', runsLink?.tag === 'A' && runsLink.href === '/runs', JSON.stringify(runsLink))
await clickAt(navButton('Runs')); await atUrl('/runs')
const current = await js(`document.querySelector('[data-slot=sidebar] [aria-current=page]')?.textContent`)
check('clicking Runs opens /runs and marks it current', (await url()) === '/runs' && (await heading()) === 'Runs' && current === 'Runs', `${await url()} ${await heading()} ${current}`)
await back(); await atUrl('/agents')
check('browser back returns to Agents', (await url()) === '/agents' && (await heading()) === 'Agents', `${await url()} ${await heading()}`)

await clickAt(navButton('Tools')); await atUrl('/tools')
check('clicking Tools switches the main heading', (await heading()) === 'Tools' && (await text()).includes('No tools yet'), await heading())

await clickAt('document.querySelector("[data-sidebar=trigger]")'); await sleep(500)
bar = await sidebar()
check('trigger collapses the sidebar to icons', bar?.state === 'collapsed' && bar.width < 64 && !bar.agentsLabelVisible, JSON.stringify(bar))
await shot('dash-tools-collapsed')
await hoverAt(navButton('Runs')); await sleep(400)
const tip = await js('document.querySelector("[data-slot=tooltip-content]")?.textContent')
check('hovering a collapsed icon shows its label', tip === 'Runs', tip)
await shot('dash-tooltip')
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 0, y: 0 }); await sleep(300)

await clickAt(navButton('Knowledge')); await atUrl('/knowledge')
await send('Page.reload'); await sleep(300); await until('document.querySelector("[data-slot=sidebar-wrapper]")')
check('reload on /knowledge stays on Knowledge', (await url()) === '/knowledge' && (await heading()) === 'Knowledge', `${await url()} ${await heading()}`)
bar = await sidebar()
check('sidebar stays collapsed after reload', bar?.state === 'collapsed' && bar.width < 64, JSON.stringify(bar))
check('reload keeps the session', (await text()).includes(email))

await pressCtrlB()
const afterOne = (await sidebar())?.state
await pressCtrlB()
const afterTwo = (await sidebar())?.state
check('Ctrl+B toggles the sidebar', afterOne === 'expanded' && afterTwo === 'collapsed', `${afterOne}, ${afterTwo}`)

await clickAt(navButton('Integrations')); await atUrl('/integrations')
await until(`document.querySelector('main li h2')?.textContent === 'Google Calendar'`)
check('clicking Integrations lists Google Calendar', (await heading()) === 'Integrations' && (await js(`document.querySelector('main li h2')?.textContent`)) === 'Google Calendar', `${await heading()} ${await text()}`)
await shot('dash-integrations')
// Google sends the browser to the callback through the dashboard's /api proxy. A forged state connects nothing.
await go(`${base}api/v1/integrations/google-calendar/callback/?state=forged&code=x`)
await atUrl('/integrations?error=expired'); await until('document.querySelector("main [role=alert]")')
const notice = await js('document.querySelector("main [role=alert]")?.textContent')
check('a failed connection returns to Integrations and says why', (await url()) === '/integrations?error=expired' && notice?.includes('expired'), `${await url()} ${notice}`)
await clickAt(`document.querySelector('main [aria-label=Dismiss]')`); await atUrl('/integrations')
check('dismissing the notice clears it from the address', (await url()) === '/integrations' && !(await js('!!document.querySelector("main [role=alert]")')), await url())

await js(`(() => { const s = JSON.parse(localStorage.getItem('nextsci-agents.session')); s.access = 'expired'; localStorage.setItem('nextsci-agents.session', JSON.stringify(s)); return true })()`)
await go(base)
t = await text()
const renewed = await js(`JSON.parse(localStorage.getItem('nextsci-agents.session')).access !== 'expired'`)
check('expired access token refreshes silently', t.includes(email) && renewed, t)

await go(`${base}no-such-page`)
const notFound = await js(`(() => {
  const a = [...document.querySelectorAll('main a')].find((l) => l.textContent === 'Go to Agents')
  return { title: document.querySelector('main h2')?.textContent, link: a?.getAttribute('href'), shell: !!document.querySelector('[data-slot=sidebar]') }
})()`)
check('an unknown path shows the not-found page in the shell', notFound.title === 'Page not found' && notFound.shell && (await heading()) === 'Page not found', JSON.stringify(notFound))
await shot('dash-not-found')
await clickAt(`[...document.querySelectorAll('main a')].find((l) => l.textContent === 'Go to Agents')`); await atUrl('/agents')
check('the not-found page links back to Agents', (await url()) === '/agents' && (await heading()) === 'Agents', `${await url()} ${await heading()}`)
await go(`${base}agents/no-such-agent`)
const marked = await js(`document.querySelectorAll('[data-slot=sidebar] [aria-current], [data-slot=sidebar] [data-active]').length`)
check('a not-found path under /agents marks no section current', (await heading()) === 'Page not found' && marked === 0 && (await js('document.title')) === 'Page not found · Nextsci', `${await heading()} ${marked}`)

await go(`${base}sign-in`); await atUrl('/agents')
check('signed-in visit to /sign-in goes to Agents', (await url()) === '/agents' && (await heading()) === 'Agents', `${await url()} ${await heading()}`)

await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true })
await sleep(500)
check('signed in, no horizontal scroll at 390px', !(await js('document.documentElement.scrollWidth > innerWidth')))
await shot('dash-home-phone')
await clickAt('document.querySelector("[data-sidebar=trigger]")'); await sleep(500)
check('trigger opens the navigation sheet on a phone', await js(`!!document.querySelector('[data-mobile=true]')?.textContent.includes('Knowledge')`))
await shot('dash-sidebar-phone')
await clickAt(navButton('Runs', '[data-mobile=true]')); await sleep(500)
check('choosing a section in the sheet shows it and closes the sheet', (await url()) === '/runs' && (await heading()) === 'Runs' && !(await js('!!document.querySelector("[data-mobile=true]")')), `${await url()} ${await heading()}`)

await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false })
await sleep(500)
await clickAt('document.querySelector("[data-slot=sidebar-footer] [data-sidebar=menu-button]")'); await sleep(400)
await shot('dash-user-menu')
const openUserMenu = async () => { await clickAt('document.querySelector("[data-slot=sidebar-footer] [data-sidebar=menu-button]")'); await sleep(400) }
const signOutItem = `[...document.querySelectorAll('[role=menuitem]')].find((i) => i.textContent.trim() === 'Sign out')`
const signedIn = async () => (await url()) === '/runs' && (await js('localStorage.getItem("nextsci-agents.session")')) !== null
await clickAt(signOutItem); await sleep(400)
check('sign out asks for confirmation first', (await confirmDialog())?.startsWith('Sign out?') && (await signedIn()), await confirmDialog())
await shot('dash-signout-confirm')
await clickAt(dialogButton('Cancel')); await sleep(400)
check('cancel closes the dialog and keeps the session', !(await confirmDialog()) && (await signedIn()), await url())
await openUserMenu(); await clickAt(signOutItem); await sleep(400)
for (const type of ['keyDown', 'keyUp']) await send('Input.dispatchKeyEvent', { type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
await sleep(400)
check('escape closes the dialog and keeps the session', !(await confirmDialog()) && (await signedIn()), await url())
await openUserMenu(); await clickAt(signOutItem); await sleep(400)
await clickAt(dialogButton('Sign out')); await atUrl('/sign-in')
check('confirming sign out returns to sign-in and clears storage', (await url()) === '/sign-in' && (await text()).startsWith('Sign in to Nextsci') && (await js('localStorage.getItem("nextsci-agents.session")')) === null, await url())
await go(`${base}agents`)
check('after sign out, /agents goes to sign-in', (await url()) === '/sign-in?redirect=%2Fagents', await url())
await go(`${base}no-such-page`)
check('signed-out visit to an unknown path goes to sign-in', (await url()) === '/sign-in?redirect=%2Fno-such-page', await url())

// A redirect that leaves this origin is dropped, so signing in opens Agents instead.
for (const target of ['//evil.example', 'https://evil.example/', '/\\evil.example']) {
  await go(`${base}sign-in?redirect=${encodeURIComponent(target)}`)
  await submit(email, password); await until('document.querySelector("[data-slot=sidebar-wrapper]")'); await atUrl('/agents')
  check(`sign-in ignores the redirect ${target}`, (await js('location.origin')) === new URL(base).origin && (await url()) === '/agents', `${await js('location.href')}`)
  await js('localStorage.clear(), true')
}
await go(`${base}sign-in`)

await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true })
await sleep(400); await shot('dash-signin-phone')
const overflow = await js('document.documentElement.scrollWidth > innerWidth')
check('no horizontal scroll at 390px', !overflow)
ws.close()
process.exit(failed ? 1 : 0)
