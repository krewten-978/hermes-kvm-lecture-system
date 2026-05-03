# Hermes KVM Lecture System

A minimal FastAPI starter for the Hermes-controlled classroom lecture presenter.

## Phase 1C status

Phase 1C provides:

- Basic FastAPI application
- Static files folder mounted at `/static`
- Tailwind CSS loaded on the presenter page
- Reveal.js loaded from CDN
- `/` page displaying a hardcoded 5-slide sample lecture about photosynthesis
- Large, high-contrast teleprompter panel fixed to the bottom of the page
- Manual **Previous** and **Next** presenter buttons
- Teleprompter text that updates as slides change
- `/health` endpoint for quick deployment checks

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

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For laptop-only testing, this is also fine:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open:

- Presenter page: `http://YOUR_SERVER_IP:8000/`
- Laptop presenter page: `http://127.0.0.1:8000/`
- Health check: `http://YOUR_SERVER_IP:8000/health`

## Phase 1C test checklist

- Confirm the page opens as a full-screen Reveal.js slide deck.
- Confirm the first slide says `Photosynthesis`.
- Confirm the large teleprompter appears across the bottom of the page.
- Click **Next** and **Previous** and confirm the slides change.
- Confirm the teleprompter text changes with each slide.
- Confirm keyboard arrow navigation still works.

## Notes

Security, markdown notes, WebSockets, and Telegram controls are intentionally left for later phases per the phased development plan.
