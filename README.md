# Hermes KVM Lecture System

A minimal FastAPI starter for the Hermes-controlled classroom lecture presenter.

## Phase 1A status

Phase 1A provides:

- Basic FastAPI application
- Static files folder mounted at `/static`
- Tailwind CSS loaded on the home page
- `/` page that says `Hermes Lecture System ready`
- `/health` endpoint for quick deployment checks

## Local / KVM setup

```bash
git clone https://github.com/krewten-978/hermes-kvm-lecture-system.git
cd hermes-kvm-lecture-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run with uvicorn

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open:

- Home page: `http://YOUR_SERVER_IP:8000/`
- Health check: `http://YOUR_SERVER_IP:8000/health`

## Notes

Security, Reveal.js slides, teleprompter, notes, WebSockets, and Telegram controls are intentionally left for later phases per the phased development plan.
