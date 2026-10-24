"""Whole-orchestrator runs on the SkyRail copies from disk, with a fake Agent (no TinyFish calls)."""
from pathlib import Path

import backend.audit as audit

DEMO = Path(__file__).resolve().parents[2] / "demo-site"
TASK = "Find trains, select the first train, and enter the passenger name Asha Verma."
AGENT_STEPS = [   # the shape the Agent should return: exact labels, already-set dropdowns included
    {"action": "select", "element_text": "From", "value": "New Delhi", "description": "Choose the departure station"},
    {"action": "select", "element_text": "To", "value": "Mumbai", "description": "Choose the destination"},
    {"action": "select", "element_text": "Journey date", "value": "Fri 24 Oct", "description": "Choose the date"},
    {"action": "click", "element_text": "Find trains", "description": "Search for trains"},
    {"action": "click", "element_text": "Select", "description": "Choose the first train"},
    {"action": "type", "element_text": "Passenger name", "value": "Asha Verma", "description": "Enter the name"},
]


async def fake_baseline(url, task, on_event):
    await on_event({"type": "STREAMING_URL", "streaming_url": "https://stream.example/live"})
    await on_event({"type": "PROGRESS", "purpose": "Search for trains"})
    return {"task_completed": True, "steps": AGENT_STEPS}


async def run(copy, monkeypatch, tmp_path):
    monkeypatch.setenv("WALKER_MODE", "local")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(audit, "run_baseline", fake_baseline)
    events = []

    async def emit(type_, data):
        events.append((type_, data))

    record = {"id": "t1", "url": (DEMO / copy / "index.html").as_uri(), "task": TASK,
              "persona": "keyboard", "created_at": "2026-10-24T00:00:00Z"}
    return await audit.run_audit(record, emit), events


async def test_fixed_copy_completes_with_agent_steps(monkeypatch, tmp_path):
    report, events = await run("fixed", monkeypatch, tmp_path)
    assert (report["verdict"], report["score"], report["status"]) == ("Completed", 100, "done")
    assert [s["status"] for s in report["steps"]] == ["activated"] * 5 + ["typed"]
    assert report["steps"][4]["description"] == "Choose the first train"
    assert report["baseline_source"] == "agent" and report["issues"] == []
    types = [t for t, _ in events]
    assert types[0] == "baseline_started" and types[-1] == "done"
    assert types.index("streaming_url") < types.index("baseline_done") < types.index("walker_stop")


async def test_broken_copy_is_blocked_at_the_trap(monkeypatch, tmp_path):
    report, _ = await run("broken", monkeypatch, tmp_path)
    assert report["verdict"] == "Blocked at step 5 of 6" and report["score"] <= 40
    found = {i["check"] for i in report["issues"]}
    assert {"kb_trap", "no_name", "focus_invisible", "axe:html-has-lang", "axe:image-alt",
            "axe:color-contrast"} <= found
    assert "axe:button-name" not in found                     # the walker's no_name covers it
    trap = next(i for i in report["issues"] if i["check"] == "kb_trap")
    assert (tmp_path / "screens" / "t1" / Path(trap["screenshot"]).name).exists()
