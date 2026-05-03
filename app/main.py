"""Phase 1A FastAPI application for the Hermes KVM Lecture System."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Hermes KVM Lecture System",
    description="A classroom lecture presenter controlled by Hermes.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    """Render the Phase 1A readiness page."""
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Hermes KVM Lecture System</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="/static/css/site.css" />
      </head>
      <body class="min-h-screen bg-slate-950 text-white">
        <main class="flex min-h-screen items-center justify-center px-6">
          <section class="max-w-3xl rounded-3xl border border-cyan-400/30 bg-slate-900/80 p-10 text-center shadow-2xl shadow-cyan-950/50">
            <p class="mb-4 text-sm font-semibold uppercase tracking-[0.35em] text-cyan-300">Phase 1A</p>
            <h1 class="mb-6 text-5xl font-black tracking-tight md:text-7xl">Hermes Lecture System ready</h1>
            <p class="text-xl leading-relaxed text-slate-300">
              FastAPI is running, static files are mounted, and Tailwind CSS is available for the classroom presenter interface.
            </p>
          </section>
        </main>
      </body>
    </html>
    """


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for deployment smoke tests."""
    return {"status": "ok"}
