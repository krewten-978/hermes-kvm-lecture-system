import importlib

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def load_main(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "phase-test-password")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "phase-test-secret")
    monkeypatch.setenv("LECTURE_SLIDE_SECONDS", "0.05")
    import app.main as main

    return importlib.reload(main)


def test_student_join_requires_valid_presenter_session_code_and_returns_token(monkeypatch):
    main = load_main(monkeypatch)
    _session_id, session_code = main.create_session()
    client = TestClient(main.app)

    invalid = client.post("/api/join", json={"session_code": "BADCODE"})
    assert invalid.status_code == 404

    response = client.post("/api/join", json={"session_code": session_code.lower()})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_code"] == session_code
    assert isinstance(payload["student_token"], str)
    assert len(payload["student_token"]) >= 24
    assert main.STUDENT_SESSIONS[payload["student_token"]]["session_code"] == session_code


def test_multiple_student_websockets_are_tracked_without_affecting_presenter_socket(monkeypatch):
    main = load_main(monkeypatch)
    session_id, session_code = main.create_session()
    client = TestClient(main.app)

    first_token = client.post("/api/join", json={"session_code": session_code}).json()["student_token"]
    second_token = client.post("/api/join", json={"session_code": session_code}).json()["student_token"]

    with client.websocket_connect("/ws/session", cookies={main.SESSION_COOKIE_NAME: session_id}) as presenter_ws:
        presenter_initial = presenter_ws.receive_json()
        assert presenter_initial["type"] == "control_state"
        assert presenter_initial["student_count"] == 0

        with client.websocket_connect(f"/ws/student?token={first_token}") as first_ws:
            first_initial = first_ws.receive_json()
            presenter_after_first = presenter_ws.receive_json()

            assert first_initial["type"] == "student_state"
            assert first_initial["session_code"] == session_code
            assert presenter_after_first["student_count"] == 1
            assert main.get_connected_student_count(session_code) == 1
            assert len(main.WEBSOCKET_CONNECTIONS[session_code]) == 1

            with client.websocket_connect(f"/ws/student?token={second_token}") as second_ws:
                second_initial = second_ws.receive_json()
                presenter_after_second = presenter_ws.receive_json()

                assert second_initial["type"] == "student_state"
                assert presenter_after_second["student_count"] == 2
                assert main.get_connected_student_count(session_code) == 2
                assert len(main.WEBSOCKET_CONNECTIONS[session_code]) == 1

            presenter_after_second_disconnect = presenter_ws.receive_json()
            assert presenter_after_second_disconnect["student_count"] == 1
            assert main.get_connected_student_count(session_code) == 1

        presenter_after_first_disconnect = presenter_ws.receive_json()
        assert presenter_after_first_disconnect["student_count"] == 0
        assert main.get_connected_student_count(session_code) == 0


def test_student_websocket_rejects_missing_or_unknown_token(monkeypatch):
    main = load_main(monkeypatch)
    client = TestClient(main.app)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/student"):
            pass

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/student?token=unknown-token"):
            pass
