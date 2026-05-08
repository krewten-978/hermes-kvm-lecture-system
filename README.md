# Hermes KVM Lecture System

A FastAPI + Reveal.js classroom lecture presenter for Wayne's high-school classroom.

Current status: Phase 3A complete.

Phase 3A adds the student session and connection foundation for live participation. Students can join an active presenter session with the session code through `POST /api/join`, receive a student token, and connect to `/ws/student`. The presenter WebSocket and `/api/lecture-status` now include `student_count` while all Phase 1 and Phase 2 presenter, Markdown, media, timing, and command behavior remains in place.

Repository:

```text
https://github.com/krewten-978/hermes-kvm-lecture-system
```

## What the app currently does

The app currently includes:

- Protected login with `ADMIN_PASSWORD`
- A full-screen Reveal.js presenter
- A large teleprompter panel
- Previous / Next slide buttons that sync with backend lecture state
- Pause / Resume lecture control
- WebSocket updates for presenter control state
- Autonomous slide advance after the `Begin lecture` command
- Protected markdown notes in `notes/`
- Protected direct command endpoint at `/api/telegram-command`
- Protected start-lecture endpoint at `/api/start-lecture`
- Phase 2A media folder serving at `/media`
- Phase 2B safe media filename-to-URL resolver
- Phase 2C enhanced Markdown parser function: `build_lecture_from_md(title, content)`
- Phase 2D wait markers and per-slide duration support in autopilot state
- Phase 2E protected lecture-status API at `/api/lecture-status`
- Phase 2F Telegram note-start integration using the enhanced parser
- Phase 2F parsed Markdown slide rendering on the presenter page
- Phase 3A student join endpoint at `POST /api/join`
- Phase 3A student WebSocket endpoint at `/ws/student`
- Phase 3A student connection count in presenter WebSocket messages and `/api/lecture-status`

Important current limitations:

- Lecture state is stored in memory. Restarting the server clears the active session.
- Student participation Phase 3A currently tracks joined/connected students only. Student-facing pages, questions, polls, knowledge checks, and dashboards come in later Phase 3 sub-phases.
- The presenter initially shows the built-in sample deck until a Markdown lecture is started through `/api/telegram-command` or a compatible payload is posted to `/api/start-lecture`.

## Requirements for laptop testing

You need:

- Python 3.11 or newer
- Git
- A terminal
- A web browser

Python packages are listed in `requirements.txt`:

```text
fastapi==0.115.12
uvicorn[standard]==0.34.2
bcrypt==4.3.0
```

## First-time laptop setup

Use these steps if you do not already have the project folder on your laptop.

```bash
git clone https://github.com/krewten-978/hermes-kvm-lecture-system.git
cd hermes-kvm-lecture-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `python3 -m venv .venv` fails, install Python from https://www.python.org/downloads/ and try again.

## Updating an existing laptop copy

Use these steps if the project is already cloned on your laptop.

```bash
cd hermes-kvm-lecture-system
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
```

If the app is already running, stop it first with `Ctrl+C`, update it, and then start it again.

## Start the app on your laptop

Use this command when you are testing in a browser on the same laptop that is running the app.

```bash
cd hermes-kvm-lecture-system
source .venv/bin/activate
export ADMIN_PASSWORD='test-password'
export TELEGRAM_WEBHOOK_SECRET='test-telegram-secret'
export LECTURE_SLIDE_SECONDS='5'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep this terminal window open while testing. If you close it or press `Ctrl+C`, the app stops.

Open this address in your browser:

```text
http://127.0.0.1:8000/
```

Log in with:

```text
test-password
```

The command above uses `LECTURE_SLIDE_SECONDS='5'` so that automatic slide advance can be tested quickly. For normal classroom pacing later, use a larger value such as `75`.

## Phase 2 Markdown syntax

Markdown remains the single source of truth for note-driven lectures.

### Slides

Each level-two heading starts a slide:

```markdown
## Big Idea
Plants convert light energy into chemical energy stored as glucose.
```

### Local images

Use image tokens with filenames only:

```markdown
{{image:photosynthesis-overview.svg}}
```

Media naming convention:

- Put teacher-provided images in `media/images/`.
- Reference only the filename in Markdown.
- Use kebab-case names such as `cell-energy-diagram.png` or `photosynthesis-overview.svg`.
- Do not use paths, raw URLs, `..`, or leading slashes in image tokens.

### YouTube videos

Use YouTube video IDs only:

```markdown
{{youtube:UPBMG5EYydo}}
```

The parser turns the token into an embedded YouTube iframe. YouTube slides autoplay muted when the browser allows it and pause autonomous advancement when the slide appears. After students have had time to watch, use `Resume lecture` to continue automatic timing.

### Wait markers

Add a wait marker on a slide heading when autopilot should stop until a manual Next command:

```markdown
## Teacher Checkpoint {{wait}}
Pause here and ask students to answer before moving on.
```

The app also accepts:

```markdown
## Discussion Pause {{pause-autopilot}}
```

Wait behavior:

- Normal slides advance after their `duration`.
- Wait slides stay on screen until the presenter presses Next or Hermes sends `Next slide`.
- Wait markers are stripped from the visible slide heading.
- `/api/lecture-status` reports `wait_mode: true` while the lecture is on a wait slide.

## Phase 3A test checklist

Complete these tests on the laptop before moving to Phase 3B.

### 1. Confirm the app starts and login still works

Expected result:

- Uvicorn starts without errors.
- The browser opens `http://127.0.0.1:8000/`.
- Login with `test-password` succeeds.
- The browser shows a one-slide `No lecture loaded` placeholder if no Markdown lecture has been started.
- The badge says `Phase 3A` and shows the presenter session code.

### 2. Confirm a student can join with the session code

Use the session code shown in the presenter badge. In a second terminal, replace `ABC123` below with that code:

```bash
curl -s -X POST http://127.0.0.1:8000/api/join \
  -H 'Content-Type: application/json' \
  -d '{"session_code":"ABC123"}'
```

Expected result:

- The response returns the normalized `session_code`.
- The response includes a `student_token`.
- A bad or made-up session code returns `404` instead of joining a lecture.

### 3. Confirm connected students are counted

After a student joins, use the returned `student_token` to open a student WebSocket. One simple command-line test is:

```bash
python - <<'PY'
import json
import sys
import websocket

token = sys.argv[1] if len(sys.argv) > 1 else 'PASTE_STUDENT_TOKEN_HERE'
ws = websocket.create_connection(f'ws://127.0.0.1:8000/ws/student?token={token}')
print(json.dumps(json.loads(ws.recv()), indent=2))
input('Student socket is connected. Press Enter to disconnect...')
ws.close()
PY
```

Expected result:

- The first WebSocket message has `type: student_state`.
- The message includes the correct `session_code`.
- While the socket is connected, the presenter control state reports `student_count: 1`.

If the `websocket` Python package is not installed on your laptop, you can skip this command-line socket test and use the API/status test below for this phase.

### 4. Confirm `/api/lecture-status` includes student count

Run:

```bash
curl -s -c /tmp/kvm-lecture-cookies.txt \
  -d 'password=test-password' \
  http://127.0.0.1:8000/login >/dev/null

curl -s -b /tmp/kvm-lecture-cookies.txt http://127.0.0.1:8000/api/lecture-status
```

Expected result:

- The status JSON still includes Phase 2 fields such as `current_slide_index`, `current_slide`, `wait_mode`, `total_slides`, and `media_on_slide`.
- The status JSON now also includes `student_count`.
- Existing presenter controls, Markdown lecture start commands, media, wait slides, and pause/resume behavior still work.

### 5. Confirm invalid student WebSocket tokens are rejected

Open this WebSocket path with an invalid token if you have a WebSocket tool available:

```text
ws://127.0.0.1:8000/ws/student?token=bad-token
```

Expected result:

- The connection is rejected.
- The presenter WebSocket at `/ws/session` is unaffected.

## Stopping the app

Return to the terminal window running Uvicorn and press:

```text
Ctrl+C
```

## What to report back

If every item above works, reply:

```text
Phase 3A tested — proceed to Phase 3B
```

If something does not work, report:

- Which step failed
- What you expected to happen
- What actually happened
- Any error text shown in the browser or terminal

Do not proceed to Phase 3B until Phase 3A is tested successfully.
