"""FastAPI application for the Hermes KVM Lecture System."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Hermes KVM Lecture System",
    description="A classroom lecture presenter controlled by Hermes.",
    version="0.3.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    """Render the Phase 1C Reveal.js sample lecture with presenter controls."""
    return """
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
          Hermes Lecture System • Phase 1C
        </div>

        <div class="reveal lecture-stage">
          <div class="slides">
            <section data-notes="Welcome students. Today we are learning how plants make their own food. Start by emphasizing that photosynthesis is one of the most important processes for life on Earth." data-background-gradient="linear-gradient(135deg, #0f172a, #164e63)">
              <h1>Photosynthesis</h1>
              <p class="text-cyan-200">How plants turn light into food</p>
              <p class="mt-8 text-3xl">Sample lecture powered by Reveal.js</p>
            </section>

            <section data-notes="The big idea is energy conversion. Plants capture light energy and store it as chemical energy in glucose. Keep this slide slow and clear.">
              <h2>Big Idea</h2>
              <p>Photosynthesis is the process plants use to convert sunlight, water, and carbon dioxide into glucose and oxygen.</p>
              <p class="mt-8 rounded-2xl bg-cyan-900/40 p-6 text-cyan-100">Light energy becomes chemical energy.</p>
            </section>

            <section data-notes="Walk through the inputs one at a time. Sunlight is captured by chlorophyll, water enters through roots, and carbon dioxide enters through tiny openings in leaves.">
              <h2>What Plants Need</h2>
              <ul>
                <li>Sunlight</li>
                <li>Water from the roots</li>
                <li>Carbon dioxide from the air</li>
                <li>Chlorophyll inside chloroplasts</li>
              </ul>
            </section>

            <section data-notes="Explain that glucose is useful to the plant as stored energy. Oxygen is released as a byproduct, but that byproduct is essential for animals and humans.">
              <h2>The Products</h2>
              <p>Plants produce:</p>
              <ul>
                <li><strong>Glucose</strong> — stored chemical energy</li>
                <li><strong>Oxygen</strong> — released into the atmosphere</li>
              </ul>
            </section>

            <section data-notes="Close by connecting photosynthesis to food chains and breathable oxygen. Let students know that later versions of this system will guide the lecture automatically from notes.">
              <h2>Why It Matters</h2>
              <p>Photosynthesis supports most food chains and helps maintain oxygen in Earth’s atmosphere.</p>
              <p class="mt-8 text-cyan-200">Next phase: full security with login and session codes.</p>
            </section>
          </div>
        </div>

        <aside class="teleprompter" aria-label="Lecture teleprompter">
          <div class="teleprompter__header">
            <span>Teleprompter</span>
            <span id="slide-counter">Slide 1 of 5</span>
          </div>
          <p id="teleprompter-text" class="teleprompter__text">
            Welcome students. Today we are learning how plants make their own food.
          </p>
        </aside>

        <nav class="presenter-controls" aria-label="Presenter controls">
          <button id="previous-slide" class="presenter-button" type="button">← Previous</button>
          <button id="next-slide" class="presenter-button presenter-button--primary" type="button">Next →</button>
        </nav>

        <script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
        <script src="/static/js/lecture.js"></script>
      </body>
    </html>
    """


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for deployment smoke tests."""
    return {"status": "ok"}
