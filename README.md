# Hermes KVM Lecture System

A FastAPI + Reveal.js classroom lecture presenter for Wayne's high-school classroom.

Current status: Phase 2C complete.

Phase 2C adds an enhanced Markdown parser function for future lecture generation. The parser can split Markdown into slide objects, recognize simple local image tokens, recognize YouTube video tokens, produce HTML for slide bodies, collect media metadata, and preserve the original Markdown in the lecture payload.

Phase 2C does not yet wire this parser into Telegram lecture-start commands, does not change the visible sample lecture content, does not add wait-marker timing behavior, and does not add the lecture-status API. Those are later Phase 2 sub-phases and should not be expected during this test.

Repository:

```text
https://github.com/krewten-978/hermes-kvm-lecture-system
```

## What the app currently does

The app currently includes:

- Protected login with `ADMIN_PASSWORD`
- A full-screen Reveal.js sample lecture
- A large teleprompter panel
- Previous / Next slide buttons
- Pause / Resume lecture control
- WebSocket updates for presenter control state
- Autonomous slide advance after the `Begin lecture` command
- Protected markdown notes in `notes/`
- Protected direct command endpoint at `/api/telegram-command`
- Protected start-lecture endpoint at `/api/start-lecture`
- Phase 2A media folder serving at `/media`
- Phase 2B safe media filename-to-URL resolver
- Phase 2C enhanced Markdown parser function: `build_lecture_from_md(title, content)`

Important current limitations:

- The presenter still shows the existing Phase 1 sample slide deck.
- Phase 2C prepares parser output, but Telegram commands still use the older Phase 1 lecture shell until Phase 2F.
- Wait markers and per-slide timing are not active yet. That is Phase 2D.
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

## Phase 2C test checklist

Complete these tests on the laptop before moving to Phase 2D.

### 1. Confirm the app starts

Expected result:

- Uvicorn starts without errors.
- The browser opens `http://127.0.0.1:8000/`.
- You see the login page.

### 2. Confirm login still works

Use the password:

```text
test-password
```

Expected result:

- The presenter page opens after login.
- The sample lecture appears.
- You can see a session code in the top-left badge.
- The badge says `Phase 2C`.

### 3. Confirm the Phase 1 presenter still works

On the presenter page, test:

- Previous / Next buttons
- Keyboard arrow keys
- Teleprompter text changing with slides
- Pause / Resume button

Expected result:

- The existing presenter controls still work.
- Nothing about Phase 2C should change the visible sample lecture yet.

### 4. Confirm automatic slide advance still works

Open a second terminal window in the same project folder and run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"Begin lecture"}'
```

Expected result:

- The presenter status changes to Running.
- The slide should advance automatically after about 5 seconds.

To stop the automatic lecture, run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/telegram-command \
  -H 'Content-Type: application/json' \
  -H 'X-Hermes-Telegram-Secret: test-telegram-secret' \
  -d '{"text":"End lecture"}'
```

### 5. Confirm the Phase 2C Markdown parser

Open a second terminal window in the project folder and run:

```bash
source .venv/bin/activate
python3 - <<'PY'
from app.main import build_lecture_from_md

markdown = """# Cell Energy

## Overview
Cells need energy to do work.
{{image:chloroplast.png}}

## Video Example
Watch this short explanation.
{{youtube:dQw4w9WgXcQ}}

## Plain Review
- ATP stores usable energy.
- Glucose stores chemical energy.
"""

lecture = build_lecture_from_md("Cell Energy", markdown)
slides = lecture["slides"]

assert lecture["title"] == "Cell Energy"
assert lecture["source_markdown"] == markdown
assert lecture["original_markdown"] == markdown
assert len(slides) == 3

for slide in slides:
    assert isinstance(slide["heading"], str)
    assert isinstance(slide["body"], str)
    assert isinstance(slide["narration"], str)
    assert isinstance(slide["duration"], int)
    assert slide["wait"] is False
    assert isinstance(slide["media"], list)
    assert "poll" in slide
    assert "knowledge_check" in slide

assert slides[0]["media"] == [{"type": "image", "value": "chloroplast.png", "url": "/media/images/chloroplast.png"}]
assert '<img src="/media/images/chloroplast.png" style="max-width:100%; height:auto;">' in slides[0]["body"]
assert slides[1]["media"][0]["type"] == "youtube"
assert slides[1]["media"][0]["value"] == "dQw4w9WgXcQ"
assert 'https://www.youtube.com/embed/dQw4w9WgXcQ' in slides[1]["body"]
assert "<ul>" in slides[2]["body"]

print("Phase 2C parser checks passed.")
PY
```

Expected result:

```text
Phase 2C parser checks passed.
```

### 6. Confirm old Phase 1-style notes still parse

Run:

```bash
source .venv/bin/activate
python3 - <<'PY'
from app.main import build_lecture_from_md
from pathlib import Path

content = Path("notes/sample-photosynthesis.md").read_text(encoding="utf-8")
lecture = build_lecture_from_md("Photosynthesis", content)

assert lecture["title"] == "Photosynthesis"
assert len(lecture["slides"]) >= 1
assert lecture["source_markdown"] == content
for slide in lecture["slides"]:
    assert "heading" in slide
    assert "body" in slide
    assert "narration" in slide
    assert "duration" in slide
    assert "wait" in slide
    assert "media" in slide

print("Old notes parser compatibility checks passed.")
PY
```

Expected result:

```text
Old notes parser compatibility checks passed.
```

### 7. Confirm source files are not exposed through media URLs

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
Phase 2C tested — proceed to Phase 2D
```

If something does not work, report:

- Which step failed
- What you expected to happen
- What actually happened
- Any error text shown in the browser or terminal

Do not proceed to Phase 2D until Phase 2C is tested successfully.
