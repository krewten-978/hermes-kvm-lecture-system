import asyncio
import importlib


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class FakeRequest:
    def url_for(self, route_name):
        assert route_name == "home"
        return "http://testserver/"


def load_main(monkeypatch, interval="0.05"):
    monkeypatch.setenv("ADMIN_PASSWORD", "phase-test-password")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "phase-test-secret")
    monkeypatch.setenv("LECTURE_SLIDE_SECONDS", interval)
    import app.main as main
    return importlib.reload(main)


def create_active_session(main):
    _session_id, session_code = main.create_session()
    return session_code


def test_telegram_start_using_notes_builds_rich_parsed_lecture(monkeypatch):
    main = load_main(monkeypatch)
    session_code = create_active_session(main)

    payload = asyncio.run(
        main.apply_telegram_command(
            "Start lecture on Photosynthesis using notes/sample-photosynthesis.md",
            FakeRequest(),
            session_code,
        )
    )

    assert payload["ok"] is True
    lecture = main.LECTURE_SESSIONS[session_code]
    slides = lecture["slides"]

    assert lecture["title"] == "Photosynthesis"
    assert lecture["source"] == "notes/sample-photosynthesis.md"
    assert lecture["source_markdown"] == main.read_note_file("sample-photosynthesis.md")
    assert len(slides) >= 4
    assert any(slide.get("wait") is True for slide in slides)
    assert any(media.get("type") == "image" for slide in slides for media in slide.get("media", []))
    assert any(media.get("type") == "youtube" for slide in slides for media in slide.get("media", []))
    assert all("poll" in slide and "knowledge_check" in slide for slide in slides)


def test_presenter_page_renders_parsed_note_media_after_telegram_start(monkeypatch):
    main = load_main(monkeypatch)
    session_id, session_code = main.create_session()

    command_payload = asyncio.run(
        main.apply_telegram_command(
            "Start lecture on Photosynthesis using notes/sample-photosynthesis.md",
            FakeRequest(),
            session_code,
        )
    )
    assert command_payload["ok"] is True

    page_response = main.home(session_id)
    body = page_response.body.decode("utf-8")

    assert page_response.status_code == 200
    assert "Phase 2F" in body
    assert "/media/images/" in body
    assert "https://www.youtube.com/embed/" in body
    assert "data-wait=\"true\"" in body


def test_command_endpoint_prefers_visible_presenter_session_over_status_api_login(monkeypatch):
    main = load_main(monkeypatch)
    presenter_session_id, presenter_session_code = main.create_session()
    _status_cookie_session_id, status_session_code = main.create_session()

    # The browser presenter has the live WebSocket. A later curl login used only
    # for /api/lecture-status must not steal later Telegram/direct commands.
    main.WEBSOCKET_CONNECTIONS[presenter_session_code] = [FakeWebSocket()]

    command_payload = asyncio.run(
        main.apply_telegram_command(
            "Start lecture on Photosynthesis using notes/sample-photosynthesis.md",
            FakeRequest(),
        )
    )

    assert command_payload["ok"] is True
    assert command_payload["session_code"] == presenter_session_code
    assert presenter_session_code in main.LECTURE_SESSIONS
    assert status_session_code not in main.LECTURE_SESSIONS

    page_response = main.home(presenter_session_id)
    body = page_response.body.decode("utf-8")
    assert "photosynthesis-overview.svg" in body
    assert "Slide 1 of 6" in body


def test_parsed_lecture_slide_count_does_not_include_static_fallback_slides(monkeypatch):
    main = load_main(monkeypatch)
    session_code = create_active_session(main)
    main.LECTURE_SESSIONS[session_code] = main.build_lecture_from_md("Short", "## Only Parsed Slide\nContent")

    assert len(main.get_session_slides(session_code)) == 1
    assert main.get_slide_count(session_code) == 1
    assert main.build_lecture_status(session_code)["total_slides"] == 1


def test_phase2f_sample_note_contains_required_markdown_tokens(monkeypatch):
    main = load_main(monkeypatch)
    sample = main.read_note_file("sample-photosynthesis.md") or ""

    assert "{{image:" in sample
    assert "{{youtube:" in sample
    assert "{{wait}}" in sample or "{{pause-autopilot}}" in sample


def test_fresh_presenter_does_not_render_duplicate_photosynthesis_fallback_deck(monkeypatch):
    main = load_main(monkeypatch)
    session_id, _session_code = main.create_session()

    page_response = main.home(session_id)
    body = page_response.body.decode("utf-8")

    assert page_response.status_code == 200
    assert "<h1>Photosynthesis</h1>" not in body
    assert "Sample lecture powered by Reveal.js" not in body
    assert "Slide 1 of 5" not in body
    assert "No lecture loaded" in body


def test_restarting_same_slide_count_lecture_increments_presenter_revision(monkeypatch):
    main = load_main(monkeypatch)
    session_id, session_code = main.create_session()

    first = asyncio.run(
        main.apply_telegram_command(
            "Start lecture on Photosynthesis using notes/sample-photosynthesis.md",
            FakeRequest(),
            session_code,
        )
    )
    first_page = main.home(session_id).body.decode("utf-8")
    second = asyncio.run(
        main.apply_telegram_command(
            "Start lecture on Photosynthesis using notes/sample-photosynthesis.md",
            FakeRequest(),
            session_code,
        )
    )
    second_page = main.home(session_id).body.decode("utf-8")

    assert first["ok"] is True
    assert second["ok"] is True
    assert 'data-lecture-revision="1"' in first_page
    assert 'data-lecture-revision="2"' in second_page
    assert main.build_control_message(session_code)["lecture_revision"] == 2


def test_youtube_slide_embeds_autoplay_and_pauses_on_entry(monkeypatch):
    main = load_main(monkeypatch)

    lecture = main.build_lecture_from_md("Video Test", "## Video\n{{youtube:dQw4w9WgXcQ}}")
    slide = lecture["slides"][0]

    assert slide["wait"] is False
    assert slide["pause_on_enter"] is True
    assert slide["media"][0]["type"] == "youtube"
    assert "autoplay=1" in slide["body"]
    assert "mute=1" in slide["body"]
    assert "allow=\"autoplay; encrypted-media; picture-in-picture; fullscreen\"" in slide["body"]


def test_autonomous_lecture_pauses_once_when_landing_on_youtube_slide_then_resume_advances(monkeypatch):
    main = load_main(monkeypatch, interval="0.05")
    session_code = create_active_session(main)
    main.LECTURE_SESSIONS[session_code] = main.build_lecture_from_md(
        "Video Test",
        "## Intro\nStart here.\n\n## Video\n{{youtube:dQw4w9WgXcQ}}\n\n## After Video\nContinue.\n\n## Wrap Up\nFinish.",
    )
    main.LECTURE_SLIDE_INDEX[session_code] = 0
    main.LECTURE_RUNTIME_STATE[session_code] = "running"
    main.LECTURE_CONTROL_STATE[session_code] = False

    async def run_check():
        task = asyncio.create_task(main.auto_advance_lecture(session_code))
        await asyncio.sleep(0.08)
        assert main.LECTURE_SLIDE_INDEX[session_code] == 1
        assert main.LECTURE_CONTROL_STATE[session_code] is True
        assert main.build_lecture_status(session_code)["is_paused"] is True

        response = await main.apply_telegram_command("Resume lecture", FakeRequest(), session_code)
        assert response["ok"] is True
        await asyncio.sleep(0.13)
        assert main.LECTURE_SLIDE_INDEX[session_code] >= 2
        assert main.LECTURE_RUNTIME_STATE[session_code] == "running"
        assert main.LECTURE_CONTROL_STATE[session_code] is False

        main.LECTURE_RUNTIME_STATE[session_code] = "ended"
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run_check())


def test_telegram_started_parsed_lecture_waits_then_advances_manually(monkeypatch):
    main = load_main(monkeypatch, interval="0.01")
    session_code = create_active_session(main)

    response = asyncio.run(
        main.apply_telegram_command(
            "Start lecture on Photosynthesis using notes/sample-photosynthesis.md",
            FakeRequest(),
            session_code,
        )
    )
    assert response["ok"] is True

    wait_index = next(
        index
        for index, slide in enumerate(main.LECTURE_SESSIONS[session_code]["slides"])
        if slide.get("wait") is True
    )
    main.LECTURE_SLIDE_INDEX[session_code] = max(wait_index - 1, 0)
    main.LECTURE_RUNTIME_STATE[session_code] = "running"
    main.LECTURE_CONTROL_STATE[session_code] = False

    async def run_check():
        task = asyncio.create_task(main.auto_advance_lecture(session_code))
        await asyncio.sleep(0.08)
        assert main.LECTURE_SLIDE_INDEX[session_code] == wait_index
        assert main.build_lecture_status(session_code)["wait_mode"] is True
        await main.advance_lecture_slide(session_code, 1)
        assert main.LECTURE_SLIDE_INDEX[session_code] == wait_index + 1
        main.LECTURE_RUNTIME_STATE[session_code] = "ended"
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run_check())
