import backend.tinyfish_browser as tb


async def test_sessions_left_open_are_ended_on_shutdown(monkeypatch):
    ended = []

    async def fake_end(session_id):
        ended.append(session_id)
        tb.OPEN_SESSIONS.discard(session_id)

    monkeypatch.setattr(tb, "end_session", fake_end)
    monkeypatch.setattr(tb, "OPEN_SESSIONS", {"tf-a", "tf-b"})
    await tb.end_open_sessions()
    assert sorted(ended) == ["tf-a", "tf-b"] and tb.OPEN_SESSIONS == set()
