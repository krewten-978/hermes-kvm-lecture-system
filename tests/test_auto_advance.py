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
    main.LECTURE_SESSIONS[session_code] = {"title": "One payload slide", "slides": [{"heading": "Only payload slide"}], "narration": ["Notes"]}

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
