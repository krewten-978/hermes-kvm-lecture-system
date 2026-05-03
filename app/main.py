"""FastAPI application for the Hermes KVM Lecture System."""

import os
import secrets
from typing import Annotated
from urllib.parse import parse_qs

import bcrypt
from fastapi import Cookie, FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
SESSION_COOKIE_NAME = "hermes_session_id"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt())
SESSIONS: dict[str, str] = {}

app = FastAPI(
    title="Hermes KVM Lecture System",
    description="A classroom lecture presenter controlled by Hermes.",
    version="0.4.0",
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def verify_password(password: str) -> bool:
    """Check a submitted password against the bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), ADMIN_PASSWORD_HASH)


def create_session() -> tuple[str, str]:
    """Create an authenticated browser session and a human-readable code."""
    session_id = secrets.token_urlsafe(32)
    session_code = secrets.token_hex(3).upper()
    SESSIONS[session_id] = session_code
    return session_id, session_code


def get_session_code(session_id: str | None) -> str | None:
    """Return the session code for an authenticated session cookie."""
    if not session_id:
        return None
    return SESSIONS.get(session_id)


def login_page(error: str = "") -> str:
    """Render the login page."""
    error_block = (
        f'<p class="mt-4 rounded-xl border border-red-400/60 bg-red-950/70 p-4 text-red-100">{error}</p>'
        if error
        else ""
    )
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Login | Hermes KVM Lecture System</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="/static/css/site.css" />
      </head>
      <body class="min-h-screen bg-slate-950 text-white">
        <main class="flex min-h-screen items-center justify-center px-6">
          <form method="post" action="/login" class="w-full max-w-xl rounded-3xl border border-cyan-400/30 bg-slate-900/90 p-10 shadow-2xl shadow-cyan-950/50">
            <p class="mb-4 text-sm font-semibold uppercase tracking-[0.35em] text-cyan-300">Protected system</p>
            <h1 class="mb-4 text-4xl font-black tracking-tight">Hermes KVM Lecture System</h1>
            <p class="mb-8 text-lg text-slate-300">Enter the configured admin password to start a protected presenter session.</p>
            <label for="password" class="mb-2 block text-sm font-bold uppercase tracking-[0.2em] text-slate-300">Admin password</label>
            <input id="password" name="password" type="password" autofocus required class="w-full rounded-2xl border border-slate-600 bg-slate-950 px-5 py-4 text-2xl text-white outline-none ring-cyan-300 focus:ring-4" />
            {error_block}
            <button type="submit" class="mt-8 w-full rounded-2xl bg-cyan-600 px-6 py-4 text-xl font-black text-white shadow-lg shadow-cyan-950 hover:bg-cyan-500 focus:outline-none focus:ring-4 focus:ring-cyan-300">Log in</button>
          </form>
        </main>
      </body>
    </html>
    """


@app.get("/login", response_class=HTMLResponse)
def login_form(hermes_session_id: Annotated[str | None, Cookie()] = None):
    """Render a login form unless the browser is already authenticated."""
    if get_session_code(hermes_session_id):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return HTMLResponse(login_page())


@app.post("/login")
async def login(request: Request):
    """Authenticate with ADMIN_PASSWORD and create a session code."""
    form = parse_qs((await request.body()).decode("utf-8"))
    password = form.get("password", [""])[0]
    if not verify_password(password):
        return HTMLResponse(login_page("Incorrect admin password."), status_code=status.HTTP_401_UNAUTHORIZED)

    session_id, _session_code = create_session()
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    return response


@app.post("/logout")
def logout(hermes_session_id: Annotated[str | None, Cookie()] = None) -> RedirectResponse:
    """End the current authenticated session."""
    if hermes_session_id:
        SESSIONS.pop(hermes_session_id, None)
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/", response_class=HTMLResponse)
def home(hermes_session_id: Annotated[str | None, Cookie()] = None):
    """Render the protected Phase 1D Reveal.js lecture page."""
    session_code = get_session_code(hermes_session_id)
    if not session_code:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return HTMLResponse(f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Hermes KVM Lecture System</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css" />
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/theme/black.css" />
        <link rel="stylesheet" href="/static/css/site.css" />
      </head>
      <body class="bg-slate-950 text-white">
        <div class="fixed left-4 top-4 z-50 rounded-full border border-cyan-400/40 bg-slate-950/80 px-4 py-2 text-sm font-semibold uppercase tracking-[0.25em] text-cyan-200">
          Hermes Lecture System • Phase 1D • Session {session_code}
        </div>
        <form method="post" action="/logout" class="fixed right-4 top-4 z-50">
          <button type="submit" class="rounded-full border border-slate-500 bg-slate-950/80 px-4 py-2 text-sm font-bold uppercase tracking-[0.2em] text-slate-200 hover:bg-slate-800">Logout</button>
        </form>
        <div class="reveal lecture-stage">
          <div class="slides">
            <section data-notes="Welcome students. Today we are learning how plants make their own food. Start by emphasizing that photosynthesis is one of the most important processes for life on Earth." data-background-gradient="linear-gradient(135deg, #0f172a, #164e63)">
              <h1>Photosynthesis</h1><p class="text-cyan-200">How plants turn light into food</p><p class="mt-8 text-3xl">Sample lecture powered by Reveal.js</p>
            </section>
            <section data-notes="The big idea is energy conversion. Plants capture light energy and store it as chemical energy in glucose. Keep this slide slow and clear.">
              <h2>Big Idea</h2><p>Photosynthesis is the process plants use to convert sunlight, water, and carbon dioxide into glucose and oxygen.</p><p class="mt-8 rounded-2xl bg-cyan-900/40 p-6 text-cyan-100">Light energy becomes chemical energy.</p>
            </section>
            <section data-notes="Walk through the inputs one at a time. Sunlight is captured by chlorophyll, water enters through roots, and carbon dioxide enters through tiny openings in leaves.">
              <h2>What Plants Need</h2><ul><li>Sunlight</li><li>Water from the roots</li><li>Carbon dioxide from the air</li><li>Chlorophyll inside chloroplasts</li></ul>
            </section>
            <section data-notes="Explain that glucose is useful to the plant as stored energy. Oxygen is released as a byproduct, but that byproduct is essential for animals and humans.">
              <h2>The Products</h2><p>Plants produce:</p><ul><li><strong>Glucose</strong> — stored chemical energy</li><li><strong>Oxygen</strong> — released into the atmosphere</li></ul>
            </section>
            <section data-notes="Close by connecting photosynthesis to food chains and breathable oxygen. Let students know that later versions of this system will guide the lecture automatically from notes.">
              <h2>Why It Matters</h2><p>Photosynthesis supports most food chains and helps maintain oxygen in Earth’s atmosphere.</p><p class="mt-8 text-cyan-200">Next phase: protected markdown notes on the server.</p>
            </section>
          </div>
        </div>
        <aside class="teleprompter" aria-label="Lecture teleprompter">
          <div class="teleprompter__header"><span>Teleprompter</span><span id="slide-counter">Slide 1 of 5</span></div>
          <p id="teleprompter-text" class="teleprompter__text">Welcome students. Today we are learning how plants make their own food.</p>
        </aside>
        <nav class="presenter-controls" aria-label="Presenter controls">
          <button id="previous-slide" class="presenter-button" type="button">← Previous</button>
          <button id="next-slide" class="presenter-button presenter-button--primary" type="button">Next →</button>
        </nav>
        <script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
        <script src="/static/js/lecture.js"></script>
      </body>
    </html>
    """)


@app.get("/health")
def health(hermes_session_id: Annotated[str | None, Cookie()] = None) -> JSONResponse:
    """Protected health check for deployment smoke tests."""
    session_code = get_session_code(hermes_session_id)
    if not session_code:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)
    return JSONResponse({"status": "ok", "session_code": session_code})


@app.get("/api/session")
def api_session(hermes_session_id: Annotated[str | None, Cookie()] = None) -> JSONResponse:
    """Protected API endpoint returning the active session code."""
    session_code = get_session_code(hermes_session_id)
    if not session_code:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)
    return JSONResponse({"session_code": session_code})
