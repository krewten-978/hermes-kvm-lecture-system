# Hermes KVM Lecture System

A FastAPI + Reveal.js classroom lecture presenter for Wayne's high-school classroom.

Current status: Phase 2D complete.

Phase 2D adds timing-control support to the existing Phase 2 parser and autonomous lecture task. Markdown slide headings can now include `{{wait}}` or `{{pause-autopilot}}`; the marker is stripped from the displayed heading, the slide receives `wait: true`, and autopilot stays on that slide until a manual or Hermes next-slide command advances it. WebSocket state messages now include timing fields for the current slide.

Phase 2D does not add the lecture-status API yet and does not update the sample Markdown lecture. Those are later Phase 2 sub-phases.

Repository:

```text
https://github.com/krewten-978/hermes-kvm-lecture-system
```

## What the app currently does

The app currently includes:

- Protected login with `ADMIN_PASSWORD`
- A full-screen Reveal.js sample lecture
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

Important current limitations:

- The presenter still shows the existing Phase 1 sample slide deck.
- Telegram note-start integration is still scheduled for Phase 2F.
- The lecture-status API is not added yet. That is Phase 2E.
- Lecture state is still stored in memory. Restarting the server clears the active session.

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

## Phase 2D test checklist

Complete these tests on the laptop before moving to Phase 2E.

### 1. Confirm the app starts and login still works

Expected result:

- Uvicorn starts without errors.
- The browser opens `http://127.0.0.1:8000/`.
- Login with `test-password` succeeds.
- The sample lecture appears.
- The badge says `Phase 2D`.

### 2. Confirm automatic slide advance still works

Open a second terminal window in the same project folder and run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"Begin lecture"}'
```

Expected result:

- The presenter status changes to Running.
- A normal slide advances automatically after about 5 seconds.
- The Pause / Resume button and Telegram `Pause lecture` / `Resume lecture` commands still work.
- The Previous / Next buttons still move slides manually through the backend WebSocket state.

### 3. Confirm Phase 2D parser wait markers

Open a second terminal window in the project folder and run:

```bash
source .venv/bin/activate
python3 - <<'PY'
from app.main import build_lecture_from_md

markdown = """# Cell Energy

## Overview
Cells need energy to do work.

## Teacher Checkpoint {{wait}}
Ask students to predict what happens next.

## Video Example {{pause-autopilot}}
{{youtube:dQw4w9WgXcQ}}
"""

lecture = build_lecture_from_md("Cell Energy", markdown)
slides = lecture["slides"]

assert len(slides) == 3
assert slides[0]["heading"] == "Overview"
assert slides[0]["wait"] is False
assert slides[1]["heading"] == "Teacher Checkpoint"
assert slides[1]["wait"] is True
assert "{{wait}}" not in slides[1]["heading"]
assert slides[2]["heading"] == "Video Example"
assert slides[2]["wait"] is True
assert "{{pause-autopilot}}" not in slides[2]["heading"]
assert all(isinstance(slide["duration"], int) for slide in slides)

print("Phase 2D parser wait-marker checks passed.")
PY
```

Expected result:

```text
Phase 2D parser wait-marker checks passed.
```

### 4. Confirm wait slides stop autopilot in backend state

Run:

```bash
source .venv/bin/activate
python3 - <<'PY'
import asyncio
import importlib
import os

os.environ["LECTURE_SLIDE_SECONDS"] = "0.05"
import app.main as main
main = importlib.reload(main)

class FakeWebSocket:
    def __init__(self):
        self.messages = []
    async def send_json(self, message):
        self.messages.append(message)

async def run_check():
    _session_id, session_code = main.create_session()
    websocket = FakeWebSocket()
    main.WEBSOCKET_CONNECTIONS[session_code] = [websocket]
    main.LECTURE_SESSIONS[session_code] = {
        "title": "Wait Test",
        "slides": [
            {"heading": "Fast", "duration": 0.05, "wait": False},
            {"heading": "Stop Here", "duration": 0.05, "wait": True},
            {"heading": "After Wait", "duration": 0.05, "wait": False},
            {"heading": "Extra", "duration": 0.05, "wait": False},
            {"heading": "Done", "duration": 0.05, "wait": False},
        ],
        "narration": [],
    }
    main.LECTURE_RUNTIME_STATE[session_code] = "running"
    main.LECTURE_CONTROL_STATE[session_code] = False
    main.LECTURE_SLIDE_INDEX[session_code] = 0

    task = asyncio.create_task(main.auto_advance_lecture(session_code))
    await asyncio.sleep(0.2)
    assert main.LECTURE_SLIDE_INDEX[session_code] == 1
    assert any(message.get("is_waiting") is True for message in websocket.messages)

    await main.advance_lecture_slide(session_code, 1)
    await asyncio.sleep(0.12)
    assert main.LECTURE_SLIDE_INDEX[session_code] >= 2

    main.LECTURE_RUNTIME_STATE[session_code] = "ended"
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

asyncio.run(run_check())
print("Phase 2D wait-slide autopilot checks passed.")
PY
```

Expected result:

```text
Phase 2D wait-slide autopilot checks passed.
```

### 5. Confirm WebSocket timing fields exist

The backend now includes these fields in WebSocket control messages:

```text
is_waiting
duration_remaining
slide_duration
```

Expected result during the checks above:

- Normal slides report `is_waiting: false` and a countdown-style `duration_remaining`.
- Wait slides report `is_waiting: true` and do not auto-advance until a next-slide command moves the lecture forward.

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
Phase 2D tested — proceed to Phase 2E
```

If something does not work, report:

- Which step failed
- What you expected to happen
- What actually happened
- Any error text shown in the browser or terminal

Do not proceed to Phase 2E until Phase 2D is tested successfully.
