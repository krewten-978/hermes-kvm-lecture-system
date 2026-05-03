# Hermes KVM Lecture System

A minimal FastAPI starter for the Hermes-controlled classroom lecture presenter.

## Phase 1D status

Phase 1D provides:

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

## Phase 1D test checklist

- Open `/` and confirm you are redirected to `/login`.
- Log in with your `ADMIN_PASSWORD`.
- Confirm the presenter page loads after login.
- Confirm the top-left badge shows a `Session` code.
- Confirm the large teleprompter still appears across the bottom.
- Click **Next** and **Previous** and confirm slides and teleprompter text change.
- Open `/health` after login and confirm it returns JSON with `"status":"ok"` and a session code.
- Click **Logout** and confirm `/` requires login again.

## Notes

Markdown notes, WebSockets, and Telegram controls are intentionally left for later phases per the phased development plan.
