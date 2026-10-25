# AccessAudit

**Lighthouse tells you a page has errors. AccessAudit tells you whether a blind person can actually book the ticket.**

AccessAudit tries to finish a real task on a website the way a disabled user would: keyboard only, listening to what a screen reader announces. It then shows exactly where the task gets stuck, which WCAG rule each barrier breaks, and how to fix it.

## Status

AccessAudit is being built in stages; this section is updated as each one lands. Commands in the rest of this README work only once their stage is done.

| Stage | What it adds | Status |
| --- | --- | --- |
| 0. Scaffold | Project layout, dependencies, `python -m backend.smoke` (all three TinyFish APIs verified) | ✅ Done |
| 1. Demo site | SkyRail broken and fixed copies (live on Vercel), `cli scan` | ✅ Done |
| 2. Audit engine | Keyboard walker, issues, scoring, `cli audit`, backend tests | ✅ Done |
| 3. API | Backend server, stored reports, live events, replays | ✅ Done |
| 4. Web app | Audit form, live view, report, PDF | ✅ Done |
| 5. Hardening | Real-site audits, golden runs that replay offline (the baseline cache is already built) | ⏳ In progress: stealth retry, clear error reasons and offline-safe replays done; waiting for the two real sites |
| 6. Extras | AI code fixes or a leaderboard | Not started |

## How an audit works

1. You enter a URL, a task in plain language (for example "Find the fee for B.Tech admission") and a persona (screen-reader user or keyboard-only user).
2. **Sighted baseline:** a TinyFish agent completes the task like a normal user. This proves the task is possible and records the path. You watch its browser live.
3. **Keyboard walker:** the same site opens in a TinyFish cloud browser, and our Playwright controller retries each step using only Tab, Shift+Tab, Enter, Space, arrow keys and typing. At every focus stop it records what a screen reader would announce.
4. **Page scan:** axe-core checks every page the walker visits.
5. **Report:** a verdict (Completed, Completed with barriers, Blocked at step N of M, or Inconclusive), a score out of 100, and a card for each barrier with a screenshot, what a screen reader heard (playable aloud), who it blocks, the WCAG criterion and a code fix. Reports can be shared as a link or downloaded as a PDF.

The agents never log in, pay, or submit a form that creates a record. The walker never activates a control whose name contains "pay", "submit", "confirm", "place order" or "book now".

## What it checks

| Barrier | How it's detected | WCAG | Severity |
| --- | --- | --- | --- |
| Control can't be reached by keyboard | The target exists but never takes focus in a full Tab cycle | 2.1.1 Keyboard | Blocker |
| Keyboard trap | Focus loops among 3 or fewer elements | 2.1.2 No Keyboard Trap | Blocker |
| Control ignores Enter or Space | No URL, page or state change after activation | 2.1.1 Keyboard | Blocker |
| Control with no accessible name | The screen reader announces only its role, e.g. "button" | 4.1.2 Name, Role, Value | Critical |
| Form field without a label | axe-core `label` | 1.3.1, 4.1.2 | Critical |
| Focus not visible | No outline or box-shadow on the focused element | 2.4.7 Focus Visible | Serious |
| Low-contrast text | axe-core `color-contrast` | 1.4.3 Contrast | Serious |
| Image without alt text | axe-core `image-alt` | 1.1.1 Non-text Content | Serious |
| Focus jumps back up the page | On the same page, the next focus stop is more than 400 px above the last (not counting the wrap back to the top) | 2.4.3 Focus Order | Moderate |
| Page language missing | axe-core `html-has-lang` | 3.1.1 Language of Page | Moderate |

Every other WCAG 2.0/2.1 A and AA violation axe-core finds is reported too, with axe's own impact level. The report also notes whether the site links an accessibility statement (not scored).

## Scoring

```
Score = max(0, min(G, 100 − Σ weight(severity) × min(count, 3)))
```

- **G** is 100 if the keyboard walker completed the task, and 40 if it was blocked. A site where a keyboard user can't finish the task never scores above 40.
- **Weights per instance:** Blocker 25, Critical 10, Serious 5, Moderate 2. Each issue counts at most 3 times, so one repeated error can't sink the score on its own.
- If the sighted baseline can't finish the task, nothing is scored and the verdict is Inconclusive.

The weights are our own choice, not a standard.

## How TinyFish is used

| TinyFish feature | Job in AccessAudit |
| --- | --- |
| Agent API (`/run-sse`) | Sighted baseline: completes the task and returns its steps as structured JSON via `output_schema`, with each element's exact label (which the walker matches) and a plain-English description of the step (which the report shows) |
| Agent live stream (`STREAMING_URL` event) | Embedded live view of the agent's browser while the baseline runs |
| Browser API (remote Chromium over CDP) | Runs the keyboard walker and the axe-core scans, driven by Playwright; the session is deleted after every audit |
| Fetch API | Reads the home page to check for an accessibility statement link |

Every site an audit visits must be on a public URL, because TinyFish's cloud browsers can't reach `localhost`.

**Cost per audit (measured):** about $0.21 with a live Agent baseline (Agent about $0.016 per step; Browser about $0.002 per minute), and about $0.002 when the baseline steps are hand-checked or cached.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer, with npm
- A TinyFish API key ([docs.tinyfish.ai](https://docs.tinyfish.ai/))

## Setup

The commands below are for Windows PowerShell, run from the repo root. On macOS or Linux, activate the environment with `source .venv/bin/activate`.

**1. Configuration**

```powershell
Copy-Item .env.example .env
# then edit .env and set TINYFISH_API_KEY
"NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File -Encoding utf8 frontend\.env.local
```

**2. Backend**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
playwright install chromium
```

Chromium is only used locally, for rendering PDFs and for development mode. Audits themselves run in TinyFish cloud browsers. axe-core is already included at `backend/vendor/axe.min.js`.

**3. Frontend**

```powershell
cd frontend
npm install
```

## Running

**Backend** (port 8000), from the repo root with the environment active:

```powershell
uvicorn backend.app:app --port 8000
```

On Windows, don't use `--reload`; it can break Playwright's async API.

**Frontend** (port 3000), in a second terminal:

```powershell
cd frontend
npm run dev
```

Open http://localhost:3000, pick a preset or enter a URL and task, and press **Run audit**.

**Command-line tools** (from the repo root):

| Command | What it does |
| --- | --- |
| `python -m backend.smoke [agent] [browser] [fetch]` | Checks that your key works with each TinyFish API (default: all three) |
| `python -m backend.cli scan <url>` | Runs only the axe-core scan on one page |
| `python -m backend.cli audit <url> "<task>" [--override]` | Runs a full audit in the terminal and prints every event and the final report. `--override` uses the hand-checked baseline steps instead of the agent's |
| `python -m backend.ws_client <url> "<task>"` | With the backend running: starts an audit through the API, prints its live events, and checks the saved report and replay |
| `python -m pytest backend/tests` | Runs the backend tests (these never call TinyFish) |

The Agent and Browser APIs use TinyFish credits; the tests and `WALKER_MODE=local` don't.

## Configuration

All settings live in `.env` at the repo root (see `.env.example`).

| Variable | Default | Meaning |
| --- | --- | --- |
| `TINYFISH_API_KEY` | | Your TinyFish key |
| `WALKER_MODE` | `tinyfish` | `local` runs the walker in a local Chromium, for development only |
| `TF_BROWSER_PROXY` | `default` | `direct` connects Browser sessions without TinyFish's proxy (try this if a site blocks the default US exit) |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed origin for the API, and the page rendered into PDFs |
| `DATA_DIR` | `./data` | Database, screenshots, replays, cached baselines and PDFs |
| `FORCE_BASELINE_OVERRIDE` | `0` | `1` uses hand-checked steps even when the agent succeeds |
| `CACHE_BASELINES` | `1` | `1` reuses a saved agent baseline for the same URL and exact task (no agent call, no live stream); set `0` to see the live stream every time |
| `ANTHROPIC_API_KEY`, `LLM_MODEL` | | Optional, for AI-generated code fixes |

## Demo site: SkyRail

SkyRail is a fictional train-booking site in two copies, built to show the difference between a broken and an accessible flow. It's plain HTML, CSS and JavaScript in `demo-site/`.

- **Task:** "Find trains, select the first train, and enter the passenger name Asha Verma."
- **`broken/`:** no page language, an image without alt text, low-contrast text, an unnamed icon button, invisible focus, and a date strip that traps keyboard focus. Expected result: "Blocked at step 2 of 3", score 40 or below.
- **`fixed/`:** the same flow with every barrier fixed. Expected result: "Completed", score 90 or above.

Public URLs:

- Broken: https://skyrail-demo.vercel.app/broken/index.html
- Fixed: https://skyrail-demo.vercel.app/fixed/index.html

To redeploy after changing the site, run `npx vercel@latest --prod` from `demo-site/`.

## Replays

Every audit's events are saved, so any finished audit can be replayed with its original timing at `/audit/{id}?replay=1`. A replay needs no network or TinyFish credits.

## Project layout

```text
backend/     FastAPI app, audit orchestrator, TinyFish clients, keyboard walker, axe-core scan, scoring
  baselines/ hand-checked step files for the demo site
  vendor/    axe.min.js
  tests/     pytest tests and small HTML fixtures
frontend/    Next.js app: audit form, live view, report, PDF print view
demo-site/   SkyRail, broken and fixed copies
data/        runtime output (git-ignored)
```

## Limitations

- AccessAudit is a fast first pass that produces evidence. It doesn't replace testing by people who use assistive technology.
- The walker follows the steps the sighted agent took. If the agent records a label that isn't on the page, the audit ends as Inconclusive rather than blaming the site.
- Both personas currently use the same keyboard walker; the persona is shown in the report.
- Audits only visit public pages, run one at a time, and never log in or submit forms.
