"""FastAPI application for the Hermes KVM Lecture System."""

import asyncio
import contextlib
import os
import re
import secrets
import time
from html import escape
from pathlib import Path, PurePath
from typing import Annotated
from urllib.parse import parse_qs, quote

import bcrypt
from fastapi import Cookie, FastAPI, Header, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
LECTURE_SLIDE_SECONDS = float(os.getenv("LECTURE_SLIDE_SECONDS", "75"))
PRESENTER_SLIDE_COUNT = 5
SESSION_COOKIE_NAME = "hermes_session_id"
NOTES_DIR = Path("notes").resolve()
MEDIA_DIR = Path("media").resolve()

# The configured password is hashed with bcrypt at startup. Login attempts are
# checked against this hash; the plain password is never stored in a session.
ADMIN_PASSWORD_HASH = bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt())
SESSIONS: dict[str, str] = {}
LECTURE_SESSIONS: dict[str, dict[str, object]] = {}
LECTURE_CONTROL_STATE: dict[str, bool] = {}
LECTURE_RUNTIME_STATE: dict[str, str] = {}
LECTURE_SLIDE_INDEX: dict[str, int] = {}
LECTURE_SLIDE_STARTED_AT: dict[str, float] = {}
LECTURE_AUTONOMOUS_TASKS: dict[str, asyncio.Task[None]] = {}
WEBSOCKET_CONNECTIONS: dict[str, list[WebSocket]] = {}

app = FastAPI(
    title="Hermes KVM Lecture System",
    description="A classroom lecture presenter controlled by Hermes.",
    version="0.9.5",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


def mount_media() -> None:
    """Mount the optional media directory used for teacher-provided assets."""
    if not MEDIA_DIR.exists():
        print(f"Warning: media directory not found at {MEDIA_DIR}; /media was not mounted.")
        return
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


mount_media()


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


def login_required_redirect(session_id: str | None) -> str | RedirectResponse:
    """Return the session code or redirect an unauthenticated browser."""
    session_code = get_session_code(session_id)
    if session_code:
        return session_code
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


def read_note_file(filename: str) -> str | None:
    """Read a markdown note from the protected notes directory safely."""
    requested_path = (NOTES_DIR / filename).resolve()

    # Keep note reads inside NOTES_DIR and limit this phase to markdown files.
    if NOTES_DIR not in requested_path.parents or requested_path.suffix.lower() != ".md":
        return None
    if not requested_path.is_file():
        return None
    return requested_path.read_text(encoding="utf-8")


def get_media_url(filename: str) -> str | None:
    """Return a safe public URL for an image filename, or None if unsafe."""
    cleaned_filename = filename.strip()

    if not cleaned_filename:
        print("Rejected media filename: empty value")
        return None
    if cleaned_filename.startswith("/") or cleaned_filename.startswith("\\"):
        print(f"Rejected media filename with leading slash: {filename!r}")
        return None
    if "/" in cleaned_filename or "\\" in cleaned_filename:
        print(f"Rejected media filename with path separator: {filename!r}")
        return None
    if ".." in cleaned_filename:
        print(f"Rejected media filename with parent traversal: {filename!r}")
        return None
    if PurePath(cleaned_filename).name != cleaned_filename:
        print(f"Rejected media filename with path component: {filename!r}")
        return None

    return f"/media/images/{quote(cleaned_filename)}"


def markdown_lines_to_html(markdown_text: str) -> str:
    """Convert a small, safe Markdown subset to HTML while preserving media HTML."""
    html_blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        if list_items:
            html_blocks.append("<ul>" + "".join(list_items) + "</ul>")
            list_items.clear()

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue
        if line.startswith("<img ") or line.startswith("<iframe ") or line.startswith("<div "):
            flush_list()
            html_blocks.append(line)
            continue
        if line.startswith("- "):
            list_items.append(f"<li>{escape(line[2:].strip())}</li>")
            continue
        flush_list()
        html_blocks.append(f"<p>{escape(line)}</p>")

    flush_list()
    return "\n".join(html_blocks)


def replace_media_tokens(markdown_text: str) -> tuple[str, list[dict[str, str]]]:
    """Replace supported Phase 2C media tokens and return collected metadata."""
    media: list[dict[str, str]] = []

    def replace_image(match: re.Match[str]) -> str:
        filename = match.group(1).strip()
        media_url = get_media_url(filename)
        if media_url is None:
            return ""
        media.append({"type": "image", "value": filename, "url": media_url})
        return f'<img src="{media_url}" style="max-width:100%; height:auto;">'

    def replace_youtube(match: re.Match[str]) -> str:
        video_id = match.group(1).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", video_id):
            print(f"Rejected YouTube video ID: {video_id!r}")
            return ""
        embed_url = f"https://www.youtube.com/embed/{quote(video_id)}"
        media.append({"type": "youtube", "value": video_id, "url": embed_url})
        return f'<iframe src="{embed_url}" width="100%" height="500" allowfullscreen></iframe>'

    with_images = re.sub(r"\{\{image:([^}]+)\}\}", replace_image, markdown_text)
    with_videos = re.sub(r"\{\{youtube:([^}]+)\}\}", replace_youtube, with_images)
    return with_videos, media


def parse_slide_heading(raw_heading: str) -> tuple[str, bool]:
    """Strip Phase 2D wait markers from a slide heading and report wait mode."""
    has_wait_marker = bool(re.search(r"\{\{\s*(?:wait|pause-autopilot)\s*\}\}", raw_heading, flags=re.IGNORECASE))
    cleaned_heading = re.sub(r"\s*\{\{\s*(?:wait|pause-autopilot)\s*\}\}", "", raw_heading, flags=re.IGNORECASE).strip()
    return cleaned_heading, has_wait_marker


def build_lecture_from_md(title: str, content: str | None) -> dict[str, object]:
    """Build a rich lecture payload from Markdown while preserving Phase 1 compatibility."""
    original_markdown = content or ""
    cleaned_title = title.strip() or "Untitled Lecture"
    markdown = original_markdown.strip()
    slides: list[dict[str, object]] = []

    if not markdown:
        slides.append(
            {
                "heading": cleaned_title,
                "body": "<p>Lecture is ready. Use Begin lecture when the class is ready.</p>",
                "narration": f"Begin the lecture on {cleaned_title}.",
                "duration": int(LECTURE_SLIDE_SECONDS),
                "wait": False,
                "media": [],
                "poll": None,
                "knowledge_check": None,
            }
        )
    else:
        sections = re.split(r"(?m)^##\s+", markdown)
        preamble = sections[0].strip()
        slide_sections = sections[1:] if len(sections) > 1 else []

        if not slide_sections:
            rendered_body, media = replace_media_tokens(markdown)
            slides.append(
                {
                    "heading": cleaned_title,
                    "body": markdown_lines_to_html(rendered_body),
                    "narration": re.sub(r"\{\{[^}]+\}\}", "", markdown).strip() or cleaned_title,
                    "duration": int(LECTURE_SLIDE_SECONDS),
                    "wait": False,
                    "media": media,
                    "poll": None,
                    "knowledge_check": None,
                }
            )
        else:
            for section in slide_sections:
                lines = section.splitlines()
                raw_heading = lines[0].strip() if lines else cleaned_title
                parsed_heading, wait_for_manual_advance = parse_slide_heading(raw_heading or cleaned_title)
                heading = parsed_heading or cleaned_title
                body_markdown = "\n".join(lines[1:]).strip()
                rendered_body, media = replace_media_tokens(body_markdown)
                narration = re.sub(r"\{\{[^}]+\}\}", "", body_markdown).strip() or heading
                slides.append(
                    {
                        "heading": heading,
                        "body": markdown_lines_to_html(rendered_body),
                        "narration": narration,
                        "duration": int(LECTURE_SLIDE_SECONDS),
                        "wait": wait_for_manual_advance,
                        "media": media,
                        "poll": None,
                        "knowledge_check": None,
                    }
                )

        if preamble and preamble.startswith("#"):
            first_line = preamble.splitlines()[0].lstrip("# ").strip()
            if first_line and cleaned_title == "Untitled Lecture":
                cleaned_title = first_line

    return {
        "title": cleaned_title,
        "slides": slides,
        "narration": [str(slide["narration"]) for slide in slides],
        "source_markdown": original_markdown,
        "original_markdown": original_markdown,
    }


def get_active_session_code(requested_session_code: str | None = None) -> str | None:
    """Return the requested valid session code or the newest active session code."""
    active_codes = list(SESSIONS.values())
    if requested_session_code and requested_session_code in active_codes:
        return requested_session_code
    if active_codes:
        return active_codes[-1]
    return None


def presenter_url_for_request(request: Request) -> str:
    """Return the presenter URL for command responses."""
    return str(request.url_for("home"))


def build_help_message() -> str:
    """Return Telegram command help text."""
    return (
        "Hermes Lecture commands:\n"
        "- Start lecture on <topic>\n"
        "- Start lecture on <topic> using notes/<filename>.md\n"
        "- Begin lecture\n"
        "- Pause lecture\n"
        "- Resume lecture\n"
        "- Next slide\n"
        "- Previous slide\n"
        "- End lecture\n\n"
        "Open the presenter and log in first so commands can target the active SESSION_CODE."
    )


def extract_note_filename(command_text: str) -> str | None:
    """Extract a notes/<file>.md reference from a Telegram command."""
    words = command_text.replace("\n", " ").split()
    for word in words:
        cleaned = word.strip(".,;:()[]{}<>\"'")
        if cleaned.startswith("notes/") and cleaned.lower().endswith(".md"):
            return cleaned.removeprefix("notes/")
    return None


def extract_lecture_title(command_text: str) -> str:
    """Extract a lecture title from a start-lecture command."""
    text = command_text.strip()
    lowered = text.lower()
    if lowered.startswith("/startlecture"):
        title = text[len("/startlecture"):].strip()
    elif lowered.startswith("start lecture on"):
        title = text[len("start lecture on"):].strip()
    elif lowered.startswith("start lecture"):
        title = text[len("start lecture"):].strip()
    else:
        title = text

    using_index = title.lower().find(" using ")
    if using_index != -1:
        title = title[:using_index].strip()
    return title or "Untitled Lecture"


def parse_telegram_payload(payload: object) -> tuple[str, int | str | None, str | None]:
    """Extract message text, chat ID, and optional session code from direct or Telegram webhook JSON."""
    if not isinstance(payload, dict):
        return "", None, None

    if isinstance(payload.get("text"), str):
        return payload["text"], payload.get("chat_id"), payload.get("session_code")

    message = payload.get("message") or payload.get("edited_message")
    if isinstance(message, dict):
        text = message.get("text") or ""
        chat = message.get("chat") or {}
        return text, chat.get("id") if isinstance(chat, dict) else None, None

    return "", None, None


def get_session_slides(session_code: str) -> list[dict[str, object]]:
    """Return slide dictionaries for an active lecture payload, if present."""
    lecture = LECTURE_SESSIONS.get(session_code, {})
    slides = lecture.get("slides") if isinstance(lecture, dict) else None
    if not isinstance(slides, list):
        return []
    return [slide for slide in slides if isinstance(slide, dict)]


def get_slide_count(session_code: str) -> int:
    """Return how many slides the current presenter page can advance through."""
    return max(PRESENTER_SLIDE_COUNT, len(get_session_slides(session_code)))


def get_current_slide(session_code: str) -> dict[str, object]:
    """Return metadata for the current slide, or an empty dict for legacy static slides."""
    slides = get_session_slides(session_code)
    current_index = LECTURE_SLIDE_INDEX.get(session_code, 0)
    if 0 <= current_index < len(slides):
        return slides[current_index]
    return {}


def get_current_slide_duration(session_code: str) -> float:
    """Return the current slide duration, falling back to the global default."""
    duration = get_current_slide(session_code).get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        return float(duration)
    return max(float(LECTURE_SLIDE_SECONDS), 0.01)


def is_current_slide_waiting(session_code: str) -> bool:
    """Return whether the current slide has an explicit Phase 2D wait marker."""
    return bool(get_current_slide(session_code).get("wait"))


def mark_slide_started(session_code: str) -> None:
    """Record when the current slide became active for duration tracking."""
    LECTURE_SLIDE_STARTED_AT[session_code] = time.monotonic()


def get_duration_remaining(session_code: str) -> float:
    """Return seconds remaining on the current slide for WebSocket clients."""
    if LECTURE_RUNTIME_STATE.get(session_code) != "running" or LECTURE_CONTROL_STATE.get(session_code, False):
        return get_current_slide_duration(session_code)
    if is_current_slide_waiting(session_code):
        return 0.0
    started_at = LECTURE_SLIDE_STARTED_AT.get(session_code, time.monotonic())
    elapsed = time.monotonic() - started_at
    return max(get_current_slide_duration(session_code) - elapsed, 0.0)


def get_time_on_slide(session_code: str) -> float:
    """Return how many seconds the current slide has been active."""
    started_at = LECTURE_SLIDE_STARTED_AT.get(session_code)
    if started_at is None:
        return 0.0
    return max(time.monotonic() - started_at, 0.0)


def summarize_slide_body(body: object, max_length: int = 180) -> str:
    """Return a compact text summary from a slide body value."""
    if not isinstance(body, str):
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", body)
    compact = " ".join(without_tags.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "…"


def build_lecture_status(session_code: str) -> dict[str, object]:
    """Build the compact Phase 2E lecture-status payload for Hermes."""
    current_index = LECTURE_SLIDE_INDEX.get(session_code, 0)
    current_slide = get_current_slide(session_code)
    session_slides = get_session_slides(session_code)
    media = current_slide.get("media") if isinstance(current_slide, dict) else []
    if not isinstance(media, list):
        media = []

    return {
        "session_code": session_code,
        "state": LECTURE_RUNTIME_STATE.get(session_code, "ready"),
        "current_slide_index": current_index,
        "current_slide": {
            "heading": str(current_slide.get("heading", "")) if current_slide else "",
            "body_summary": summarize_slide_body(current_slide.get("body", "")) if current_slide else "",
        },
        "is_paused": LECTURE_CONTROL_STATE.get(session_code, False),
        "wait_mode": is_current_slide_waiting(session_code),
        "time_on_slide_seconds": round(get_time_on_slide(session_code), 2),
        "total_slides": len(session_slides) if session_slides else PRESENTER_SLIDE_COUNT,
        "media_on_slide": media,
    }


def build_control_message(session_code: str, message_type: str = "control_state") -> dict[str, object]:
    """Build the WebSocket state payload shared by controls and autonomous mode."""
    current_duration = get_current_slide_duration(session_code)
    return {
        "type": message_type,
        "paused": LECTURE_CONTROL_STATE.get(session_code, False),
        "state": LECTURE_RUNTIME_STATE.get(session_code, "ready"),
        "session_code": session_code,
        "slide_index": LECTURE_SLIDE_INDEX.get(session_code, 0),
        "slide_count": get_slide_count(session_code),
        "slide_seconds": LECTURE_SLIDE_SECONDS,
        "slide_duration": current_duration,
        "is_waiting": is_current_slide_waiting(session_code),
        "duration_remaining": round(get_duration_remaining(session_code), 2),
    }


def start_autonomous_lecture(session_code: str) -> None:
    """Ensure exactly one autonomous slide-advance task is running for a session."""
    existing_task = LECTURE_AUTONOMOUS_TASKS.get(session_code)
    if existing_task and not existing_task.done():
        return
    LECTURE_AUTONOMOUS_TASKS[session_code] = asyncio.create_task(auto_advance_lecture(session_code))


async def stop_autonomous_lecture(session_code: str) -> None:
    """Cancel the autonomous task for a session if it is running."""
    task = LECTURE_AUTONOMOUS_TASKS.pop(session_code, None)
    if task and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def auto_advance_lecture(session_code: str) -> None:
    """Advance presenter slides while respecting per-slide duration and wait markers."""
    LECTURE_AUTONOMOUS_TASKS[session_code] = asyncio.current_task()  # type: ignore[assignment]
    mark_slide_started(session_code)

    while LECTURE_RUNTIME_STATE.get(session_code) == "running":
        if LECTURE_CONTROL_STATE.get(session_code, False):
            await asyncio.sleep(0.1)
            continue

        if is_current_slide_waiting(session_code):
            await broadcast_control_state(session_code)
            while (
                LECTURE_RUNTIME_STATE.get(session_code) == "running"
                and not LECTURE_CONTROL_STATE.get(session_code, False)
                and is_current_slide_waiting(session_code)
            ):
                await asyncio.sleep(0.1)
            mark_slide_started(session_code)
            continue

        mark_slide_started(session_code)
        while get_duration_remaining(session_code) > 0:
            if LECTURE_RUNTIME_STATE.get(session_code) != "running":
                break
            if LECTURE_CONTROL_STATE.get(session_code, False) or is_current_slide_waiting(session_code):
                break
            await asyncio.sleep(min(get_duration_remaining(session_code), 1.0))
            await broadcast_control_state(session_code)

        if LECTURE_RUNTIME_STATE.get(session_code) != "running":
            break
        if LECTURE_CONTROL_STATE.get(session_code, False) or is_current_slide_waiting(session_code):
            continue

        current_index = LECTURE_SLIDE_INDEX.get(session_code, 0)
        slide_count = get_slide_count(session_code)
        if current_index >= slide_count - 1:
            LECTURE_RUNTIME_STATE[session_code] = "ended"
            LECTURE_CONTROL_STATE[session_code] = True
            await broadcast_control_state(session_code)
            break

        LECTURE_SLIDE_INDEX[session_code] = current_index + 1
        mark_slide_started(session_code)
        await broadcast_control_state(session_code, message_type="slide_advance")

    task = LECTURE_AUTONOMOUS_TASKS.get(session_code)
    if task is asyncio.current_task():
        LECTURE_AUTONOMOUS_TASKS.pop(session_code, None)


async def advance_lecture_slide(session_code: str, step: int) -> int:
    """Move the tracked slide index manually and reset Phase 2D timing."""
    slide_count = get_slide_count(session_code)
    current_index = LECTURE_SLIDE_INDEX.get(session_code, 0)
    next_index = min(max(current_index + step, 0), max(slide_count - 1, 0))
    LECTURE_SLIDE_INDEX[session_code] = next_index
    mark_slide_started(session_code)
    await broadcast_control_state(session_code, message_type="slide_advance")
    return next_index


async def apply_telegram_command(command_text: str, request: Request, requested_session_code: str | None = None) -> dict[str, object]:
    """Apply a Telegram lecture command and return a reply payload."""
    normalized = " ".join(command_text.lower().strip().split())
    session_code = get_active_session_code(requested_session_code)
    presenter_url = presenter_url_for_request(request)

    if normalized in {"", "/start", "help", "/help"}:
        return {"ok": True, "reply": build_help_message(), "session_code": session_code, "url": presenter_url}

    if session_code is None:
        return {
            "ok": False,
            "reply": f"No active presenter session yet. Open {presenter_url}, log in, then send the command again.",
            "url": presenter_url,
        }

    if normalized.startswith("start lecture") or normalized.startswith("/startlecture"):
        title = extract_lecture_title(command_text)
        note_filename = extract_note_filename(command_text)
        note_content = read_note_file(note_filename) if note_filename else None
        slide_body = (
            note_content.splitlines()[0].lstrip("# ").strip()
            if note_content and note_content.splitlines()
            else "Lecture is ready. Use Begin lecture when the class is ready."
        )
        narration = note_content or f"Begin the lecture on {title}."
        LECTURE_SESSIONS[session_code] = {
            "title": title,
            "slides": [{"heading": title, "body": slide_body}],
            "narration": [narration],
            "source": f"notes/{note_filename}" if note_filename and note_content else "telegram",
        }
        LECTURE_RUNTIME_STATE[session_code] = "ready"
        LECTURE_CONTROL_STATE[session_code] = False
        LECTURE_SLIDE_INDEX[session_code] = 0
        mark_slide_started(session_code)
        await stop_autonomous_lecture(session_code)
        await broadcast_control_state(session_code)
        note_line = f" using notes/{note_filename}" if note_filename and note_content else ""
        missing_note_line = f"\nNote file notes/{note_filename} was not found, so I created a basic lecture shell." if note_filename and not note_content else ""
        return {
            "ok": True,
            "reply": f"Lecture ready: {title}{note_line}\nPresenter: {presenter_url}\nSession: {session_code}{missing_note_line}",
            "url": presenter_url,
            "session_code": session_code,
            "state": "ready",
        }

    if normalized in {"begin lecture", "/begin", "begin"}:
        LECTURE_RUNTIME_STATE[session_code] = "running"
        LECTURE_CONTROL_STATE[session_code] = False
        LECTURE_SLIDE_INDEX[session_code] = 0
        mark_slide_started(session_code)
        start_autonomous_lecture(session_code)
        await broadcast_control_state(session_code)
        return {"ok": True, "reply": f"Lecture begun. Autonomous slide advance is running every {LECTURE_SLIDE_SECONDS:g} seconds. Presenter: {presenter_url}", "url": presenter_url, "session_code": session_code, "state": "running", "slide_seconds": LECTURE_SLIDE_SECONDS}

    if normalized in {"pause lecture", "/pause", "pause"}:
        LECTURE_CONTROL_STATE[session_code] = True
        await broadcast_control_state(session_code)
        return {"ok": True, "reply": "Lecture paused.", "session_code": session_code, "state": LECTURE_RUNTIME_STATE.get(session_code, "ready"), "paused": True}

    if normalized in {"resume lecture", "/resume", "resume"}:
        LECTURE_RUNTIME_STATE[session_code] = "running"
        LECTURE_CONTROL_STATE[session_code] = False
        mark_slide_started(session_code)
        start_autonomous_lecture(session_code)
        await broadcast_control_state(session_code)
        return {"ok": True, "reply": "Lecture resumed. Autonomous slide advance is running.", "session_code": session_code, "state": "running", "paused": False, "slide_seconds": LECTURE_SLIDE_SECONDS}

    if normalized in {"next slide", "/next", "next"}:
        slide_index = await advance_lecture_slide(session_code, 1)
        return {"ok": True, "reply": f"Advanced to slide {slide_index + 1}.", "session_code": session_code, "state": LECTURE_RUNTIME_STATE.get(session_code, "ready"), "slide_index": slide_index}

    if normalized in {"previous slide", "prev slide", "/previous", "/prev", "previous", "prev"}:
        slide_index = await advance_lecture_slide(session_code, -1)
        return {"ok": True, "reply": f"Moved back to slide {slide_index + 1}.", "session_code": session_code, "state": LECTURE_RUNTIME_STATE.get(session_code, "ready"), "slide_index": slide_index}

    if normalized in {"end lecture", "/end", "end"}:
        LECTURE_RUNTIME_STATE[session_code] = "ended"
        LECTURE_CONTROL_STATE[session_code] = True
        LECTURE_SLIDE_STARTED_AT.pop(session_code, None)
        await stop_autonomous_lecture(session_code)
        await broadcast_control_state(session_code)
        return {"ok": True, "reply": "Lecture ended.", "session_code": session_code, "state": "ended", "paused": True}

    return {"ok": False, "reply": "I did not recognize that command.\n\n" + build_help_message(), "session_code": session_code, "url": presenter_url}


async def broadcast_control_state(session_code: str, message_type: str = "control_state") -> None:
    """Broadcast current lecture state to presenter WebSocket clients."""
    message = build_control_message(session_code, message_type=message_type)
    active_connections = []

    for websocket in WEBSOCKET_CONNECTIONS.get(session_code, []):
        try:
            await websocket.send_json(message)
            active_connections.append(websocket)
        except RuntimeError:
            pass

    if active_connections:
        WEBSOCKET_CONNECTIONS[session_code] = active_connections
    else:
        WEBSOCKET_CONNECTIONS.pop(session_code, None)


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
        session_code = SESSIONS.pop(hermes_session_id, None)
        if session_code:
            LECTURE_SESSIONS.pop(session_code, None)
            LECTURE_CONTROL_STATE.pop(session_code, None)
            LECTURE_RUNTIME_STATE.pop(session_code, None)
            LECTURE_SLIDE_INDEX.pop(session_code, None)
            LECTURE_SLIDE_STARTED_AT.pop(session_code, None)
            task = LECTURE_AUTONOMOUS_TASKS.pop(session_code, None)
            if task and not task.done():
                task.cancel()
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/", response_class=HTMLResponse)
def home(hermes_session_id: Annotated[str | None, Cookie()] = None):
    """Render the protected Phase 2E Reveal.js lecture page."""
    session_code_or_redirect = login_required_redirect(hermes_session_id)
    if isinstance(session_code_or_redirect, RedirectResponse):
        return session_code_or_redirect
    session_code = session_code_or_redirect

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
          Hermes Lecture System • Phase 2E • Session {session_code}
        </div>

        <form method="post" action="/logout" class="fixed right-4 top-4 z-50">
          <button type="submit" class="rounded-full border border-slate-500 bg-slate-950/80 px-4 py-2 text-sm font-bold uppercase tracking-[0.2em] text-slate-200 hover:bg-slate-800">Logout</button>
        </form>

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
              <p class="mt-8 text-cyan-200">Phase 2E: Protected lecture-status API is available for Hermes visibility.</p>
            </section>
          </div>
        </div>

        <aside class="teleprompter" aria-label="Lecture teleprompter">
          <div class="teleprompter__header">
            <span>Teleprompter</span>
            <span id="slide-counter">Slide 1 of 5</span>
          </div>
          <p id="teleprompter-text" class="teleprompter__text">Welcome students. Today we are learning how plants make their own food.</p>
        </aside>

        <div id="lecture-status" class="lecture-status" aria-live="polite">Live</div>

        <nav class="presenter-controls" aria-label="Presenter controls">
          <button id="pause-resume-lecture" class="presenter-button presenter-button--pause" type="button">Pause Lecture</button>
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


@app.get("/api/lecture-status")
def lecture_status(hermes_session_id: Annotated[str | None, Cookie()] = None) -> JSONResponse:
    """Protected Phase 2E endpoint exposing compact lecture status for Hermes."""
    session_code = get_session_code(hermes_session_id)
    if not session_code:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)
    return JSONResponse(build_lecture_status(session_code))


@app.websocket("/ws/session")
async def websocket_session(websocket: WebSocket) -> None:
    """Authenticated presenter WebSocket for pause/resume control state."""
    session_id = websocket.cookies.get(SESSION_COOKIE_NAME)
    session_code = get_session_code(session_id)
    if not session_code:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    WEBSOCKET_CONNECTIONS.setdefault(session_code, []).append(websocket)
    await websocket.send_json(build_control_message(session_code))

    try:
        while True:
            message = await websocket.receive_json()
            command = message.get("command") if isinstance(message, dict) else None

            if command == "pause":
                LECTURE_CONTROL_STATE[session_code] = True
                await broadcast_control_state(session_code)
            elif command == "resume":
                LECTURE_RUNTIME_STATE[session_code] = "running"
                LECTURE_CONTROL_STATE[session_code] = False
                mark_slide_started(session_code)
                start_autonomous_lecture(session_code)
                await broadcast_control_state(session_code)
            elif command == "next":
                await advance_lecture_slide(session_code, 1)
            elif command == "previous":
                await advance_lecture_slide(session_code, -1)
            elif command == "toggle":
                LECTURE_CONTROL_STATE[session_code] = not LECTURE_CONTROL_STATE.get(session_code, False)
                if not LECTURE_CONTROL_STATE[session_code]:
                    LECTURE_RUNTIME_STATE[session_code] = "running"
                    mark_slide_started(session_code)
                    start_autonomous_lecture(session_code)
                await broadcast_control_state(session_code)
            else:
                await websocket.send_json({"type": "error", "detail": "Unknown command"})
    except WebSocketDisconnect:
        pass
    finally:
        connections = WEBSOCKET_CONNECTIONS.get(session_code, [])
        if websocket in connections:
            connections.remove(websocket)
        if connections:
            WEBSOCKET_CONNECTIONS[session_code] = connections
        else:
            WEBSOCKET_CONNECTIONS.pop(session_code, None)


@app.post("/api/telegram-command")
async def telegram_command(
    request: Request,
    x_hermes_telegram_secret: Annotated[str | None, Header(alias="X-Hermes-Telegram-Secret")] = None,
    x_telegram_secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> JSONResponse:
    """Protected Telegram webhook/direct command endpoint for lecture control."""
    supplied_secret = x_hermes_telegram_secret or x_telegram_secret
    if not TELEGRAM_WEBHOOK_SECRET:
        return JSONResponse({"detail": "Telegram command endpoint is not configured"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    if not supplied_secret or not secrets.compare_digest(supplied_secret, TELEGRAM_WEBHOOK_SECRET):
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"detail": "Expected JSON body"}, status_code=status.HTTP_400_BAD_REQUEST)

    command_text, chat_id, requested_session_code = parse_telegram_payload(payload)
    result = await apply_telegram_command(command_text, request, requested_session_code)

    # Telegram can execute this method response directly when the endpoint is used as a webhook.
    if chat_id is not None:
        return JSONResponse({"method": "sendMessage", "chat_id": chat_id, "text": result["reply"]})
    return JSONResponse(result, status_code=status.HTTP_200_OK if result.get("ok") else status.HTTP_400_BAD_REQUEST)


@app.post("/api/start-lecture")
async def start_lecture(request: Request, hermes_session_id: Annotated[str | None, Cookie()] = None) -> JSONResponse:
    """Protected endpoint for storing a lecture payload in memory for this session."""
    session_code = get_session_code(hermes_session_id)
    if not session_code:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"detail": "Expected JSON body"}, status_code=status.HTTP_400_BAD_REQUEST)

    if not isinstance(payload, dict):
        return JSONResponse({"detail": "Expected JSON object"}, status_code=status.HTTP_400_BAD_REQUEST)

    title = payload.get("title")
    slides = payload.get("slides")
    narration = payload.get("narration")

    if not isinstance(title, str) or not title.strip():
        return JSONResponse({"detail": "Field 'title' must be a non-empty string"}, status_code=status.HTTP_400_BAD_REQUEST)
    if not isinstance(slides, list) or not slides:
        return JSONResponse({"detail": "Field 'slides' must be a non-empty list"}, status_code=status.HTTP_400_BAD_REQUEST)
    if narration is None:
        return JSONResponse({"detail": "Field 'narration' is required"}, status_code=status.HTTP_400_BAD_REQUEST)

    lecture = {
        "title": title.strip(),
        "slides": slides,
        "narration": narration,
    }
    LECTURE_SESSIONS[session_code] = lecture
    LECTURE_RUNTIME_STATE[session_code] = "ready"
    LECTURE_CONTROL_STATE[session_code] = False
    LECTURE_SLIDE_INDEX[session_code] = 0
    mark_slide_started(session_code)
    await stop_autonomous_lecture(session_code)
    await broadcast_control_state(session_code)

    return JSONResponse(
        {
            "url": str(request.url_for("home")),
            "session_code": session_code,
            "title": lecture["title"],
            "slide_count": len(slides),
        }
    )


@app.get("/api/notes/{filename:path}")
def api_note(filename: str, hermes_session_id: Annotated[str | None, Cookie()] = None) -> JSONResponse:
    """Protected endpoint for reading markdown notes stored on the KVM."""
    session_code = get_session_code(hermes_session_id)
    if not session_code:
        return JSONResponse({"detail": "Not authenticated"}, status_code=status.HTTP_401_UNAUTHORIZED)

    content = read_note_file(filename)
    if content is None:
        return JSONResponse({"detail": "Note not found"}, status_code=status.HTTP_404_NOT_FOUND)

    return JSONResponse({"filename": filename, "content": content, "session_code": session_code})

