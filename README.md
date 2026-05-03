# Hermes KVM Lecture System

A minimal FastAPI starter for the Hermes-controlled classroom lecture presenter.

## Phase 1E status

Phase 1E provides:

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
- Logout button

## Configure the admin password

Set `ADMIN_PASSWORD` before starting the server. Example:

```bash
export ADMIN_PASSWORD='choose-a-long-private-password'
```

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
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For laptop-only testing:

```bash
export ADMIN_PASSWORD='test-password'
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

## Phase 1E test checklist

- Open `/` and confirm you are redirected to `/login` if not logged in.
- Log in with your `ADMIN_PASSWORD`.
- Confirm the presenter page still loads after login.
- Confirm the top-left badge says `Phase 1E` and shows a `Session` code.
- Confirm the teleprompter and Previous/Next controls still work.
- Open `/api/notes/sample-photosynthesis.md` after login and confirm it returns JSON with markdown content.
- Open `/api/notes/sample-photosynthesis.md` in a private/incognito window and confirm it requires login or returns `401`.
- Try a missing note, such as `/api/notes/missing.md`, and confirm it returns `404`.
- Click **Logout** and confirm `/` requires login again.

## Notes

Start-lecture API, WebSockets, and Telegram controls are intentionally left for later phases per the phased development plan.
