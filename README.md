# Hermes KVM Lecture System

A FastAPI + Reveal.js classroom lecture presenter for Wayne's high-school classroom.

Current status: Phase 2B complete.

Phase 2B adds a safe media URL resolver for future Markdown image support. The app can now turn a simple image filename such as `chloroplast.png` into `/media/images/chloroplast.png`, while rejecting unsafe values such as paths, parent-directory traversal, and absolute paths.

Phase 2B does not yet add Markdown image syntax, YouTube embeds, per-slide timing, wait markers, or the lecture-status API. Those are later Phase 2 sub-phases and should not be expected during this test.

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
- Phase 2B safe media filename-to-URL resolver for future image support

Important current limitations:

- The presenter still shows the existing Phase 1 sample slide deck.
- Phase 2B prepares safe image URL handling, but images are not yet rendered from Markdown.
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

## Phase 2B test checklist

Complete these tests on the laptop before moving to Phase 2C.

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

### 3. Confirm the Phase 1 presenter still works

On the presenter page, test:

- Previous / Next buttons
- Keyboard arrow keys
- Teleprompter text changing with slides
- Pause / Resume button

Expected result:

- The existing Phase 1 controls still work.
- Nothing about Phase 2B should change the visible presenter behavior yet.

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

### 5. Confirm media serving still works

Put any small image file into the project folder at:

```text
media/images/test-image.png
```

Then open:

```text
http://127.0.0.1:8000/media/images/test-image.png
```

Expected result:

- The image loads in the browser.

After the test, you may delete the temporary image:

```bash
rm media/images/test-image.png
```

### 6. Confirm the Phase 2B safe media resolver

Open a second terminal window in the project folder and run:

```bash
source .venv/bin/activate
python3 - <<'PY'
from app.main import get_media_url

tests = {
    "chloroplast.png": "/media/images/chloroplast.png",
    "cell diagram.png": "/media/images/cell%20diagram.png",
    "../secret": None,
    "/etc/passwd": None,
    "slides/chloroplast.png": None,
    r"slides\\chloroplast.png": None,
    "": None,
}

for value, expected in tests.items():
    actual = get_media_url(value)
    print(f"{value!r} -> {actual!r}")
    assert actual == expected, f"Expected {expected!r}, got {actual!r}"

print("Phase 2B media resolver checks passed.")
PY
```

Expected result:

```text
Phase 2B media resolver checks passed.
```

Some rejected test values may also print a short rejection warning. That is expected.

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
Phase 2B tested — proceed to Phase 2C
```

If something does not work, report:

- Which step failed
- What you expected to happen
- What actually happened
- Any error text shown in the browser or terminal

Do not proceed to Phase 2C until Phase 2B is tested successfully.
