# Hermes KVM Lecture System

A minimal FastAPI starter for the Hermes-controlled classroom lecture presenter.

## Phase 1H status

Phase 1H provides:

- Basic FastAPI application
- Static files folder mounted at `/static`
- Tailwind CSS loaded on the presenter page
- Reveal.js sample lecture with teleprompter and manual Previous/Next controls
- Admin login form protected by configurable `ADMIN_PASSWORD`
- Bcrypt password hashing at application startup
- HTTP-only browser session cookie after login
- Unique `SESSION_CODE` for each authenticated session
- Protected `/` page
- Protected `/health` endpoint
- Protected `/api/session` endpoint
- Protected `notes/` folder on the server
- Protected `GET /api/notes/{filename}` endpoint for markdown notes
- Protected `POST /api/start-lecture` endpoint for accepting `title`, `slides`, and `narration`
- In-memory lecture session storage keyed to the current `SESSION_CODE`
- Protected WebSocket endpoint at `/ws/session` for presenter control state
- Protected Telegram webhook/direct command endpoint at `/api/telegram-command`
- Telegram command support for start lecture, begin lecture, pause, resume, end, and help
- Native Telegram webhook response shape for returning the presenter link/message to Telegram
- Prominent on-screen Pause / Resume button wired through WebSockets
- Live/Paused status badge on the presenter page
- Logout button

## Configure the admin password

Set `ADMIN_PASSWORD` before starting the server. Example:

```bash
export ADMIN_PASSWORD='choose-a-long-private-password'
```

Set `TELEGRAM_WEBHOOK_SECRET` to protect the Telegram command endpoint. Use a different long private value from the admin password:

```bash
export TELEGRAM_WEBHOOK_SECRET='choose-a-second-long-private-secret'
```

If `TELEGRAM_WEBHOOK_SECRET` is not set, `/api/telegram-command` stays disabled and returns `503`.

If `ADMIN_PASSWORD` is not set, the development fallback password is:

```text
change-me
```

Do not use the fallback password on the KVM or any network-exposed deployment.

## Local / KVM setup

```bash
git clone https://github.com/krewten-978/hermes-kvm-lecture-system.git
cd hermes-kvm-lecture-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you already cloned an earlier phase, update instead:

```bash
cd hermes-kvm-lecture-system
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
```

## Run with uvicorn

For KVM testing:

```bash
export ADMIN_PASSWORD='choose-a-long-private-password'
export TELEGRAM_WEBHOOK_SECRET='choose-a-second-long-private-secret'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For laptop-only testing:

```bash
export ADMIN_PASSWORD='test-password'
export TELEGRAM_WEBHOOK_SECRET='test-telegram-secret'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open:

- Presenter page: `http://YOUR_SERVER_IP:8000/`
- Laptop presenter page: `http://127.0.0.1:8000/`
- Health check: `http://YOUR_SERVER_IP:8000/health`

## Markdown notes

Markdown note files live in the protected server-side `notes/` folder. They are not mounted as public static files.

A sample file is included:

```text
notes/sample-photosynthesis.md
```

After logging in through the browser, fetch it at:

```text
http://127.0.0.1:8000/api/notes/sample-photosynthesis.md
```

The endpoint returns JSON with the note filename, markdown content, and active session code. Only `.md` files inside `notes/` are readable.

To add your own notes on the KVM later, copy markdown files into the `notes/` folder, for example:

```bash
nano notes/my-lecture.md
```

Then read them at:

```text
/api/notes/my-lecture.md
```

## Start a lecture through the API

After logging in, `POST /api/start-lecture` accepts JSON with `title`, `slides`, and `narration`. The lecture payload is stored in memory for the authenticated browser session's `SESSION_CODE`.

Example using curl after saving login cookies:

```bash
curl -i -c /tmp/lecture-cookies.txt \
  -d 'password=your-admin-password' \
  http://127.0.0.1:8000/login

curl -s -b /tmp/lecture-cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"title":"Cell Energy","slides":[{"heading":"ATP","body":"Cells store usable energy in ATP."}],"narration":["Introduce ATP as the cell energy molecule."]}' \
  http://127.0.0.1:8000/api/start-lecture
```

The response includes the presenter `url`, active `session_code`, accepted `title`, and `slide_count`.

For now, lecture payloads are stored in memory only. Restarting the server or logging out clears them.

## Presenter pause/resume control

The protected presenter page opens an authenticated WebSocket connection to:

```text
/ws/session
```

The on-screen **Pause Lecture** button sends a WebSocket control message and changes the presenter state to **Paused**. The same button then becomes **Resume Lecture** and can switch the state back to **Live**. The status badge near the bottom-left of the presenter shows the current state.

## Telegram command handling

Phase 1H adds a protected command endpoint:

```text
POST /api/telegram-command
```

The endpoint accepts either direct JSON such as:

```json
{"text":"Start lecture on Cell Energy using notes/sample-photosynthesis.md"}
```

or a normal Telegram webhook update with `message.text` and `message.chat.id`.

Protection options:

- Direct tests or Hermes-side calls: send `X-Hermes-Telegram-Secret: your-secret`
- Native Telegram webhooks: configure Telegram's `secret_token`; Telegram sends it as `X-Telegram-Bot-Api-Secret-Token`

Example direct command test after the presenter is open and logged in:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: your-secret' \
  -d '{"text":"Start lecture on Cell Energy using notes/sample-photosynthesis.md"}'
```

Supported commands:

- `Start lecture on <topic>`
- `Start lecture on <topic> using notes/<filename>.md`
- `Begin lecture`
- `Pause lecture`
- `Resume lecture`
- `End lecture`
- `Help`

Important: open the presenter page and log in first. Telegram commands target the newest active presenter `SESSION_CODE`. If there is no active presenter session, the command response asks you to open and log in to the presenter first.

To configure a Telegram webhook later, use your real bot token and public HTTPS URL:

```bash
curl -s "https://api.telegram.org/bot[REDACTED]/setWebhook" \
  -d "url=https://YOUR_PUBLIC_DOMAIN/api/telegram-command" \
  -d "secret_token=your-secret"
```

## Phase 1H test checklist

- Open `/` and confirm you are redirected to `/login` if not logged in.
- Log in with your `ADMIN_PASSWORD`.
- Confirm the presenter page still loads after login.
- Confirm the top-left badge says `Phase 1H` and shows a `Session` code.
- Confirm the teleprompter and Previous/Next controls still work.
- Confirm a **Live** status badge appears near the bottom-left.
- Send `Start lecture on Cell Energy using notes/sample-photosynthesis.md` to `/api/telegram-command` with the correct secret and confirm the response includes a presenter URL and session code.
- Send `Begin lecture` and confirm the response says the lecture began; the presenter status should change to **Running**.
- Send `Pause lecture` and confirm the presenter button changes to **Resume Lecture** and the status badge changes to **Paused**.
- Send `Resume lecture` and confirm the presenter status changes back to **Running**.
- Send `End lecture` and confirm the presenter status changes to **Ended**.
- Click the on-screen **Pause Lecture** / **Resume Lecture** button and confirm it still works.
- Open `/api/notes/sample-photosynthesis.md` after login and confirm it still returns JSON with markdown content.
- Send a logged-in `POST /api/start-lecture` request with `title`, `slides`, and `narration`; confirm it still returns JSON with `url`, `session_code`, `title`, and `slide_count`.
- Click **Logout** and confirm `/` requires login again.

## Notes

Telegram commands now connect to the presenter control state. Rendering dynamic lecture payloads in the presenter remains intentionally left for the final polish phase per the phased development plan.
