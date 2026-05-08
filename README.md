# Hermes KVM Lecture System

A FastAPI + Reveal.js classroom lecture presenter for Wayne's high-school classroom.

Current status: Phase 2F complete with Phase 2F retest fixes for presenter-session targeting.

Phase 2F wires the Phase 2 Markdown parser into Telegram/direct lecture-start commands, updates the sample Photosynthesis note with image, YouTube, and wait-marker examples, renders parsed note slides on the presenter page, and documents the Phase 2 Markdown syntax. The Phase 2F retest fix also keeps direct curl commands attached to the visible browser presenter when a separate curl login is used for `/api/lecture-status`.

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

Important current limitations:

- Lecture state is stored in memory. Restarting the server clears the active session.
- Student participation features such as polls, student questions, and knowledge checks are prepared in slide data structures but are not active student UI features yet.
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

## Phase 2F test checklist

Complete these tests on the laptop before moving to Phase 3.

### 1. Confirm the app starts and login still works

Expected result:

- Uvicorn starts without errors.
- The browser opens `http://127.0.0.1:8000/`.
- Login with `test-password` succeeds.
- The browser shows a one-slide `No lecture loaded` placeholder, not the old 5-slide Photosynthesis sample deck.
- The badge says `Phase 2F`.

### 2. Start the enhanced sample note through the command endpoint

Open a second terminal window in the same project folder and run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"Start lecture on Photosynthesis using notes/sample-photosynthesis.md"}'
```

Expected result:

- The JSON response says the lecture is ready.
- Refresh `http://127.0.0.1:8000/` in the browser if it does not reload automatically.
- The presenter now renders slides from `notes/sample-photosynthesis.md`.
- The slide deck includes the local image from `media/images/photosynthesis-overview.svg`.
- The deck includes the embedded YouTube slide.
- The YouTube iframe URL includes autoplay parameters; most browsers require it to start muted.
- The Teacher Checkpoint slide does not show the raw `{{wait}}` marker in its heading.

### 3. Begin the lecture and confirm timing / wait behavior

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"Begin lecture"}'
```

Expected result:

- The presenter status changes to Running.
- Normal slides advance automatically after about 5 seconds.
- The Teacher Checkpoint wait slide stays on screen.
- Pressing the browser Next button or sending `Next slide` moves past the wait slide.
- When the presenter reaches the YouTube slide, autonomous advancement pauses so students have time to watch.
- Send `Resume lecture` after the video discussion/watch time to continue automatic timing from that slide.

To test the command version of manual advance, run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"Next slide"}'
```

### 4. Confirm the lecture-status API sees the parsed lecture

Run:

```bash
curl -s -c /tmp/kvm-lecture-cookies.txt \
  -d 'password=test-password' \
  http://127.0.0.1:8000/login >/dev/null

curl -s -b /tmp/kvm-lecture-cookies.txt http://127.0.0.1:8000/api/lecture-status
```

Expected result:

- The status JSON includes `current_slide_index`, `current_slide`, `is_paused`, `wait_mode`, `time_on_slide_seconds`, `total_slides`, and `media_on_slide`.
- On an image or YouTube slide, `media_on_slide` identifies the media item.
- On the Teacher Checkpoint slide, `wait_mode` is `true`.

### 5. Confirm pause, resume, and end still work

Run each command as needed:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"Pause lecture"}'

curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"Resume lecture"}'

curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"End lecture"}'
```

Expected result:

- Pause stops automatic advancement.
- Resume restarts automatic advancement on the visible browser presenter, even after the separate `/api/lecture-status` curl login above.
- If the current slide is the Teacher Checkpoint wait slide, Resume will return the deck to running state but will intentionally keep waiting there until you use `Next slide` or the browser Next button.
- End marks the lecture ended and stops autopilot.

### 6. Confirm source files are not exposed through media URLs

Open this address:

```text
http://127.0.0.1:8000/media/../app/main.py
```

Expected result:

- The app should not show the Python source file.
- A `404 Not Found` response is expected.

## Stopping the app

Return to the terminal window running Uvicorn and press:

```text
Ctrl+C
```

## What to report back

If every item above works, reply:

```text
Phase 2F tested — proceed to Phase 3
```

If something does not work, report:

- Which step failed
- What you expected to happen
- What actually happened
- Any error text shown in the browser or terminal

Do not proceed to Phase 3 until Phase 2F is tested successfully.
