# Hermes KVM Lecture System

FastAPI + Reveal.js classroom lecture presenter for Wayne's high-school classroom. The app runs on a laptop or KVM/VPS, shows full-screen slides with a large teleprompter, and accepts protected command calls for starting, beginning, pausing, resuming, and ending a lecture.

## Phase 1I status

Phase 1I is the final polish/documentation phase for the Phase 1 build. The application currently includes:

- FastAPI web application
- Reveal.js presenter view
- Tailwind-loaded dark classroom display styling
- Hardcoded sample Photosynthesis deck
- Large bottom teleprompter panel
- Previous / Next presenter buttons
- Prominent Pause / Resume button
- Autonomous slide advancement after `Begin lecture` with a configurable pace (`LECTURE_SLIDE_SECONDS`, default 75 seconds)
- WebSocket `slide_advance` events that keep the presenter slides and teleprompter synchronized
- Presenter status badge: Live, Running, Paused, Ended, or disconnected
- Configurable admin password with bcrypt hashing
- Login form and HTTP-only session cookie
- Unique six-character session code for each authenticated browser session
- Protected `/`, `/health`, `/api/session`, `/api/notes/{filename}`, and `/api/start-lecture` routes
- Protected `/ws/session` WebSocket endpoint for presenter state
- Protected `/api/telegram-command` endpoint for Telegram-shaped webhooks and direct curl/Hermes command calls
- Protected server-side `notes/` folder for markdown lecture notes
- In-memory lecture payload and runtime state storage
- Full deployment, notes, password, and control examples in this README

Phase 1 is intentionally minimal. Lecture payloads and runtime state are stored in memory only. Restarting the server or logging out clears the active session state. Student interactivity, TTS, persistent databases, automatic slide generation, and Phase 2 features are intentionally not included.

## Repository

```text
https://github.com/krewten-978/hermes-kvm-lecture-system
```

## Requirements

- Python 3.11+
- `git`
- Network access from the presenter browser to the machine running uvicorn

Python packages are pinned in `requirements.txt`:

```text
fastapi==0.115.12
uvicorn[standard]==0.34.2
bcrypt==4.3.0
```

## First-time setup

```bash
git clone https://github.com/krewten-978/hermes-kvm-lecture-system.git
cd hermes-kvm-lecture-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Updating an existing install

```bash
cd hermes-kvm-lecture-system
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
```

If uvicorn is already running, stop it with `Ctrl+C`, update with the commands above, then start it again with the run command below.

## Password and secret setup

Set an admin password before starting the server:

```bash
export ADMIN_PASSWORD='choose-a-long-private-password'
```

Set a separate Telegram/direct-command secret before starting the server:

```bash
export TELEGRAM_WEBHOOK_SECRET='choose-a-second-long-private-secret'
```

Optionally set the autonomous slide pace before starting the server. The default is 75 seconds, which is inside the intended 60-90 second natural classroom pace:

```bash
export LECTURE_SLIDE_SECONDS='75'
```

Use two different values. Do not reuse the admin password as the Telegram command secret.

If `ADMIN_PASSWORD` is not set, the development fallback password is:

```text
change-me
```

Do not use the fallback password on the KVM, classroom network, or any network-exposed deployment.

If `TELEGRAM_WEBHOOK_SECRET` is not set, `/api/telegram-command` is disabled and returns `503`.

## Running the app

### Laptop-only testing

Use this when the browser and curl command are on the same laptop:

```bash
cd hermes-kvm-lecture-system
source .venv/bin/activate
export ADMIN_PASSWORD='test-password'
export TELEGRAM_WEBHOOK_SECRET='test-telegram-secret'
export LECTURE_SLIDE_SECONDS='75'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

### Laptop on your LAN

Use this when the presenter page or curl command needs to reach your laptop from another device on the same network:

```bash
cd hermes-kvm-lecture-system
source .venv/bin/activate
export ADMIN_PASSWORD='test-password'
export TELEGRAM_WEBHOOK_SECRET='test-telegram-secret'
export LECTURE_SLIDE_SECONDS='75'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find your laptop IP address:

macOS:

```bash
ipconfig getifaddr en0
```

Linux:

```bash
hostname -I
```

Windows PowerShell:

```powershell
ipconfig
```

Open the presenter with your real LAN IP:

```text
http://YOUR_LAPTOP_IP:8000/
```

Example:

```text
http://192.168.254.41:8000/
```

### KVM / VPS testing

SSH to the KVM and run:

```bash
cd hermes-kvm-lecture-system
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD='choose-a-long-private-password'
export TELEGRAM_WEBHOOK_SECRET='choose-a-second-long-private-secret'
export LECTURE_SLIDE_SECONDS='75'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open from a browser that can reach the KVM:

```text
http://YOUR_KVM_IP:8000/
```

## Basic presenter workflow

1. Start uvicorn.
2. Open the presenter URL in the browser.
3. Log in with `ADMIN_PASSWORD`.
4. Confirm the top-left badge says `Phase 1I` and shows a session code.
5. Use Previous / Next to move through slides manually.
6. Use the on-screen Pause / Resume button or command endpoint to control the lecture state.
7. Use Logout when finished.

## Markdown notes

Markdown files live in the protected server-side `notes/` folder. They are not public static files.

A sample note file is included:

```text
notes/sample-photosynthesis.md
```

To add a note file on the KVM:

```bash
cd hermes-kvm-lecture-system
nano notes/my-lecture.md
```

Save the file with a `.md` extension.

After logging in through the browser, you can fetch a note file with:

```text
http://127.0.0.1:8000/api/notes/sample-photosynthesis.md
```

Or with a LAN/KVM IP:

```text
http://YOUR_SERVER_IP:8000/api/notes/sample-photosynthesis.md
```

The endpoint returns JSON:

```json
{
  "filename": "sample-photosynthesis.md",
  "content": "...markdown content...",
  "session_code": "ABC123"
}
```

Only `.md` files inside `notes/` are readable. Missing files, non-markdown files, and path traversal attempts return `404`.

## Start a lecture with `/api/start-lecture`

This endpoint is protected by the browser login cookie. It accepts a lecture payload and stores it in memory for the current session code.

First log in and save cookies:

```bash
curl -i -c /tmp/lecture-cookies.txt \
  -d 'password=your-admin-password' \
  http://127.0.0.1:8000/login
```

Then post a lecture:

```bash
curl -s -b /tmp/lecture-cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"title":"Cell Energy","slides":[{"heading":"ATP","body":"Cells store usable energy in ATP."}],"narration":["Introduce ATP as the cell energy molecule."]}' \
  http://127.0.0.1:8000/api/start-lecture
```

Expected response shape:

```json
{
  "url": "http://127.0.0.1:8000/",
  "session_code": "ABC123",
  "title": "Cell Energy",
  "slide_count": 1
}
```

Current Phase 1 behavior: this stores the lecture payload in memory and returns the presenter URL/session details. It does not persist the payload across restarts.

## Telegram/direct command endpoint

Phase 1I includes the protected command endpoint:

```text
POST /api/telegram-command
```

The endpoint accepts direct JSON for curl/Hermes tests:

```json
{"text":"Start lecture on Cell Energy using notes/sample-photosynthesis.md"}
```

It also accepts normal Telegram webhook-shaped JSON containing `message.text` and `message.chat.id`.

Authentication headers:

- Direct curl/Hermes calls: `X-Hermes-Telegram-Secret: your-secret`
- Native Telegram webhook calls: `X-Telegram-Bot-Api-Secret-Token: your-secret`

Important: open the presenter page and log in first. Commands target the newest active presenter session unless a direct JSON payload includes a valid `session_code`.

## Direct command examples with curl

Replace these values:

- `YOUR_SERVER_IP` with `127.0.0.1`, your laptop LAN IP, or your KVM IP
- `your-secret` with the value of `TELEGRAM_WEBHOOK_SECRET`

Start / prepare a lecture:

```bash
curl -s -X POST http://YOUR_SERVER_IP:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: your-secret' \
  -d '{"text":"Start lecture on Cell Energy using notes/sample-photosynthesis.md"}'
```

Begin:

```bash
curl -s -X POST http://YOUR_SERVER_IP:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: your-secret' \
  -d '{"text":"Begin lecture"}'
```

Expected behavior: the presenter status changes to `Running`, and the server begins broadcasting autonomous slide advances over `/ws/session`. With the default setting, the current five-slide presenter deck advances every 75 seconds. To test faster, restart uvicorn with a shorter temporary value such as `export LECTURE_SLIDE_SECONDS='5'`.

Pause:

```bash
curl -s -X POST http://YOUR_SERVER_IP:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: your-secret' \
  -d '{"text":"Pause lecture"}'
```

Resume:

```bash
curl -s -X POST http://YOUR_SERVER_IP:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: your-secret' \
  -d '{"text":"Resume lecture"}'
```

End:

```bash
curl -s -X POST http://YOUR_SERVER_IP:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: your-secret' \
  -d '{"text":"End lecture"}'
```

Help:

```bash
curl -s -X POST http://YOUR_SERVER_IP:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: your-secret' \
  -d '{"text":"Help"}'
```

Supported command text:

- `Start lecture on <topic>`
- `Start lecture on <topic> using notes/<filename>.md`
- `Begin lecture`
- `Pause lecture`
- `Resume lecture`
- `End lecture`
- `Help`

## Native Telegram webhook setup

This step requires a real Telegram bot token and a public HTTPS URL. Do not put the bot token in GitHub, screenshots, or classroom displays.

Set the webhook:

```bash
curl -s "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
  -d "url=https://YOUR_PUBLIC_DOMAIN/api/telegram-command" \
  -d "secret_token=your-secret"
```

Check webhook info:

```bash
curl -s "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
```

The `secret_token` value must match the app's `TELEGRAM_WEBHOOK_SECRET`.

## WebSocket presenter control

The presenter page opens this protected WebSocket after login:

```text
/ws/session
```

It receives control state broadcasts from:

- On-screen Pause / Resume button
- `/api/telegram-command` begin, pause, resume, and end commands
- The server-side autonomous slide-advance task started by `Begin lecture`

The status badge updates to show Live, Running, Paused, Ended, or disconnected. While Running, the browser applies `slide_advance` messages from the server to move Reveal.js to the next slide and refresh/scroll the teleprompter. Pause stops advancing; Resume restarts it; End cancels the autonomous task.

## Health and session checks

These endpoints require the login cookie.

Health:

```text
GET /health
```

Expected authenticated response:

```json
{"status":"ok","session_code":"ABC123"}
```

Session:

```text
GET /api/session
```

Expected authenticated response:

```json
{"session_code":"ABC123"}
```

Unauthenticated requests return `401` or redirect to `/login`, depending on whether the route is a browser page or an API endpoint.

## Troubleshooting

### The presenter opens on the laptop but not from another device

Start uvicorn with `--host 0.0.0.0`, not `--host 127.0.0.1`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Also check the laptop firewall and confirm both devices are on the same network.

### Curl returns `401`

The Telegram/direct command secret is missing or wrong. Confirm the value used when starting uvicorn:

```bash
echo "$TELEGRAM_WEBHOOK_SECRET"
```

Then send the same value in the header:

```text
X-Hermes-Telegram-Secret: your-secret
```

### Curl returns `503`

`TELEGRAM_WEBHOOK_SECRET` was not set when uvicorn started. Stop uvicorn, export the secret, then start uvicorn again.

### Command response says no active presenter session

Open the presenter page and log in first. Then rerun the command.

### Browser status says control disconnected

Refresh the presenter page. If it still happens, confirm uvicorn is running and the browser can reach `/ws/session` on the same host and port.

### Notes file returns `404`

Confirm the file exists inside `notes/`, has a `.md` extension, and the command references it as `notes/filename.md`.

### State disappears after restart

That is expected in Phase 1. Sessions, lecture payloads, and lecture state are in memory only.

## Classroom test checklist

After deploying Phase 1I:

- Open `/` and confirm unauthenticated users are redirected to `/login`.
- Log in with `ADMIN_PASSWORD`.
- Confirm the presenter loads and the top-left badge says `Phase 1I`.
- Confirm a session code appears.
- Confirm Previous / Next slide controls work.
- Confirm teleprompter text changes with slides.
- Confirm the on-screen Pause / Resume button works.
- Confirm `/health` works after login and returns the session code.
- Confirm `/api/notes/sample-photosynthesis.md` works after login.
- Use curl to send `Start lecture on Cell Energy using notes/sample-photosynthesis.md` to `/api/telegram-command`.
- Confirm the response includes `ok: true`, a presenter URL, a session code, and `state: ready`.
- Send `Begin lecture` and confirm the presenter status changes to Running.
- Wait for the configured interval and confirm the presenter automatically moves to the next slide without pressing Next.
- Confirm the teleprompter updates to the current slide's notes and slowly scrolls while Running.
- Send `Pause lecture` and confirm the presenter status changes to Paused and slide movement stops.
- Send `Resume lecture` and confirm the presenter status changes back to Running.
- Send `End lecture` and confirm the presenter status changes to Ended.
- Log out and confirm `/` requires login again.

## Security notes

- Keep `ADMIN_PASSWORD`, `TELEGRAM_WEBHOOK_SECRET`, and Telegram bot tokens private.
- Do not commit secrets to GitHub.
- Use HTTPS before exposing the app publicly.
- Treat this Phase 1 build as a minimal controlled classroom tool, not a multi-user public application.
- In-memory state is convenient for Phase 1 testing but not durable.

## Phase 1 completion summary

Phase 1A through Phase 1I produce a minimal protected classroom lecture presenter that can be deployed, opened on a classroom display, and controlled through browser controls or protected Telegram/direct command calls.

Future Phase 2 ideas, if requested later, could include generated slide rendering from markdown, persistent storage, richer autonomous pacing, TTS, student interactivity, or production process management. Those features are intentionally outside Phase 1.
