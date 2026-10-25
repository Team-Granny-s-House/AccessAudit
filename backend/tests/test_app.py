"""The API end to end in-process: local Chromium, a fake Agent, the SkyRail copies from disk (no TinyFish)."""
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

import backend.app as app_module
import backend.audit as audit
from backend import store

DEMO = Path(__file__).resolve().parents[2] / "demo-site"
TASK = "Find trains, select the first train, and enter the passenger name Asha Verma."
STEPS = [
    {"action": "click", "element_text": "Find trains", "description": "Search for trains"},
    {"action": "click", "element_text": "Select", "description": "Choose the first train"},
    {"action": "type", "element_text": "Passenger name", "value": "Asha Verma", "description": "Enter the name"},
]
REPORT_KEYS = {"id", "url", "task", "persona", "created_at", "status", "verdict", "score", "blocked_at",
               "total_steps", "baseline_source", "cached", "error", "steps", "issues", "transcript", "page_scans", "notes"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WALKER_MODE", "local")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    async def fake_baseline(url, task, on_event):
        await on_event({"type": "STREAMING_URL", "streaming_url": "https://stream.example/live"})
        await on_event({"type": "PROGRESS", "purpose": "Search for trains"})
        await asyncio.sleep(0.3)                    # long enough for a second POST to see the lock
        return {"task_completed": True, "steps": STEPS}

    monkeypatch.setattr(audit, "run_baseline", fake_baseline)
    with TestClient(app_module.app) as c:
        yield c


def start(client, copy, persona="keyboard"):
    r = client.post("/audits", json={"url": (DEMO / copy / "index.html").as_uri(), "task": TASK, "persona": persona})
    assert r.status_code == 200
    return r.json()["id"]


def stream(client, audit_id):
    events = []
    with client.websocket_connect(f"/audits/{audit_id}/events") as ws:
        while True:
            try:
                events.append(ws.receive_json())
            except WebSocketDisconnect:              # the server closes the socket after "done"
                return events


def test_audit_runs_through_the_api(client):
    audit_id = start(client, "fixed")
    busy = client.post("/audits", json={"url": (DEMO / "fixed" / "index.html").as_uri(), "task": TASK})
    assert busy.status_code == 409

    events = stream(client, audit_id)
    types = [e["type"] for e in events]
    assert types[0] == "baseline_started" and types[-1] == "done"
    assert types.index("streaming_url") < types.index("baseline_done") < types.index("walker_stop")
    assert all({"type", "t", "data"} == set(e) for e in events)
    times = [e["t"] for e in events]
    assert times == sorted(times)                   # in the order they happened
    assert events[-1]["data"]["verdict"] == "Completed"
    assert not app_module.audit_lock.locked()

    report = client.get(f"/audits/{audit_id}").json()
    assert set(report) == REPORT_KEYS
    assert (report["status"], report["verdict"], report["score"], report["persona"]) == \
        ("done", "Completed", 100, "keyboard")
    assert [s["description"] for s in report["steps"]] == [s["description"] for s in STEPS]
    assert client.get(f"/audits/{audit_id}/replay").json() == events
    assert client.get("/audits").json()[0] == {
        "id": audit_id, "url": report["url"], "task": TASK, "persona": "keyboard",
        "created_at": report["created_at"], "status": "done", "verdict": "Completed", "score": 100}


def test_broken_audit_is_stored_with_screenshots(client):
    audit_id = start(client, "broken")
    events = stream(client, audit_id)
    assert events[-1]["data"] == {"verdict": "Blocked at step 2 of 3", "score": 20, "blocked_at": 2, "total_steps": 3}

    report = client.get(f"/audits/{audit_id}").json()
    trap = next(i for i in report["issues"] if i["check"] == "kb_trap")
    shot = client.get(trap["screenshot"])
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"

    with Session(store.engine()) as s:
        assert s.get(store.Audit, audit_id).verdict == "Blocked at step 2 of 3"
        assert len(s.exec(select(store.Issue).where(store.Issue.audit_id == audit_id)).all()) == len(report["issues"])
        assert len(s.exec(select(store.Stop).where(store.Stop.audit_id == audit_id)).all()) == len(report["transcript"])
        assert [st.walker_status for st in s.exec(select(store.Step).where(store.Step.audit_id == audit_id))] == \
            ["activated", "trap"]


def test_a_late_websocket_gets_the_whole_log(client):
    audit_id = start(client, "fixed")
    live = stream(client, audit_id)
    assert stream(client, audit_id) == live         # connecting after "done" replays everything, then closes


def test_bad_requests(client):
    assert client.get("/audits/nope").status_code == 404
    assert client.get("/audits/nope/replay").status_code == 404
    assert client.get("/audits/nope/pdf").status_code == 404
    assert client.post("/audits", json={"url": "ftp://example.com", "task": TASK}).status_code == 422
    assert client.post("/audits", json={"url": "https://example.com", "task": TASK,
                                        "persona": "robot"}).status_code == 422
    assert client.get("/files/../backend/app.py").status_code == 404
    assert client.get("/files/%2e%2e/%2e%2e/.env").status_code == 404
