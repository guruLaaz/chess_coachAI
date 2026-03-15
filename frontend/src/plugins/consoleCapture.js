/**
 * Console log capture plugin.
 * Must be imported and called BEFORE mounting the Vue app.
 */

const MAX_LOGS = 100
const buffer = []

const origConsole = {
  log: console.log.bind(console),
  warn: console.warn.bind(console),
  error: console.error.bind(console),
}

function capture(level, args) {
  let msg
  try {
    msg = Array.prototype.map
      .call(args, (a) => (typeof a === 'object' ? JSON.stringify(a) : String(a)))
      .join(' ')
  } catch {
    msg = String(args[0] || '')
  }
  buffer.push({ ts: new Date().toISOString(), level, msg })
  if (buffer.length > MAX_LOGS) buffer.shift()
}

export function getConsoleLogs() {
  return buffer
}

export function installConsoleCapture() {
  // Wrap console methods
  console.log = function () {
    capture('log', arguments)
    origConsole.log.apply(null, arguments)
  }
  console.warn = function () {
    capture('warn', arguments)
    origConsole.warn.apply(null, arguments)
  }
  console.error = function () {
    capture('error', arguments)
    origConsole.error.apply(null, arguments)
  }

  // Capture unhandled errors
  window.addEventListener('error', (e) => {
    capture('error', [
      'Uncaught: ' + (e.message || '') + ' at ' + (e.filename || '') + ':' + (e.lineno || ''),
    ])
  })
  window.addEventListener('unhandledrejection', (e) => {
    capture('error', ['Unhandled rejection: ' + (e.reason || '')])
  })

  // Intercept fetch to log failed requests
  const origFetch = window.fetch
  window.fetch = function () {
    let url = arguments[0]
    if (typeof url === 'object' && url.url) url = url.url
    return origFetch.apply(this, arguments).then((resp) => {
      if (!resp.ok) capture('warn', ['Fetch ' + resp.status + ': ' + url])
      return resp
    }).catch((err) => {
      capture('error', ['Fetch failed: ' + url + ' — ' + err])
      throw err
    })
  }

  // Seed with page context
  capture('log', ['Page: ' + location.href])
  capture('log', ['UA: ' + navigator.userAgent])
  capture('log', [
    'Screen: ' + screen.width + 'x' + screen.height +
    ', viewport: ' + window.innerWidth + 'x' + window.innerHeight,
  ])
  capture('log', [
    'Theme: ' + (localStorage.getItem('theme') || 'system') +
    ', Lang: ' + (localStorage.getItem('lang') || 'en'),
  ])

  // Log page load timing
  window.addEventListener('load', () => {
    setTimeout(() => {
      const nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0]
      if (nav) {
        capture('log', [
          'Page loaded: DOM ready ' + Math.round(nav.domContentLoadedEventEnd) +
          'ms, full load ' + Math.round(nav.loadEventEnd) + 'ms',
        ])
      }
    }, 0)
  })
}
