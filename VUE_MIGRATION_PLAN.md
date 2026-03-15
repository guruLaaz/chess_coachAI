# Vue 3 Migration Plan — Chess CoachAI

## Overview

Full rewrite from Jinja2 templates + inline JS/CSS to a Vue 3 SPA served by Vite, with Flask as a pure JSON API backend.

**Tech stack:** Vue 3 (Composition API), Vite, Vue Router, Pinia, vue-i18n

**Current state:** 10 Jinja2 templates, ~600 lines inline JS, ~3,500 lines inline CSS, 140+ i18n keys, 15 Flask routes (4 already JSON APIs).

---

## Execution Order

| Phase | Prompts | What | Parallel? |
|-------|---------|------|-----------|
| 1 | 1 + 2 | API layer + Vue scaffolding | Yes, run together |
| 2 | 3 + 4 | Sidebar/filters + Feedback/ChessBoard | Yes, run together (need phase 1 done) |
| 3 | 5 + 6 + 7 + 8 | All pages | Yes, all 4 can run together (need phase 2 done) |
| 4 | 9 | Test migration | Run alone (need phase 3 done) |
| 5 | 10 | Flask SPA integration + cleanup | Run last |

---

## File Structure After Migration

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── vitest.config.js
├── src/
│   ├── main.js
│   ├── App.vue
│   ├── api/
│   │   └── index.js
│   ├── assets/
│   │   └── theme.css
│   ├── components/
│   │   ├── ui/                    # ← REUSABLE primitives (used across pages)
│   │   │   ├── BaseButton.vue     #   Primary/secondary/ghost variants
│   │   │   ├── BaseInput.vue      #   Text input with label, icon prefix, error state
│   │   │   ├── BaseSelect.vue     #   Styled <select> with label
│   │   │   ├── StatCard.vue       #   Stat card (label + value + optional donut)
│   │   │   ├── DonutChart.vue     #   SVG donut chart (percentage ring)
│   │   │   ├── EvalBadge.vue      #   Color-coded eval badge (good/bad/neutral)
│   │   │   ├── UserBadges.vue     #   Chess.com/Lichess username links
│   │   │   ├── EmptyState.vue     #   Icon + title + description + optional action
│   │   │   ├── ToggleGroup.vue    #   Multi-select toggle buttons (used for TC, color)
│   │   │   └── DropdownFilter.vue #   Button that opens a checkbox dropdown panel
│   │   ├── forms/                 # ← REUSABLE form components
│   │   │   └── AnalyzeForm.vue    #   Username inputs + submit (used on landing AND retry)
│   │   ├── controls/
│   │   │   ├── LanguageToggle.vue
│   │   │   ├── ThemeToggle.vue
│   │   │   └── SiteControls.vue
│   │   ├── layout/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppLayout.vue
│   │   │   ├── SimpleLayout.vue
│   │   │   └── AdminLayout.vue
│   │   ├── sidebar/
│   │   │   ├── TheSidebar.vue
│   │   │   ├── SidebarNav.vue
│   │   │   ├── SidebarFilters.vue
│   │   │   ├── SidebarSyncButton.vue
│   │   │   ├── PlatformFilter.vue     # uses BaseSelect
│   │   │   ├── TimeControlFilter.vue  # uses ToggleGroup
│   │   │   ├── ColorFilter.vue        # uses ToggleGroup
│   │   │   ├── MinGamesFilter.vue
│   │   │   └── DateFilter.vue
│   │   ├── openings/
│   │   │   └── OpeningCard.vue    # uses EvalBadge, ChessBoard
│   │   ├── endgames/
│   │   │   └── EndgameCard.vue    # uses EvalBadge, ChessBoard, UserBadges
│   │   ├── ChessBoard.vue
│   │   └── FeedbackModal.vue
│   ├── composables/
│   │   ├── useBoardLoader.js
│   │   ├── useInfiniteScroll.js
│   │   ├── useFiltering.js
│   │   └── useEndgameFiltering.js
│   ├── i18n/
│   │   ├── index.js
│   │   ├── en.js
│   │   └── fr.js
│   ├── plugins/
│   │   └── consoleCapture.js
│   ├── stores/
│   │   ├── theme.js
│   │   ├── filters.js
│   │   └── user.js
│   ├── utils/
│   │   └── translateMessage.js
│   └── views/
│       ├── LandingPage.vue
│       ├── StatusPage.vue
│       ├── NoGamesPage.vue
│       ├── OpeningsPage.vue
│       ├── EndgamesPage.vue
│       ├── EndgamesAllPage.vue
│       ├── AdminJobsPage.vue
│       └── AdminFeedbackPage.vue
└── tests/
    ├── setup.js
    ├── components/
    │   ├── LanguageToggle.test.js
    │   ├── ThemeToggle.test.js
    │   ├── FeedbackModal.test.js
    │   ├── ChessBoard.test.js
    │   ├── SidebarFilters.test.js
    │   ├── OpeningCard.test.js
    │   └── EndgameCard.test.js
    ├── composables/
    │   ├── useFiltering.test.js
    │   ├── useInfiniteScroll.test.js
    │   └── useEndgameFiltering.test.js
    ├── stores/
    │   ├── theme.test.js
    │   └── filters.test.js
    ├── utils/
    │   └── translateMessage.test.js
    └── views/
        ├── LandingPage.test.js
        ├── StatusPage.test.js
        └── OpeningsPage.test.js
```

---

## Reusable Component Design

These are the shared primitives that multiple pages compose. Each should be fully self-contained with props, emits, slots, and scoped styles.

| Component | Props | Used by |
|-----------|-------|---------|
| **BaseButton** | `variant` ('primary'\|'secondary'\|'ghost'), `size` ('sm'\|'md'), `disabled`, `loading` | Landing, Status, No Games, Feedback, Admin, Sidebar |
| **BaseInput** | `modelValue`, `label`, `placeholder`, `error`, `icon` (slot for prefix icon), `type` | Landing (username inputs), Status (retry form), Feedback (email) |
| **BaseSelect** | `modelValue`, `label`, `options` ([{value, label}]) | PlatformFilter, sort dropdowns, feedback type |
| **StatCard** | `label`, `value`, `donut` (boolean), `donutPct` (number) | Openings (4 cards), Endgames (3 cards), Admin (5+3 summary cards) |
| **DonutChart** | `percentage`, `size`, `strokeWidth`, `color` | StatCard (when donut=true), Openings accuracy, Endgames win rate |
| **EvalBadge** | `value`, `type` ('good'\|'bad'\|'neutral') | OpeningCard (eval loss, position eval), Endgames game rows (material diff) |
| **UserBadges** | `chesscomUser`, `lichessUser` | Openings h1, Endgames h1, EndgamesAll h1 |
| **EmptyState** | `icon`, `title`, `description`, `actionLabel`, `actionTo` | Openings (no deviations, no filter results), Endgames (no endgames), EndgamesAll (no games) |
| **ToggleGroup** | `modelValue` (string[]), `options` ([{value, label}]), `minSelected` (number, default 0) | TimeControlFilter (min 0), ColorFilter (min 1), EndgamesAll TC filter |
| **DropdownFilter** | `label`, slot for panel content | EndgamesAll time class dropdown, could be reused for future filters |
| **AnalyzeForm** | `chesscomUser`, `lichessUser`, `errorKeys`, `compact` (boolean) | Landing page (full size), Status page retry (compact), Sidebar sync button |
| **ChessBoard** | `fen`, `move`, `color`, `arrowColor`, `size` | OpeningCard (×2), EndgameCard, EndgamesAll game rows |

**Design principles:**
- Every component accepts a `class` prop for external styling overrides (Vue does this automatically)
- Use `v-model` pattern (modelValue + update:modelValue) for two-way binding on form components
- Use slots for flexible content (BaseButton default slot for label, BaseInput icon slot)
- Use CSS custom properties from theme.css — never hardcode colors except in admin pages
- All user-visible text uses `$t('key')` — no hardcoded English strings

---

## Test Plan

### What exists today

| File | Type | Tests | What it covers |
|------|------|-------|----------------|
| `tests/integration/test_web_routes.py` | pytest | 45 | URL parsing, form validation, job lifecycle, redirects, status polling, cancellation, feedback, admin pages |
| `tests/unit/test_web_reports.py` | pytest | 25 | Helper functions (group_deviations, move_to_san, format_clock, etc.), data loaders (load_openings_data, load_endgames_data), route rendering |
| `tests/e2e/test_openings_scroll.py` | Playwright | 7 | Infinite scroll pagination, lazy board loading, initial page load |

### What happens to each test file

**`tests/unit/test_web_reports.py`** — KEEP AS-IS
- Tests pure Python functions (`group_deviations`, `move_to_san`, `format_clock`, `ply_to_move_label`, `format_date`, `prepare_deviation`, `get_opening_groups`, `render_board_svg`)
- Tests data loaders (`load_openings_data`, `load_endgames_data`, `_aggregate_endgames`)
- These functions are unchanged — they still power the API endpoints
- No modifications needed

**`tests/integration/test_web_routes.py`** — MODIFY
- Tests that check HTML content (`assert b'Chess Coach' in resp.data`, `assert b'Sicilian Najdorf' in html`) need to be rewritten to test JSON API responses instead
- Tests that check redirects, validation, status/cancel, feedback submission — keep as-is (those routes don't change)
- Specific changes listed below in the migration table

**`tests/e2e/test_openings_scroll.py`** — REWRITE
- Currently tests Jinja2-rendered HTML with Playwright
- Will need to test the Vue SPA instead
- Same scenarios (infinite scroll, lazy boards) but different selectors and setup

### Test migration: what changes in `test_web_routes.py`

| Test class | Current behavior | After migration |
|------------|-----------------|-----------------|
| `TestParseUserPath` | Tests URL parsing util | **Keep as-is** — util unchanged |
| `TestBuildUserPath` | Tests URL building util | **Keep as-is** |
| `TestRoundTrip` | Tests parse/build roundtrip | **Keep as-is** |
| `TestCheckUsernameExists` | Tests account validation | **Keep as-is** |
| `TestAnalyzeValidation` | Tests POST /analyze validation, checks HTML error content | **Modify** — add JSON Accept header, assert JSON error_keys instead of HTML strings |
| `TestAnalyzeAccountExists` | Tests account-not-found, checks HTML content | **Modify** — test JSON response path |
| `TestAnalyzeRedirects` | Tests redirect logic (302s) | **Keep as-is** — redirects still work the same way |
| `TestUserReport` | Tests GET /u/{path} HTML rendering | **Replace** — test GET /api/report/openings/{path} JSON response |
| `TestStatusJson` | Tests GET /u/{path}/status/json | **Keep as-is** — endpoint unchanged |
| `TestStatusCancel` | Tests POST cancel | **Keep as-is** |
| `TestAnalyzeDispatch` | Tests Celery task dispatch | **Keep as-is** |
| `TestSubmitFeedback` | Tests POST /api/feedback | **Keep as-is** |
| `TestAdminFeedback` | Tests GET /admin/feedback HTML | **Replace** — test GET /api/admin/feedback JSON |
| `TestAdminFlaskLogs` | Tests GET /admin/logs/flask | **Keep as-is** — endpoint unchanged |
| `TestAdminJobLogs` | Tests GET /admin/jobs/{id}/logs | **Keep as-is** |

And in `test_web_reports.py`:

| Test class | After migration |
|------------|-----------------|
| All helper function tests | **Keep as-is** |
| `TestLoadOpeningsData` | **Keep as-is** |
| `TestLoadEndgamesData` | **Keep as-is** |
| `TestAggregateEndgamesGameMeta` | **Keep as-is** |
| `TestOpeningsRoute` | **Replace** — test /api/report/openings/{path} JSON |
| `TestOpeningDetailRoute` | **Replace** — test /api/report/openings/{path}/{eco}/{color} JSON |
| `TestEndgameRoutes` | **Replace** — test /api/report/endgames/{path} JSON |
| `TestRenderBoardsAPI` | **Keep as-is** |
| `TestSyncButton` | **Delete** — sync button is now a Vue component, tested in frontend |
| `TestUbuntuFont` | **Delete** — font loading is now in Vue's index.html |

### New frontend tests (Vitest + Vue Test Utils)

| Test file | What it covers |
|-----------|---------------|
| `stores/theme.test.js` | Toggle dark/light, localStorage persistence, init from system preference |
| `stores/filters.test.js` | Default state, sessionStorage save/restore, reset, TC/color/platform changes |
| `composables/useFiltering.test.js` | Filter by platform, TC, color, min games, date; sort by eval_loss and loss_pct |
| `composables/useInfiniteScroll.test.js` | Initial page size, loadMore increments, reset, never exceeds total |
| `composables/useEndgameFiltering.test.js` | Cross-filter game_details, recompute W/L/D, pick matching example candidate |
| `utils/translateMessage.test.js` | All regex patterns from _tMsg: "Analyzing game 5/120...", "Fetched 200 Lichess games", etc. |
| `components/SidebarFilters.test.js` | Filter interactions update store, at least one color stays active, range slider updates label |
| `components/FeedbackModal.test.js` | Open/close, email validation, type toggle shows/hides screenshot, submit calls API, success auto-close |
| `components/OpeningCard.test.js` | Renders eco name, eval badges, recommendation text, board components |
| `components/EndgameCard.test.js` | Renders type, balance badge, W/L/D percentages, show-all link |
| `components/LanguageToggle.test.js` | Switches locale, saves to localStorage |
| `components/ThemeToggle.test.js` | Toggles data-theme attribute, saves to localStorage |
| `components/ChessBoard.test.js` | Shows spinner while loading, renders SVG after load |
| `views/LandingPage.test.js` | Form validation, error display, submit calls /analyze |
| `views/StatusPage.test.js` | Polling updates UI, auto-redirect on complete, cancel on unmount, formatElapsed |
| `views/OpeningsPage.test.js` | Fetches data, renders cards, filters work, empty states |

### E2E test migration (`test_openings_scroll.py`)

The E2E tests use Playwright and test real browser behavior. After migration:

1. The Flask test server setup changes — instead of rendering `openings.html` template directly, it serves the built Vue SPA and provides mock API endpoints
2. The selectors change — `.card[data-filtered="yes"]` becomes whatever CSS class the Vue `OpeningCard` component uses
3. The board loading detection changes — `window.fetchingBoards` becomes whatever the Vue composable exposes
4. Same test scenarios: initial load shows PAGE_SIZE cards, scroll loads more, boards load lazily for visible cards only

---

## Prompts

Each prompt below is **self-contained**. Copy everything between the `--- START ---` and `--- END ---` markers.

---

### Prompt 1: Backend API Layer

**Depends on:** nothing | **Can run in parallel with:** Prompt 2

--- START PROMPT 1 ---

You are working on the Chess CoachAI project (Flask + PostgreSQL + Celery).

TASK: Add JSON API endpoints to `web/routes.py` so a Vue SPA can fetch all data as JSON. Keep the existing HTML routes intact — we'll remove them later. Each new API route should be prefixed with `/api/`.

Read `web/routes.py` and `web/reports.py` first to understand the current routes and data loading functions.

Here's exactly what to create:

1. **GET /api/report/openings/\<user_path\>**
   - Call `parse_user_path(user_path)` to get chesscom_user, lichess_user
   - Call `get_latest_job()` — if no job or not complete, return `{"redirect": "/"}` or `{"redirect": "/u/{user_path}/status"}` with appropriate status
   - If complete with 0 games: return `{"no_games": true, "chesscom_user": ..., "lichess_user": ...}`
   - If complete: call `load_openings_data()` and return the full dict as JSON
   - The `items` list contains datetimes and other non-serializable types — make sure to handle serialization (use `str()` for dates, or add a helper)

2. **GET /api/report/openings/\<user_path\>/\<eco\>/\<color\>**
   - Same as above but filter items to matching eco_code and color
   - Return same shape with `filter_eco` and `filter_color` fields added

3. **GET /api/report/endgames/\<user_path\>**
   - Call `load_endgames_data()` and return as JSON
   - Include `groups` from `load_openings_data()` (for sidebar navigation)
   - Handle same redirect logic as openings

4. **GET /api/report/endgames-all/\<user_path\>**
   - Accept query params: `def`, `type`, `balance`
   - Call `load_endgames_all_data()` and return as JSON
   - Handle datetime serialization for `end_time` fields

5. **GET /api/admin/jobs**
   - Return `{"jobs": [...]}` from `queries.get_all_jobs(limit=200)`
   - Include computed `duration_seconds` field

6. **GET /api/admin/feedback**
   - Return `{"entries": [...]}` from `queries.get_all_feedback(limit=200)`

7. **Update POST /analyze to support JSON responses**
   - When the request has `Accept: application/json` header:
     - On validation error: return `{"error_keys": [...]}` with status 400
     - On success (redirect): return `{"redirect": "/u/{user_path}/status"}` with status 200
   - Keep existing HTML form behavior when Accept header is not JSON

The following API endpoints ALREADY EXIST and don't need changes:
- POST /u/\<user_path\>/api/render-boards
- GET /u/\<user_path\>/status/json
- POST /u/\<user_path\>/status/cancel
- POST /api/feedback
- GET /admin/jobs/\<job_id\>/logs
- GET /admin/logs/flask

IMPORTANT DETAILS:
- `load_openings_data()` and `load_endgames_data()` return dicts that may contain datetime objects, namedtuples, or other non-JSON-serializable types. Add a `_serialize(obj)` helper that handles these (convert datetimes to ISO strings, namedtuples to dicts, etc.). Use `json.dumps(data, default=_serialize)` and return a proper Response with content-type application/json, or use Flask's `jsonify` after converting.
- The `items` in openings data have fields like `game_date` (string, already formatted) and `game_date_iso` (string) so those should be fine. But `end_time` in endgames data is a datetime.
- Add tests for each new endpoint in `tests/integration/test_web_routes.py`. Follow the existing test patterns — they use `app.test_client()` and mock `db.queries`. Add a new test class `TestApiEndpoints` with tests for:
  - Each endpoint returning correct JSON shape
  - Redirect responses for missing/incomplete jobs
  - Serialization of complex types
  - The JSON Accept header path for POST /analyze (validation errors and success)

--- END PROMPT 1 ---

---

### Prompt 2: Vue Project Scaffolding

**Depends on:** nothing | **Can run in parallel with:** Prompt 1

--- START PROMPT 2 ---

You are working on the Chess CoachAI project. The backend is Flask (Python) serving from the project root.

TASK: Create a Vue 3 SPA project in a `frontend/` directory with Vite, Vue Router, Pinia, and vue-i18n fully configured. This is the foundation all other frontend work builds on.

STEP 1: Initialize the project

Run these commands:
```bash
cd /c/Users/franc/OneDrive/Documents/chess_coachAI
npm create vite@latest frontend -- --template vue
cd frontend
npm install
npm install vue-router@4 pinia @pinia/plugin-persistedstate vue-i18n@10
```

STEP 2: Configure Vite (`frontend/vite.config.js`)

Set up a dev proxy so API calls go to the Flask backend:
```js
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5050',
      '/u': 'http://localhost:5050',
      '/analyze': 'http://localhost:5050',
      '/admin': 'http://localhost:5050',
    }
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  }
})
```

STEP 3: Set up Vue Router (`frontend/src/router/index.js`)

Create routes matching the current URL structure:
```
/                                → LandingPage
/u/:userPath                     → OpeningsPage
/u/:userPath/opening/:eco/:color → OpeningsPage (with props)
/u/:userPath/endgames            → EndgamesPage
/u/:userPath/endgames/all        → EndgamesAllPage
/u/:userPath/status              → StatusPage
/admin/jobs                      → AdminJobsPage
/admin/feedback                  → AdminFeedbackPage
```

Note: `userPath` can contain slashes (e.g., `hikaru/drnykterstein` or `-/drnykterstein`). Use a catch-all param pattern like `:userPath(.+)` or define multiple route patterns to handle this.

Use lazy-loaded route components: `() => import('../views/OpeningsPage.vue')` etc.
Create placeholder components for each view (just a `<div>Page name</div>`) in `frontend/src/views/`.

STEP 4: Set up Pinia stores (`frontend/src/stores/`)

Create these store files with placeholder structure:

a) `theme.js` — Theme store:
   - State: `darkMode` (boolean)
   - Actions: `toggle()`, `init()` (reads localStorage or prefers-color-scheme)
   - On change: sets `document.documentElement.setAttribute('data-theme', 'dark')` or removes it
   - Persist to localStorage key 'theme'

b) `filters.js` — Filter store:
   - State: `platform` ('all'|'chesscom'|'lichess'), `timeControls` (string[]), `colors` (string[]), `minGames` (number), `dateFrom` (string), `dateDays` (string), `sort` (string)
   - Actions: `reset()`, `setFromSessionStorage()`, `saveToSessionStorage()`
   - Persist to sessionStorage key '_filters'
   - Default timeControls: ['blitz', 'rapid'], colors: ['white', 'black'], minGames: 3

c) `user.js` — User/report store:
   - State: `userPath`, `chesscomUser`, `lichessUser`, `reportData` (null or object)
   - Actions: `fetchOpenings(userPath)`, `fetchEndgames(userPath)`, `fetchEndgamesAll(userPath, params)`
   - These will call the /api/report/* endpoints (implement the fetch calls)

STEP 5: Set up vue-i18n (`frontend/src/i18n/index.js`)

Create the i18n instance with all 140+ translation keys. Extract them from the existing `controls.html` translations object. The file is at `web/templates/partials/controls.html` — read it and extract the full `translations` object (it's a JS object with `en` and `fr` keys for every translation).

Structure as:
```js
// frontend/src/i18n/en.js
export default {
  badge: 'Powered by Stockfish 16',
  hero_line1: 'Find your opening weaknesses.',
  // ... ALL keys from the translations object
}

// frontend/src/i18n/fr.js
export default {
  badge: 'Propulsé par Stockfish 16',
  hero_line1: 'Trouvez vos faiblesses en ouverture.',
  // ... ALL French translations
}

// frontend/src/i18n/index.js
import { createI18n } from 'vue-i18n'
import en from './en.js'
import fr from './fr.js'

export default createI18n({
  legacy: false,
  locale: localStorage.getItem('lang') || 'en',
  fallbackLocale: 'en',
  messages: { en, fr }
})
```

IMPORTANT: Read `web/templates/partials/controls.html` and extract EVERY key from the translations object. There are 140+ keys. Do not skip any.

STEP 6: Set up the app entry point

`frontend/src/main.js`:
```js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import i18n from './i18n'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(i18n)
app.mount('#app')
```

`frontend/src/App.vue`:
- Just `<router-view />` for now. Layout will be added later.

STEP 7: Set up CSS variables (`frontend/src/assets/theme.css`)

Extract ALL CSS custom properties from the existing templates into a single theme file. Read `web/templates/landing.html`, `web/templates/openings.html`, and `web/templates/partials/sidebar.html` to collect all `--var-name` definitions for both light and dark themes.

Create `frontend/src/assets/theme.css` with:
- `:root { ... }` block with all light-mode variables
- `[data-theme="dark"] { ... }` block with all dark-mode variables
- Global reset styles (box-sizing, margin, padding, font-family Ubuntu)
- Import Ubuntu font from Google Fonts

Import this in `main.js`.

STEP 8: Create a `frontend/src/api/index.js` module

Centralize all API calls:
```js
export async function fetchOpeningsReport(userPath) { ... }
export async function fetchEndgamesReport(userPath) { ... }
export async function fetchEndgamesAll(userPath, params) { ... }
export async function fetchStatusJson(userPath) { ... }
export async function cancelJob(userPath) { ... }
export async function renderBoards(userPath, specs) { ... }
export async function submitFeedback(payload) { ... }
export async function submitAnalysis(formData) { ... }
export async function fetchAdminJobs() { ... }
export async function fetchAdminFeedback() { ... }
export async function fetchJobLogs(jobId) { ... }
export async function fetchFlaskLogs(params) { ... }
```

Each function should use `fetch()`, handle errors, and return parsed JSON. `submitAnalysis` should send with `Accept: application/json` header and return the JSON response (which contains either `{redirect: url}` or `{error_keys: [...]}`).

STEP 9: Verify it works

Run `cd frontend && npm run dev` and confirm it starts without errors. Visit http://localhost:5173 and confirm you see the placeholder page.

Add a `.gitignore` in `frontend/` with `node_modules/` and `dist/`.

--- END PROMPT 2 ---

---

### Prompt 3: Sidebar + Filter System

**Depends on:** Prompt 2 | **Can run in parallel with:** Prompt 4

--- START PROMPT 3 ---

You are working on the Chess CoachAI Vue 3 migration. The Vue project is set up in `frontend/` with Vue Router, Pinia, and vue-i18n.

TASK: Build reusable UI primitives, the sidebar component, and the full filter system. The primitives will be used across many pages, so design them to be fully self-contained.

Read the existing implementation first:
- `web/templates/partials/sidebar.html` — current sidebar HTML + filter persistence JS
- `web/templates/openings.html` — see how `applyFilters()` works (the filtering logic)
- `web/templates/endgames.html` — similar filter logic but with cross-filtering of game details

DESIGN PRINCIPLE: Maximize reuse. Every component below should be self-contained with props, emits, slots, and scoped styles. No component should have knowledge of where it's used — it should work equally well on any page.

WHAT TO BUILD:

### Reusable UI primitives (`frontend/src/components/ui/`)

Before building the sidebar, create these shared primitives that multiple pages will compose:

a) **BaseButton.vue** — Reusable button with variants:
   - Props: `variant` ('primary'|'secondary'|'ghost', default 'primary'), `size` ('sm'|'md', default 'md'), `disabled` (boolean), `loading` (boolean), `type` ('button'|'submit', default 'button')
   - Default slot for label content
   - Primary: blue bg (#2563eb), white text, hover blue-hover. Secondary: border, bg-secondary, hover opacity. Ghost: no border/bg, hover bg-secondary.
   - Sm: padding 6px 16px, 0.85rem. Md: padding 10px 24px, 0.95rem.
   - Loading state shows a small spinner and disables the button

b) **BaseInput.vue** — Reusable text input:
   - Props: `modelValue`, `label`, `placeholder`, `error` (string), `type` ('text'|'email'|'date', default 'text'), `id`
   - Emits: `update:modelValue`
   - Slot: `prefix` (for icon positioned absolute-left inside the input)
   - Error state: red border, error message below in 0.85rem red text
   - Styling: border-radius 8px, padding 10px 12px (+ 40px left if prefix slot used), focus ring blue

c) **BaseSelect.vue** — Styled select dropdown:
   - Props: `modelValue`, `label`, `options` ([{value: string, label: string}]), `id`
   - Emits: `update:modelValue`
   - Styling: width 100%, border-radius 10px, padding 10px 12px

d) **StatCard.vue** — Stat display card:
   - Props: `label` (string), `value` (string|number), `donut` (boolean, default false), `donutPct` (number)
   - When donut=true, renders a DonutChart next to the value
   - Styling: flex 1, min-width 120px, padding 20px, bg var(--card-bg), border-radius 12px

e) **DonutChart.vue** — SVG percentage ring:
   - Props: `percentage` (number 0-100), `size` (number, default 48), `strokeWidth` (number, default 4), `color` (string, default 'var(--blue)')
   - Renders an SVG circle with stroke-dasharray/dashoffset to show the fill percentage
   - Center text shows the percentage value

f) **EvalBadge.vue** — Color-coded inline badge:
   - Props: `value` (string), `type` ('good'|'bad'|'neutral', default 'neutral')
   - Good: green bg/text, Bad: red bg/text, Neutral: gray bg/text
   - Styling: inline-block, padding 2px 8px, border-radius 4px, 0.8rem font, font-weight 600
   - Respects light/dark theme

g) **UserBadges.vue** — Platform username links:
   - Props: `chesscomUser` (string|null), `lichessUser` (string|null)
   - Renders external links to Chess.com/Lichess profiles (open in new tab)
   - Shows platform icon + username for each
   - Only renders badges for non-null usernames

h) **EmptyState.vue** — Empty state display:
   - Props: `icon` (string, default '♘'), `title` (string), `description` (string), `actionLabel` (string, optional), `actionTo` (string, optional — router-link target)
   - Centered layout with icon at 3rem, title at 1.5rem, description text-secondary
   - Optional action button using BaseButton

i) **ToggleGroup.vue** — Multi-select toggle button group:
   - Props: `modelValue` (string[]), `options` ([{value: string, label: string}]), `minSelected` (number, default 0), `columns` (number, default options.length)
   - Emits: `update:modelValue`
   - Prevents deselecting below minSelected (ignores click if it would violate minimum)
   - Renders as flex-wrap grid with border-radius on outer corners only
   - Active buttons: bg var(--toggle-active-bg), color var(--text-primary)
   - Used by: TimeControlFilter (min 0, 2 columns), ColorFilter (min 1), EndgamesAll TC filter

j) **DropdownFilter.vue** — Button with dropdown panel:
   - Props: `label` (string)
   - Default slot: panel content
   - Click button toggles panel open/close
   - Clicking outside closes the panel
   - Panel: position absolute, top 100%, left 0, bg var(--card-bg), border, border-radius 8px, padding 12px, z-index 10

### Sidebar + Layout components

1. **`frontend/src/components/layout/AppHeader.vue`**
   - Fixed header bar (60px height, z-index 100)
   - Left: Logo (♞ Chess Coach AI) — links to `/` or `/u/{userPath}` if on report page
   - Right: slot for controls (language toggle, theme toggle, feedback button)
   - Matches the existing header styling from `landing.html` and `sidebar.html`

2. **`frontend/src/components/layout/AppLayout.vue`**
   - Used by report pages (openings, endgames)
   - Two-column layout: sidebar (260px sticky) + main content (flex-1)
   - Responsive: at 768px, sidebar goes full-width above content
   - Has `<slot>` for main content
   - Includes AppHeader

3. **`frontend/src/components/layout/SimpleLayout.vue`**
   - Used by landing, status, no_games pages
   - Just AppHeader + centered content
   - Has `<slot>` for content

4. **`frontend/src/components/sidebar/SidebarNav.vue`**
   - Navigation links: Openings and Endgames
   - Each link uses `<router-link>` with active state styling
   - Active state: orange left border (#f97316), orange text, warm background
   - SVG icons for each link (copy from existing sidebar.html)
   - Props: `userPath` (string)

5. **`frontend/src/components/sidebar/SidebarFilters.vue`**
   - Contains all filter controls, emits changes via the Pinia filter store
   - Sub-components for each filter type:

   a) **PlatformFilter.vue** — Uses `BaseSelect` with options: All/Chess.com/Lichess
   b) **TimeControlFilter.vue** — Uses `ToggleGroup` with options Bullet/Blitz/Rapid/Daily, columns=2, minSelected=0
   c) **ColorFilter.vue** — Uses `ToggleGroup` with options White/Black, minSelected=1
   d) **MinGamesFilter.vue** — Range slider (1-20, default 3) with value label (this is unique enough to be inline, no shared primitive needed)
   e) **DateFilter.vue** — Uses `BaseInput` (type="date") + 4 preset buttons (All-time/Last week/6 months/Last year). Clicking a preset sets the date input value and marks the preset active. Manually changing the date clears the active preset.

   Each filter component should:
   - Read initial state from the Pinia `filters` store
   - Update the store on change
   - The store auto-saves to sessionStorage on every change

6. **`frontend/src/components/sidebar/SidebarSyncButton.vue`**
   - Form that POSTs to `/analyze` with hidden username inputs
   - Teal button (#0d9488) with "Sync Games" label
   - Props: `chesscomUser`, `lichessUser`

7. **`frontend/src/components/sidebar/TheSidebar.vue`**
   - Composes all sidebar sub-components
   - Props: `userPath`, `chesscomUser`, `lichessUser`, `page` ('openings'|'endgames'|'endgames_all'), `showFilters` (boolean, default true)
   - Layout: Nav at top, divider, filters section (if showFilters), sync button at bottom (margin-top: auto)

8. **Update `frontend/src/stores/filters.js`**
   - Implement full filter state management
   - `saveToSessionStorage()`: JSON-serialize state to sessionStorage key '_filters'
   - `restoreFromSessionStorage()`: Parse and apply, return boolean success
   - Watch for changes and auto-save (use Pinia `$subscribe`)
   - Action: `reset()` — restore defaults

9. **`frontend/src/composables/useFiltering.js`**
   - A composable that takes an array of items and the filter store, returns filtered + sorted items
   - Filtering logic (replicate from openings.html applyFilters):
     - Platform: match item.platform ('chesscom'|'lichess') or 'all'
     - Time control: match item.time_class against active TCs (map: bullet→bullet, blitz→blitz, rapid→rapid, daily→daily/classical)
     - Color: match item.color against active colors
     - Min games: item.times_played >= minGames
     - Date: item.game_date_iso >= dateFrom (if set)
   - Sorting: by sort field (eval_loss_raw desc, or loss_pct desc)
   - Returns: `{ filteredItems, visibleCount, hasResults }`
   - This composable will be used by OpeningsPage and EndgamesPage

CSS DETAILS — copy these exactly from the existing templates:
- Sidebar width: 260px, sticky position, top: 60px (below header), height: calc(100vh - 60px)
- Background: var(--bg-primary), border-right: 1px solid var(--border)
- Nav links: padding 10px 20px, border-left 3px transparent, gap 10px with SVG icon
- Active nav link: color #f97316, border-left-color #f97316, background #fff7ed (light) / #431407 (dark)
- Filter sections: padding 6px 20px
- Section label: 0.7rem uppercase, color text-muted, letter-spacing 0.8px
- TC toggle: flex wrap, 2x2 grid, border 1px solid, border-radius 6px on outer corners
- TC button active: background var(--toggle-active-bg), color var(--text-primary)
- Range slider: 4px height, #f97316 thumb (16px circle)
- Date presets: flex wrap gap 6px, 0.75rem font-size, border-radius 6px
- Sync button: flex center, gap 8px, background #0d9488, color white, border-radius 10px, font-weight 600

All visible text must use `{{ $t('key') }}` for i18n. Keys: nav_openings, nav_endgames, filter_label, filter_platform, filter_all_platforms, filter_time_control, filter_playing_as, filter_min_games, filter_from, filter_alltime, filter_lastweek, filter_6months, filter_lastyear, sync_btn.

--- END PROMPT 3 ---

---

### Prompt 4: Feedback Modal + Chess Board + Controls

**Depends on:** Prompt 2 | **Can run in parallel with:** Prompt 3

--- START PROMPT 4 ---

You are working on the Chess CoachAI Vue 3 migration. The Vue project is set up in `frontend/` with Vue Router, Pinia, and vue-i18n.

TASK: Build the feedback modal, site controls (language toggle, theme toggle), and chess board rendering component.

Read the existing implementation first:
- `web/templates/partials/controls.html` — all JS for theme, language, feedback modal, console capture

WHAT TO BUILD:

### Part A: Console Log Capture Plugin

Create `frontend/src/plugins/consoleCapture.js`:
- Must run EARLY, before any other code
- Intercept `console.log`, `console.warn`, `console.error` — store originals, wrap them to also push to a buffer
- Capture `window.onerror` and `unhandledrejection` events
- Intercept `fetch()` to log failed requests (status >= 400)
- Log page context on init: URL, user agent, screen size, viewport, theme, language
- Log page timing from `performance.timing` on load
- Buffer max 100 entries (FIFO), each entry: `{ts: ISO timestamp, level: 'log'|'warn'|'error', msg: string}`
- Export `getConsoleLogs()` function that returns the buffer
- Install this in `main.js` BEFORE mounting the app

### Part B: Site Controls

Create `frontend/src/components/controls/LanguageToggle.vue`:
- Two buttons: EN / FR
- Active button has background var(--ctrl-active-bg)
- On click: update vue-i18n locale, save to localStorage('lang'), set document.documentElement.lang
- Height 28px, border-radius 6px, border 1px solid var(--border)
- Buttons: padding 0 8px, no border, transparent background, 0.75rem font, cursor pointer
- i18n keys: none (buttons are just "EN" and "FR" text)

Create `frontend/src/components/controls/ThemeToggle.vue`:
- Single 28px square button with sun/moon SVG icons
- Uses the Pinia theme store to toggle dark mode
- Sun icon visible in light mode, moon in dark mode
- Border-radius 6px, border 1px solid var(--border), cursor pointer

Create `frontend/src/components/controls/SiteControls.vue`:
- Flex row with gap 6px containing: LanguageToggle, ThemeToggle, FeedbackButton (a simple button that emits 'open-feedback')
- Feedback button: 28px square, border-radius 6px, contains a chat bubble SVG icon

### Part C: Feedback Modal

Create `frontend/src/components/FeedbackModal.vue`:
- Props: `modelValue` (boolean, v-model for open/close)
- Emits: `update:modelValue`

STRUCTURE:
- Overlay: fixed inset 0, z-index 1000, background rgba(0,0,0,0.5), flex center
- Card: max-width 480px, background var(--card-bg), border-radius 16px, padding 32px, max-height 90vh overflow-y auto
- Close button (×): absolute top-right 16px, 28px square

FORM FIELDS:
- Type select: "Bug report" / "Contact us" (keys: feedback_bug_report, feedback_contact)
- Screenshot section (visible only when type=bug):
  - Capture button: full-width, dashed border, blue text "Attach screenshot automatically"
  - Preview: border, border-radius 8px, max-height 200px, object-fit contain
  - Loading indicator: "Capturing screenshot..." text
- Email input: full-width, border-radius 8px, padding 10px 12px
- Details textarea: full-width, min-height 100px, resize vertical
- Error message (hidden by default): color var(--error), 0.85rem
- Submit button: full-width, blue background, white text, border-radius 8px, font-weight 700

SUCCESS STATE:
- Hide form, show success message with ✓ icon and "Thank you!" text
- Auto-close after 2 seconds

LOGIC:
- `captureScreenshot()`: Lazy-load html2canvas from CDN (https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js). Use it to capture viewport at scale 0.5, excluding the modal overlay. Store as data URL.
- Email validation: regex `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`
- Save email to localStorage('feedback_email') on submit, restore on open
- POST to `/api/feedback` with: `{type, email, details, screenshot, page_url: window.location.href, console_logs: JSON.stringify(getConsoleLogs())}`
- Console logs only sent for bug type

INTERACTIONS:
- Escape key closes modal
- Clicking overlay (not card) closes modal (use mousedown guard to prevent text-selection-drag from closing)
- Form resets on open

i18n keys: feedback_title, feedback_type_label, feedback_bug_report, feedback_contact, feedback_screenshot_btn, feedback_screenshot_loading, feedback_email, feedback_details, feedback_submit, feedback_success, feedback_error_email, feedback_error_details, feedback_error_generic

### Part D: AnalyzeForm Reusable Component

Create `frontend/src/components/forms/AnalyzeForm.vue`:
- This form is used in TWO places: the landing page (full size) and the status page retry section (compact)
- Props: `chesscomUser` (string, default ''), `lichessUser` (string, default ''), `compact` (boolean, default false), `errorKeys` (array, default [])
- Emits: `submit` with {chesscomUser, lichessUser} payload
- Contains:
  - Chess.com username input (using BaseInput with chess piece prefix icon)
  - Lichess username input (using BaseInput with lichess prefix icon)
  - Error message display (from errorKeys prop — renders translated errors using i18n keys error_account_not_found, error_invalid_username)
  - Client-side validation error (i18n: error_msg — "at least one username")
  - Submit button (using BaseButton variant='primary')
- Compact mode: inputs in a single row, smaller padding, smaller text
- Full mode: two-column row, larger padding, 32px card padding
- On submit: validates at least one username, emits 'submit' event with values (the PARENT handles the API call and navigation)
- Pre-fills inputs from props (for retry form on status page)
- i18n keys: label_chesscom, label_lichess, submit_btn, error_msg, error_account_not_found, error_invalid_username

### Part E: Chess Board Component + Board Loader

Create `frontend/src/components/ChessBoard.vue`:
- Props: `fen` (string), `move` (string, UCI notation), `color` ('white'|'black'), `arrowColor` (string, default ''), `size` (number, default 200)
- This component renders chess board SVGs by calling the backend API

BEHAVIOR:
- On mount (and when props change), add this board to a batch queue
- Use a debounced batch loader: collect all pending board requests, then POST to `/u/{userPath}/api/render-boards` with the specs array
- Display a loading spinner while waiting
- Once SVG is returned, render it via `v-html`

The batch loader should be a composable `frontend/src/composables/useBoardLoader.js`:
- Maintains a queue of pending board requests
- Debounces 50ms then fires a single POST with all pending specs
- Returns SVGs to the requesting components via callbacks or reactive refs
- Needs `userPath` from the route params

LOADING STATE:
- Show "Loading board…" text (i18n key: loading_board) with a small spinner
- Board slot: text-align center, inline-block

### Part F: Infinite Scroll Composable

Create `frontend/src/composables/useInfiniteScroll.js`:
- Takes: `items` (ref to full array), `pageSize` (number, default 10)
- Returns: `visibleItems` (computed, first N items), `loadMore()` (adds pageSize more), `reset()` (back to first page)
- Listens for scroll events: when within 200px of document bottom, calls loadMore()
- Cleans up scroll listener on unmount
- Used by openings, endgames, and endgames_all pages

### Part G: Update App.vue

Update `frontend/src/App.vue` to include the FeedbackModal at the app root level:
```vue
<template>
  <FeedbackModal v-model="feedbackOpen" />
  <router-view />
</template>
```
Provide `feedbackOpen` via a simple `provide/inject` or a tiny Pinia store so any SiteControls button can open it.

--- END PROMPT 4 ---

---

### Prompt 5: Landing, No Games, and Status Pages

**Depends on:** Prompts 1, 2, 3, 4 | **Can run in parallel with:** Prompts 6, 7, 8

--- START PROMPT 5 ---

You are working on the Chess CoachAI Vue 3 migration. The project is in `frontend/` with Vue Router, Pinia, vue-i18n, and shared components (AppHeader, SimpleLayout, SiteControls, FeedbackModal) already built.

TASK: Build the Landing page, No Games page, and Status page. These are the three "simple layout" pages (no sidebar).

Read the existing templates first:
- `web/templates/landing.html`
- `web/templates/no_games.html`
- `web/templates/status.html`

### Page 1: LandingPage.vue (`frontend/src/views/LandingPage.vue`)

STRUCTURE:
- Uses SimpleLayout
- Hero section: background var(--bg-secondary), centered flex column, 140px top padding
  - Badge: "Powered by Stockfish 16" (i18n: badge), inline-flex, border-radius 9999px, 6px vertical padding, font-size 0.75rem, background var(--badge-bg), color var(--badge-text)
  - h1: Two lines (i18n: hero_line1, hero_line2), font-size 2.5rem, font-weight 800
  - Subtitle paragraph (i18n: subtitle), max-width 520px, color var(--text-secondary)
- Form card: max-width 560px, background var(--card-bg), box-shadow, padding 32px, border-radius 16px, margin-top 32px
  - Uses the **AnalyzeForm** component (from `frontend/src/components/forms/AnalyzeForm.vue`) in full (non-compact) mode
  - Pass `errorKeys` from server response
- Responsive: at 768px, inputs stack vertically, h1 reduces to 2rem

LOGIC:
- Handle AnalyzeForm's `@submit` event:
  1. Call `submitAnalysis(formData)` from the API module (POSTs to `/analyze` with `Accept: application/json`)
  2. On success: response contains `{redirect: "/u/{path}/status"}` — use `router.push()` to navigate
  3. On validation error: response contains `{error_keys: [{key, platform, username}, ...]}` — pass to AnalyzeForm's `errorKeys` prop (the form handles display)

### Page 2: NoGamesPage.vue (`frontend/src/views/NoGamesPage.vue`)

STRUCTURE:
- Uses SimpleLayout
- Centered card (max-width 480px, padding 48px, border-radius 16px, box-shadow) containing:
  - **EmptyState** component with icon="♘", title=nogames_title, description=nogames_desc, actionLabel=nogames_try_another, actionTo="/"
  - Additional paragraph below for hint text (i18n: nogames_hint)
  - Username display using **UserBadges** component

LOGIC:
- Receives username info via route query params (`?chesscom=...&lichess=...`) or route state
- Display chesscom_user and/or lichess_user

### Page 3: StatusPage.vue (`frontend/src/views/StatusPage.vue`)

STRUCTURE:
- Uses SimpleLayout
- Header right: "← Back to Home" link (i18n: back_home)
- Centered status card: max-width 480px, border-radius 16px, padding 40px, text-align center
  - Spinner div: 48px, border animation (rotate 360deg, 1s linear infinite)
  - Success icon (✓, green) and Error icon (✗, red) — hidden by default, shown on complete/failed
  - Status title (h2) and message (p) — updated dynamically
  - Queue position text (i18n: status_queue_position, parameterized with {0} and {1})
  - Progress bar: 8px height, var(--progress-bg) background, blue fill with width transition
  - Progress text: percentage + message
  - Elapsed time display (i18n: status_elapsed)
  - Error detail box (hidden unless failed)
  - "View Report" link (hidden until complete)
  - Retry form (hidden unless failed/not_found) — uses **AnalyzeForm** component in `compact` mode, pre-filled with `chesscomUser`/`lichessUser` props

LOGIC — this is the most complex page:
- On mount: start polling `fetchStatusJson(userPath)` every 3 seconds (use setTimeout, not setInterval)
- Handle 6 states: pending, fetching, analyzing, complete, failed, not_found
  - `pending`: pulsing card animation, queued title/msg, show queue position if available
  - `fetching`: spinner, fetching title/msg, progress bar + percentage, elapsed time
  - `analyzing`: spinner, analyzing title/msg, progress bar + percentage, elapsed time
  - `complete`: hide spinner, show ✓ icon, complete title/msg with elapsed, show "View Report" link, auto-redirect after 1 second via `router.push('/u/' + userPath)`
  - `failed`: hide spinner, show ✗ icon, failed title/msg, show error detail if present, show retry form
  - `not_found`: hide spinner, show ✗ icon, not_found title/msg, show retry form
- `formatElapsed(seconds)`: convert to human-readable (Xs, M:SS, H:MM:SS)
- Translate server progress messages: Create `frontend/src/utils/translateMessage.js` — a function that pattern-matches server messages like "Analyzing game 5/120..." and returns translated equivalents. Read the `_tMsg()` function in `web/templates/partials/controls.html` (around line 310-340) and port ALL regex patterns. This function takes a message string and the current `$t` function, and returns the translated string.
- Cancel on unmount: if status is still 'pending', send `navigator.sendBeacon()` to cancel endpoint (`/u/{userPath}/status/cancel`)
- Pulsing animation on card: `@keyframes pulse` with box-shadow glow effect when pending

i18n keys for this page: back_home, retry_btn, status_preparing, status_please_wait, status_queued_title, status_queued_msg, status_queue_position, status_fetching_title, status_fetching_msg, status_analyzing_title, status_analyzing_msg, status_complete_title, status_complete_msg, status_failed_title, status_failed_msg, status_checking_title, status_checking_msg, status_elapsed, status_not_found_title, status_not_found_msg, status_pct_complete, and all the status_fetching_*/status_fetched_*/status_*_done/status_analysis_done/status_no_games/status_all_cached keys used by _tMsg.

--- END PROMPT 5 ---

---

### Prompt 6: Openings Page

**Depends on:** Prompts 1, 2, 3, 4 | **Can run in parallel with:** Prompts 5, 7, 8

--- START PROMPT 6 ---

You are working on the Chess CoachAI Vue 3 migration. The project is in `frontend/` with shared components already built: AppLayout (with sidebar), TheSidebar, SidebarFilters, ChessBoard, useInfiniteScroll, useFiltering, and the Pinia filter store.

TASK: Build the Openings report page — the most complex page in the app.

Read the existing template first:
- `web/templates/openings.html` — full HTML, CSS, and JS

### OpeningsPage.vue (`frontend/src/views/OpeningsPage.vue`)

DATA FETCHING:
- On mount, call `fetchOpeningsReport(userPath)` from the API module
- If response has `redirect`, use `router.push()` to navigate
- If response has `no_games`, redirect to no-games page with query params
- Store response data in a local ref
- If route has `eco` and `color` params, call the filtered endpoint instead

STRUCTURE (using AppLayout with TheSidebar):

**Header section:**
- h1 with username
- **UserBadges** component: Chess.com and Lichess links (pass chesscomUser, lichessUser)
- If `filter_eco` is set: subtitle shows "Showing {count} deviations for {eco} as {color}" (i18n: opening_deviations_for, parameterized)
- Sort dropdown using **BaseSelect**: options "Biggest mistake" / "Loss %" (i18n: sort_biggest, sort_losspct) — updates filter store sort value

**Stats bar:**
- 4 **StatCard** components in a flex row (flex-wrap for mobile):
  1. StatCard label=stat_total_games, value=total_games_analyzed
  2. StatCard label=stat_avg_eval, value="±X.X" (from avg_eval_loss)
  3. StatCard label=stat_theory, value=theory_knowledge_pct + "%"
  4. StatCard label=stat_accuracy, donut=true, donutPct=accuracy_pct
- New games badge: below stats bar, shows "{count} new game(s) analyzed" or "No new games to analyze" (i18n: stat_new_games_analyzed, stat_new_games_analyzed_plural, stat_no_new_games)

**Card list (filtered + paginated):**
- Use `useFiltering` composable to filter `items` based on Pinia filter store
- Use `useInfiniteScroll` composable to paginate filtered items (10 per page)
- Auto-escalation on first visit: if no filter state restored from sessionStorage AND filtered results are empty, automatically enable 'bullet' TC, then 'daily' TC if still empty (same logic as current template)

Each **Opening Card** — create `frontend/src/components/openings/OpeningCard.vue`:
- Props: the full item object + userPath
- Article element with border-left 4px solid #f97316
- **Card header row (flex, space-between, wrap):**
  - Left: ECO name (bold), ECO code badge (small, background var(--badge-bg)), color indicator "as white/black" (i18n: opening_as)
  - Right: **EvalBadge** for eval loss (type from eval_loss_class), **EvalBadge** for position eval, win/loss percentage text
- **Boards section (two inline-block panels):**
  - "Best:" label (i18n: board_best) + ChessBoard component (fen, best_move_uci, color, arrowColor='#22c55e' green)
  - "You played:" label (i18n: board_played) + ChessBoard component (fen, played_move_uci, color, arrowColor='#ef4444' red)
- **Meta section:**
  - Move label (e.g., "Move 15.") + best_san displayed
  - Book moves: "Book moves: Nc3, Na3" (i18n: opening_book_moves)
  - Times played badge: "{N} played" (i18n: opening_times_played)
- **Recommendation box:**
  - Green background (#f0fdf4 light / #052e16 dark), green text
  - "Play {best} instead of {played}" (i18n: opening_play_instead, parameterized with {best} and {played})
- **Game link (if available):**
  - "view example game" (i18n: opening_view_game) — external link to game_url

**Empty states** (use **EmptyState** component):
- When no items at all: EmptyState icon="♘" title=empty_title description=empty_desc
- When items exist but filters hide all: EmptyState title=no_filter_results

CSS — replicate from openings.html:
- Cards: max-width 100%, padding 24px, margin-bottom 24px, border-radius 12px, background var(--card-bg), border-left 4px solid #f97316
- Stat cards: flex 1, min-width 120px, padding 20px, background var(--card-bg), border-radius 12px
- Eval badges: inline-block, padding 2px 8px, border-radius 4px, font-size 0.8rem, font-weight 600
  - .bad: background #fef2f2, color #dc2626 (light) / background #450a0a, color #fca5a5 (dark)
  - .good: background #f0fdf4, color #16a34a (light) / background #052e16, color #86efac (dark)
- Board panels: inline-block, text-align center, margin 0 12px
- Recommendation: padding 12px 16px, border-radius 8px, margin-top 12px
- Responsive: at 768px, boards stack vertically

SORTING:
- "Biggest mistake": sort by eval_loss_raw descending
- "Loss %": sort by loss_pct descending
- Applied after filtering, before pagination

--- END PROMPT 6 ---

---

### Prompt 7: Endgames Pages

**Depends on:** Prompts 1, 2, 3, 4 | **Can run in parallel with:** Prompts 5, 6, 8

--- START PROMPT 7 ---

You are working on the Chess CoachAI Vue 3 migration. Shared components (AppLayout, TheSidebar, ChessBoard, useInfiniteScroll, useFiltering, filter store) are built.

TASK: Build the Endgames summary page and the Endgames All (drilldown) page.

Read the existing templates first:
- `web/templates/endgames.html`
- `web/templates/endgames_all.html`

### Page 1: EndgamesPage.vue (`frontend/src/views/EndgamesPage.vue`)

DATA FETCHING:
- On mount, call `fetchEndgamesReport(userPath)` from the API module
- Handle redirects and error states same as openings page

STRUCTURE (using AppLayout with TheSidebar):

**Header:**
- h1 with username + **UserBadges** component (same as openings)
- Subtitle: "Endgame performance" (i18n: eg_performance) + sort dropdown (**BaseSelect**)

**Sort dropdown options:**
- Games (i18n: eg_sort_games) — sort by total desc
- Win % (i18n: eg_sort_win_pct) — sort by win_pct desc
- Loss % (i18n: eg_sort_loss_pct) — sort by loss_pct desc
- Draw % (i18n: eg_sort_draw_pct) — sort by draw_pct desc

**Stats bar:**
- 3 **StatCard** components + 1 donut:
  1. StatCard label=eg_stat_games, value=eg_total_games
  2. StatCard label=eg_stat_types, value=eg_types_count
  3. StatCard label=eg_stat_winrate, donut=true, donutPct=eg_win_pct

**Endgame Card list (filtered + paginated):**

Each **EndgameCard** — create `frontend/src/components/endgames/EndgameCard.vue`:
- Props: stat object + userPath
- Card with border-left 4px (color varies by balance: green=#22c55e for up, red=#ef4444 for down, gray=#94a3b8 for equal)
- **Header row:**
  - Type label (e.g., "R vs R"), bold
  - Balance badge: "equal"/"up"/"down" with background color
  - Game count: "{N} games" (i18n: eg_games_suffix)
  - W/L/D percentages with color coding (green/red/gray)
  - Optional clock display: "you: M:SS / opp: M:SS" when filtered data includes clocks
- **Body:**
  - ChessBoard component showing example position
  - "Example game" heading (i18n: eg_example_game)
  - Example game link (external)
  - "show all games" link → router-link to `/u/{userPath}/endgames/all?def={definition}&type={type}&balance={balance}` (i18n: eg_show_all)

FILTERING (more complex than openings):
The endgames page does CLIENT-SIDE cross-filtering. Each stat has embedded `game_details_json` (per-game breakdown) and `example_candidates_json`.

When filters change:
1. Parse `game_details_json` for each stat (it's a JSON string, parse it once on load)
2. Filter the per-game details by platform, time_class, color, date
3. Recompute W/L/D counts and percentages from filtered games
4. Update displayed percentages on the card
5. If game details include clock data, recompute average clocks for filtered games
6. Pick a new example from `example_candidates_json` that matches the active filters (use `pickExample` logic from endgames.html — it picks the first candidate that matches active time controls, platform, and color)
7. Update the board and example link

Create a composable `frontend/src/composables/useEndgameFiltering.js` that handles this cross-filtering logic. It should:
- Take the stats array and the filter store
- Return filtered stats with recomputed W/L/D percentages
- Handle example candidate selection based on active filters
- Auto-escalate TC on first visit (same as openings)

**Empty states** (use **EmptyState** component):
- No endgames at all: EmptyState title=eg_no_endgames_title description=eg_no_endgames_desc
- Filters hide all: EmptyState title=eg_no_filter_results

### Page 2: EndgamesAllPage.vue (`frontend/src/views/EndgamesAllPage.vue`)

DATA FETCHING:
- Read query params: `def`, `type`, `balance`
- Call `fetchEndgamesAll(userPath, {def, type, balance})` from the API module

STRUCTURE (using AppLayout with TheSidebar, but `showFilters=false`):

**Header:**
- Back link: "← Back to endgames" (i18n: eg_back), router-link
- h1: endgame type name + balance badge
- Subtitle: game count + definition + "sorted by most recent" (i18n: eg_definition, eg_sorted_recent)

**Time class filter:**
- Use **DropdownFilter** component with label="Time class" (i18n: eg_time_class)
- Inside the dropdown panel, use **ToggleGroup** with options Bullet/Blitz/Rapid/Daily (i18n: tc_bullet, tc_blitz, tc_rapid, tc_daily), minSelected=0
- Changes trigger re-filtering of game list

**Game row list (filtered + paginated):**

Each game row (inline in the page, no separate component needed):
- Flex layout: board on left (ChessBoard with fen, no move, my_color), info on right
- Game info:
  - Result badge (use **EvalBadge** — win=good, loss=bad, draw=neutral), **EvalBadge** for material_diff
  - Clock badges if available: "you: M:SS" (green bg) / "opp: M:SS" (gray bg)
  - "view game" link (i18n: eg_view_game) — external deep_link
- Infinite scroll with PAGE_SIZE = 10

**Empty states** (use **EmptyState** component):
- No games match filters: EmptyState title=eg_no_games_filter
- No games at all: EmptyState title=eg_no_games_title description=eg_no_games_desc

CSS for endgames pages — replicate from templates:
- eg-card: border-left 4px, padding 20px 24px, margin-bottom 16px, border-radius 12px
- Game row: flex, gap 20px, align-items flex-start
- Result tags: win=#16a34a bg, loss=#dc2626 bg, draw=#94a3b8 bg, white text, padding 3px 10px, border-radius 4px

--- END PROMPT 7 ---

---

### Prompt 8: Admin Pages

**Depends on:** Prompts 1, 2 | **Can run in parallel with:** Prompts 5, 6, 7

--- START PROMPT 8 ---

You are working on the Chess CoachAI Vue 3 migration. Vue project is set up in `frontend/` with router and i18n.

TASK: Build the two admin pages. These are standalone dark-themed pages (no sidebar, no i18n — English only).

Read the existing templates:
- `web/templates/admin_jobs.html`
- `web/templates/admin_feedback.html`

### Page 1: AdminJobsPage.vue (`frontend/src/views/AdminJobsPage.vue`)

DATA FETCHING:
- On mount, call `fetchAdminJobs()` from the API module → `{jobs: [...]}`
- Auto-refresh: if any jobs have status 'pending' or 'fetching' or 'analyzing', reload data every 30 seconds (use setTimeout, clear on unmount)

STRUCTURE:

**Header:**
- h1: "Analysis Jobs"
- Action buttons row: "Feedback" (router-link to /admin/feedback), "Refresh" (reloads data)
- "Flask Logs" toggle button (shows/hides the flask logs panel)

**Flask Logs Panel (hidden by default):**
- Log level filter dropdown (ALL / ERROR / WARNING / INFO)
- Reload button
- `<pre>` block with log content, syntax colored by level
- Fetches via `fetchFlaskLogs({limit: 300, level})` from the API module
- Color code: ERROR=red (#f87171), WARNING=yellow (#fbbf24), INFO=green (#4ade80), DEBUG=gray

**Summary cards (5):**
- Use **StatCard** components (they work in admin dark theme too — override colors via scoped CSS or pass a `class` prop)
- Active (green), Queued (yellow), Complete (blue), Failed (red), Total (gray)
- Each shows count of jobs in that status
- Compute from jobs array client-side

**Filter tabs:**
- All / Active / Queued / Complete / Failed
- Click toggles active tab, filters table rows by status
- Default: All

**Jobs table:**
- Columns: ID, User, Status, Progress, Games, Duration, Created, Message
- Status badge: colored by status (active=green, pending=yellow, complete=blue, failed=red)
- Progress: mini progress bar (80px wide inline)
- Duration: computed from duration_seconds, format as "Xs" / "Xm Ys" / "Xh Ym"
- Created: formatted datetime
- User: show chesscom_user and/or lichess_user
- Clickable job ID: toggles a log detail row below

**Log detail rows:**
- Hidden by default, toggle on job ID click
- Lazy-loaded: on first toggle, call `fetchJobLogs(jobId)` from the API module
- Display log lines in `<pre>` with level-based coloring (same as flask logs)
- Monospace font, dark background #0c0f1a, max-height 400px scrollable

DARK THEME (always dark, independent of app theme):
- Background: #0f172a
- Card background: #1e293b
- Text: #e2e8f0
- Accent: #818cf8
- Table borders: #334155
- Don't use the app's CSS variable system — use scoped styles with hardcoded dark colors

Create `frontend/src/components/layout/AdminLayout.vue`:
- Dark-themed wrapper component
- Sets background #0f172a, min-height 100vh, color #e2e8f0
- Has header slot and main content slot

### Page 2: AdminFeedbackPage.vue (`frontend/src/views/AdminFeedbackPage.vue`)

DATA FETCHING:
- On mount, call `fetchAdminFeedback()` from the API module → `{entries: [...]}`

STRUCTURE:

**Header:**
- h1: "Feedback"
- Action buttons: "Jobs Dashboard" (router-link to /admin/jobs), "Refresh" (reloads data)

**Summary cards (3):**
- Use **StatCard** components (same as admin jobs page)
- Total, Bug Reports, Contact — counts from entries array

**Feedback table:**
- Columns: ID, Type, Email, Details, Page URL, Date, Actions
- Type badge: bug (red bg #450a0a) / contact (blue bg #172554)
- Details cell: max-width 350px, word-break break-word
- URL cell: max-width 200px, truncated, small font 0.8rem
- Actions: "Screenshot" toggle link (if screenshot exists), "Logs" toggle link (if console_logs exists and is not empty/`[]`)

**Expandable rows:**
- Screenshot row: shows `<img>` with the base64 screenshot data URL, max-width 100%, max-height 400px
- Logs row: parses console_logs JSON string on first toggle, renders each entry with level-based coloring in a `<pre>` block
  - Format: `[{ts, level, msg}]` → colored spans
  - Same coloring as flask logs panel

Same dark theme as AdminJobsPage (use AdminLayout).

--- END PROMPT 8 ---

---

### Prompt 9: Test Migration

**Depends on:** Prompts 1-8 | **Run alone**

--- START PROMPT 9 ---

You are working on the Chess CoachAI Vue 3 migration. The Vue SPA is complete in `frontend/`. Flask now has both old HTML routes AND new `/api/*` JSON routes.

TASK: Migrate and update all tests to work with the new architecture. There are two parts: updating the Python backend tests, and creating new frontend tests.

### Part A: Update Python backend tests

Read these files first:
- `tests/integration/test_web_routes.py`
- `tests/unit/test_web_reports.py`
- `tests/e2e/test_openings_scroll.py`

Here's exactly what to change in each:

**`tests/integration/test_web_routes.py`:**

KEEP UNCHANGED (these routes/behaviors haven't changed):
- `TestParseUserPath` — all tests
- `TestBuildUserPath` — all tests
- `TestRoundTrip` — all tests
- `TestCheckUsernameExists` — all tests
- `TestAnalyzeRedirects` — all tests (POST /analyze still returns 302s)
- `TestStatusJson` — all tests
- `TestStatusCancel` — all tests
- `TestAnalyzeDispatch` — all tests
- `TestSubmitFeedback` — all tests
- `TestAdminFlaskLogs` — all tests
- `TestAdminJobLogs` — all tests

MODIFY `TestAnalyzeValidation`:
- Add parallel test methods that send POST /analyze with `Accept: application/json` header
- Assert response is JSON with `error_keys` field instead of checking HTML content
- Keep existing HTML tests too (backward compat)
- New tests: `test_no_usernames_json`, `test_invalid_chesscom_username_json`, `test_valid_username_json_redirect`

MODIFY `TestAnalyzeAccountExists`:
- Add JSON variants: send with Accept: application/json, assert error_keys contains account-not-found key

REPLACE `TestUserReport`:
- Instead of testing HTML content, test the new JSON API endpoints
- `test_no_job_returns_redirect_json`: GET /api/report/openings/hikaru → `{"redirect": "/"}`
- `test_complete_returns_report_json`: GET /api/report/openings/hikaru → JSON with items, groups, stats
- `test_in_progress_returns_redirect_json`: → `{"redirect": "/u/hikaru/status"}`
- `test_zero_games_returns_no_games_json`: → `{"no_games": true, ...}`

REPLACE `TestAdminFeedback`:
- Test GET /api/admin/feedback instead of HTML page
- `test_returns_entries_json`: Assert JSON shape with entries array
- `test_entries_include_fields`: Assert each entry has id, type, email, details, etc.
- Remove HTML-specific tests (toggleLogs, HTML escaping — those are now frontend concerns)

ADD new `TestApiEndpoints` class:
- `test_openings_report_json_shape`: Verify all expected fields present
- `test_openings_filtered_by_eco_color`: GET /api/report/openings/hikaru/B90/white filters items
- `test_endgames_report_json`: Verify endgames data shape
- `test_endgames_all_json`: Verify with query params
- `test_admin_jobs_json`: GET /api/admin/jobs returns {jobs: [...]}
- `test_datetime_serialization`: Verify datetimes become ISO strings in JSON responses

**`tests/unit/test_web_reports.py`:**

KEEP UNCHANGED:
- All pure helper function tests (TestGroupDeviations, TestMoveToSan, TestFormatClock, TestPlyToMoveLabel, TestFormatDate, TestPrepareDeviation, TestGetOpeningGroups, TestRenderBoardSvg)
- TestLoadOpeningsData
- TestLoadEndgamesData
- TestAggregateEndgamesGameMeta
- TestRenderBoardsAPI

REPLACE these classes that test HTML rendering:
- `TestOpeningsRoute` → Test /api/report/openings JSON response instead
- `TestOpeningDetailRoute` → Test /api/report/openings/{path}/{eco}/{color} JSON filtering
- `TestEndgameRoutes` → Test /api/report/endgames and /api/report/endgames-all JSON

DELETE these (no longer relevant):
- `TestSyncButton` — sync button is a Vue component now
- `TestUbuntuFont` — font loading is in Vue's index.html now

**`tests/e2e/test_openings_scroll.py`:**

Mark all tests with `@pytest.mark.skip(reason="Pending Vue SPA E2E rewrite")` for now. These will need to be rewritten to test the Vue SPA, which requires a different setup (serving the built Vue app instead of rendering Jinja2 templates).

### Part B: Create frontend tests with Vitest

Set up the test infrastructure:

```bash
cd frontend
npm install -D vitest @vue/test-utils jsdom @pinia/testing
```

Create `frontend/vitest.config.js`:
```js
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
  },
})
```

Create `frontend/tests/setup.js`:
```js
import { vi } from 'vitest'
// Mock localStorage and sessionStorage
const storage = {}
global.localStorage = {
  getItem: vi.fn(key => storage[key] || null),
  setItem: vi.fn((key, val) => { storage[key] = val }),
  removeItem: vi.fn(key => { delete storage[key] }),
  clear: vi.fn(() => Object.keys(storage).forEach(k => delete storage[k])),
}
// Similar for sessionStorage
```

Add to `frontend/package.json` scripts:
```json
"test": "vitest",
"test:run": "vitest run"
```

Create these test files:

**`frontend/tests/stores/theme.test.js`:**
- Test `init()` reads from localStorage
- Test `init()` falls back to system preference (mock matchMedia)
- Test `toggle()` flips state and updates localStorage
- Test `toggle()` sets/removes data-theme attribute on documentElement

**`frontend/tests/stores/filters.test.js`:**
- Test default state values
- Test `saveToSessionStorage()` writes JSON to sessionStorage
- Test `restoreFromSessionStorage()` reads and applies saved state
- Test `restoreFromSessionStorage()` returns false when nothing saved
- Test `reset()` restores defaults
- Test that changing platform/TC/color triggers auto-save (via $subscribe)

**`frontend/tests/composables/useFiltering.test.js`:**
- Create mock items array with different platforms, time_classes, colors, dates, times_played
- Test platform filter: 'chesscom' only shows chesscom items
- Test time control filter: ['blitz'] only shows blitz items
- Test color filter: ['white'] only shows white items
- Test min games filter: minGames=5 hides items with times_played < 5
- Test date filter: dateFrom='2025-06-01' hides items before that date
- Test combined filters: multiple filters applied together
- Test sort by eval_loss_raw descending
- Test sort by loss_pct descending
- Test empty result when no items match

**`frontend/tests/composables/useInfiniteScroll.test.js`:**
- Test initial visibleItems is first pageSize items
- Test loadMore() adds pageSize more
- Test loadMore() caps at total items (never exceeds)
- Test reset() goes back to first page

**`frontend/tests/composables/useEndgameFiltering.test.js`:**
- Create mock stats with game_details_json containing mixed platforms/TCs
- Test filtering recomputes W/L/D percentages correctly
- Test filtering by platform only counts matching games
- Test example candidate selection picks matching candidate
- Test empty result when all games filtered out

**`frontend/tests/utils/translateMessage.test.js`:**
- Test "Analyzing game 5/120..." → translated equivalent
- Test "Fetching Chess.com games... (200/2280)" → translated
- Test "Fetched 200 Lichess games" → translated
- Test "Analysis complete: 500 games" → translated
- Test "Fetching Chess.com archive 3/12 (150 games)" → translated
- Test unknown message → returns original
- Test with French locale

**`frontend/tests/components/OpeningCard.test.js`:**
- Mount with mock item props
- Assert eco_name rendered
- Assert eval badges have correct CSS classes (bad/good)
- Assert recommendation text contains best_san and played_san
- Assert game link href is correct
- Assert ChessBoard components receive correct props

**`frontend/tests/views/StatusPage.test.js`:**
- Mock fetchStatusJson to return different statuses
- Test pending state shows spinner and queue position
- Test complete state shows success icon and triggers redirect
- Test failed state shows error and retry form
- Test formatElapsed(90) returns "1:30"
- Test formatElapsed(3661) returns "1:01:01"
- Test cleanup cancels polling on unmount

**`frontend/tests/views/LandingPage.test.js`:**
- Test form renders with both inputs
- Test client-side validation shows error when both inputs empty
- Test successful submit calls API and navigates
- Test server error displays translated error message

Run all tests:
```bash
cd frontend && npm run test:run
pytest
```

Fix any failures before considering this prompt complete.

--- END PROMPT 9 ---

---

### Prompt 10: Flask SPA Integration + Cleanup

**Depends on:** ALL previous prompts | **Run last**

--- START PROMPT 10 ---

You are working on the Chess CoachAI Vue 3 migration. The Vue SPA is complete in `frontend/` and all tests pass (both Python and frontend).

TASK: Wire up Flask to serve the Vue SPA, remove old HTML routes, and verify everything works.

### Part A: Build the Vue app

Run:
```bash
cd /c/Users/franc/OneDrive/Documents/chess_coachAI/frontend
npm run build
```

This outputs files to `static/dist/` (configured in vite.config.js). Verify the build succeeds and the output directory contains `index.html` and an `assets/` folder.

### Part B: Update Flask to serve the SPA

Read `web/routes.py` and `web/app.py` (or `app.py` at root) to understand how the Flask app is created and routes are registered.

Modify the Flask app to:

1. Serve static files from `static/dist/assets/` at `/assets/`:
```python
@app.route('/assets/<path:filename>')
def vue_assets(filename):
    return send_from_directory(os.path.join(app.root_path, '..', 'static', 'dist', 'assets'), filename)
```

2. Add a catch-all route that serves `static/dist/index.html` for any route that doesn't match an API endpoint:
```python
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith(('api/', 'analyze', 'u/', 'admin/')):
        # Let API routes handle these - if we got here, no API route matched
        from flask import abort
        abort(404)
    return send_from_directory(os.path.join(app.root_path, '..', 'static', 'dist'), 'index.html')
```

IMPORTANT: The catch-all must be registered AFTER all API routes. Vue Router handles client-side routing for `/u/*`, `/admin/*`, etc., but the Flask API routes under those same prefixes must still work. The catch-all is only for paths that don't match any API route.

Routes that need to stay because the SPA calls them:
- POST /analyze
- All /api/* routes
- POST /u/<user_path>/status/cancel
- GET /u/<user_path>/status/json
- POST /u/<user_path>/api/render-boards
- GET /admin/jobs/<int:job_id>/logs
- GET /admin/logs/flask

3. Remove these old HTML-serving routes:
- GET / (landing HTML — now served by catch-all → Vue SPA)
- GET /u/<user_path> (openings HTML)
- GET /u/<user_path>/opening/<eco>/<color> (filtered openings HTML)
- GET /u/<user_path>/endgames (endgames HTML)
- GET /u/<user_path>/endgames/all (endgames all HTML)
- GET /u/<user_path>/status (status page HTML)
- GET /admin/jobs (admin jobs HTML)
- GET /admin/feedback (admin feedback HTML)

### Part C: Mark old templates as deprecated

Add this comment at the top of each template file in `web/templates/` (including partials):
```
{# DEPRECATED: Replaced by Vue SPA in frontend/. Safe to delete after verification. #}
```

Do NOT delete the templates — the user will verify the Vue app works first.

### Part D: Update catch-all for SPA client-side routing

The SPA needs the catch-all to return index.html for ALL non-API paths, because Vue Router handles:
- `/` → LandingPage
- `/u/hikaru` → OpeningsPage
- `/u/hikaru/endgames` → EndgamesPage
- `/admin/jobs` → AdminJobsPage
- etc.

But Flask also has API routes under `/u/` and `/admin/`. The order matters:
1. Register ALL API routes first (they have specific patterns with methods)
2. Register the catch-all last

Review the route registration order and make sure API routes take priority.

### Part E: Run all tests and fix issues

```bash
# Backend tests
pytest -x

# Frontend tests
cd frontend && npm run test:run
```

If any test imports break because of removed routes, fix them. The tests updated in Prompt 9 should already be pointing at JSON API endpoints, but double-check.

### Part F: Update development workflow docs

Add a section to `CLAUDE.md` under Common Commands:
```
## Frontend Development
- `cd frontend && npm run dev` — Vue dev server with hot reload (port 5173, proxies API to Flask)
- `cd frontend && npm run build` — Build Vue SPA to static/dist/
- `cd frontend && npm run test` — Run frontend unit tests (Vitest)
- Production: Flask serves the built SPA from static/dist/
```

### Part G: Verify manually

Start the Flask server and confirm:
1. `http://localhost:5050/` serves the Vue SPA (check for `<div id="app">` in page source)
2. `http://localhost:5050/u/anyuser` serves the same index.html (Vue Router handles it)
3. `http://localhost:5050/u/anyuser/status/json` still returns JSON (not index.html)
4. `http://localhost:5050/api/report/openings/anyuser` returns JSON
5. `http://localhost:5050/assets/` serves JS/CSS bundles

--- END PROMPT 10 ---

---

## Notes

- **Don't commit between prompts** — the user will review and commit when ready
- **Each prompt can be pasted as-is** into a Claude Code agent conversation
- **Parallel execution** requires isolated worktrees (or at least non-overlapping files) — the dependency graph above shows what's safe to run in parallel
- **The old HTML routes stay alive** until Prompt 10 removes them, so the app keeps working throughout the migration
