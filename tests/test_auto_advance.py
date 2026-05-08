import asyncio
import importlib


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def load_main(monkeypatch, interval="0.01"):
    monkeypatch.setenv("LECTURE_SLIDE_SECONDS", interval)
    import app.main as main
    return importlib.reload(main)


def test_begin_lecture_starts_autonomous_slide_advancement_task(monkeypatch):
    main = load_main(monkeypatch)

    session_id, session_code = main.create_session()
    assert session_id
    websocket = FakeWebSocket()
    main.WEBSOCKET_CONNECTIONS[session_code] = [websocket]
    main.LECTURE_RUNTIME_STATE[session_code] = "running"
    main.LECTURE_CONTROL_STATE[session_code] = False
    main.LECTURE_SESSIONS[session_code] = {
        "title": "Two payload slides",
        "slides": [{"heading": "First payload slide"}, {"heading": "Second payload slide"}],
        "narration": ["First notes", "Second notes"],
    }

    async def run_task_once():
        task = asyncio.create_task(main.auto_advance_lecture(session_code))
        await asyncio.sleep(0.04)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run_task_once())

    slide_messages = [message for message in websocket.messages if message.get("type") == "slide_advance"]
    assert slide_messages, "running lecture should broadcast slide_advance messages"
    assert slide_messages[0]["slide_index"] == 1
    assert slide_messages[0]["state"] == "running"
    assert slide_messages[0]["paused"] is False


def test_pause_and_end_prevent_autonomous_slide_advancement(monkeypatch):
    main = load_main(monkeypatch)

    _session_id, session_code = main.create_session()
    websocket = FakeWebSocket()
    main.WEBSOCKET_CONNECTIONS[session_code] = [websocket]
    main.LECTURE_RUNTIME_STATE[session_code] = "running"
    main.LECTURE_CONTROL_STATE[session_code] = True

    async def run_paused_then_ended():
        task = asyncio.create_task(main.auto_advance_lecture(session_code))
        await asyncio.sleep(0.03)
        assert not [message for message in websocket.messages if message.get("type") == "slide_advance"]
        main.LECTURE_CONTROL_STATE[session_code] = False
        main.LECTURE_RUNTIME_STATE[session_code] = "ended"
        await asyncio.sleep(0.02)
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run_paused_then_ended())

    slide_messages = [message for message in websocket.messages if message.get("type") == "slide_advance"]
    assert slide_messages == []
    assert main.LECTURE_AUTONOMOUS_TASKS.get(session_code) is None or main.LECTURE_AUTONOMOUS_TASKS[session_code].done()


def test_build_lecture_status_returns_compact_current_slide(monkeypatch):
    main = load_main(monkeypatch)

    _session_id, session_code = main.create_session()
    main.LECTURE_SESSIONS[session_code] = {
        "title": "Status Test",
        "slides": [
            {
                "heading": "Intro",
                "body": "<p>Short body for Hermes.</p>",
                "duration": 3,
                "wait": False,
                "media": [],
            },
            {
                "heading": "Checkpoint",
                "body": "<p>Ask students to explain the model.</p>",
                "duration": 4,
                "wait": True,
                "media": [{"type": "image", "value": "cell.png", "url": "/media/images/cell.png"}],
            },
        ],
    }
    main.LECTURE_RUNTIME_STATE[session_code] = "running"
    main.LECTURE_CONTROL_STATE[session_code] = False
    main.LECTURE_SLIDE_INDEX[session_code] = 1
    main.mark_slide_started(session_code)

    status_payload = main.build_lecture_status(session_code)

    assert status_payload["current_slide_index"] == 1
    assert status_payload["current_slide"] == {"heading": "Checkpoint", "body_summary": "Ask students to explain the model."}
    assert status_payload["is_paused"] is False
    assert status_payload["wait_mode"] is True
    assert status_payload["total_slides"] == 2
    assert status_payload["media_on_slide"] == [{"type": "image", "value": "cell.png", "url": "/media/images/cell.png"}]
    assert isinstance(status_payload["time_on_slide_seconds"], float)
