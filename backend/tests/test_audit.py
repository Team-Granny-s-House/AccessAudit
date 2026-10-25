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


async def run(copy, monkeypatch, tmp_path, baseline=fake_baseline, task=TASK):
    monkeypatch.setenv("WALKER_MODE", "local")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(audit, "run_baseline", baseline)
    events = []

    async def emit(type_, data):
        events.append((type_, data))

    record = {"id": "t1", "url": (DEMO / copy / "index.html").as_uri(), "task": task,
              "persona": "keyboard", "created_at": "2026-10-24T00:00:00Z"}
    return await audit.run_audit(record, emit), events


def counting(steps=AGENT_STEPS):
    """A fake Agent that counts how often it is called."""
    async def agent(url, task, on_event):
        agent.calls += 1
        return {"task_completed": True, "steps": steps}
    agent.calls = 0
    return agent


def data(events, type_):
    return next(d for t, d in events if t == type_)


async def test_live_baseline_is_cached_then_reused_without_the_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "1")
    agent = counting()
    first, events = await run("fixed", monkeypatch, tmp_path, agent)
    assert agent.calls == 1 and first["cached"] is False
    assert data(events, "baseline_started") == {"source": "agent", "cached": False}
    url = (DEMO / "fixed" / "index.html").as_uri()
    assert audit.cache_path(url, TASK).exists()

    second, events = await run("fixed", monkeypatch, tmp_path, agent)
    assert agent.calls == 1                                   # served from the cache
    assert (second["baseline_source"], second["cached"], second["verdict"]) == ("agent", True, "Completed")
    assert data(events, "baseline_started") == {"source": "agent", "cached": True}
    assert data(events, "baseline_done")["cached"] is True
    assert "streaming_url" not in [t for t, _ in events]


async def test_cache_off_always_calls_the_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "1")
    agent = counting()
    await run("fixed", monkeypatch, tmp_path, agent)
    monkeypatch.setenv("CACHE_BASELINES", "0")
    report, _ = await run("fixed", monkeypatch, tmp_path, agent)
    assert agent.calls == 2 and report["cached"] is False


async def test_a_baseline_the_walker_cannot_follow_is_not_cached(monkeypatch, tmp_path):
    agent = counting([{"action": "click", "element_text": "Book a holiday"}])
    report, _ = await run("fixed", monkeypatch, tmp_path, agent)
    assert report["verdict"] == "Inconclusive"
    assert not audit.cache_path((DEMO / "fixed" / "index.html").as_uri(), TASK).exists()


async def test_an_invalid_cached_baseline_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    path = audit.cache_path((DEMO / "fixed" / "index.html").as_uri(), TASK)
    path.parent.mkdir(parents=True)
    path.write_text('{"task_completed": false, "steps": [{"action": "click", "element_text": "Find trains"}]}')
    agent = counting()
    report, _ = await run("fixed", monkeypatch, tmp_path, agent)
    assert agent.calls == 1 and report["cached"] is False


async def test_the_task_string_is_part_of_the_cache_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "1")
    agent = counting()
    await run("fixed", monkeypatch, tmp_path, agent)
    await run("fixed", monkeypatch, tmp_path, agent, task=TASK.rstrip("."))   # one character different
    assert agent.calls == 2


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


def failing_agent(*codes, steps=AGENT_STEPS):
    """A fake Agent that fails with each code in turn (per call), then succeeds; records the profiles used."""
    async def agent(url, task, on_event, profile="lite"):
        agent.profiles.append(profile)
        if len(agent.profiles) <= len(codes):
            code = codes[len(agent.profiles) - 1]
            if isinstance(code, Exception):
                raise code
            raise audit.AgentFailed(code, f"{code.lower()} on this site")
        return {"task_completed": True, "steps": steps}
    agent.profiles = []
    return agent


async def test_blocked_site_is_retried_once_with_the_stealth_browser(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "0")
    agent = failing_agent("SITE_BLOCKED")
    report, events = await run("fixed", monkeypatch, tmp_path, agent)
    assert agent.profiles == ["lite", "stealth"]
    assert (report["verdict"], report["error"]) == ("Completed", None)
    assert any("stealth" in d.get("text", "") for t, d in events if t == "baseline_progress")


async def test_still_blocked_after_the_retry_explains_why(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "0")
    agent = failing_agent("SITE_BLOCKED", "SITE_BLOCKED")
    report, events = await run("fixed", monkeypatch, tmp_path, agent)
    assert agent.profiles == ["lite", "stealth"]
    assert report["verdict"] == "Inconclusive" and "blocked" in report["error"]
    assert data(events, "error")["message"] == report["error"]
    assert "baseline_done" not in [t for t, _ in events]


async def test_other_agent_failures_are_not_retried_and_are_explained(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "0")
    agent = failing_agent("MAX_STEPS_EXCEEDED")
    report, _ = await run("fixed", monkeypatch, tmp_path, agent)
    assert agent.profiles == ["lite"]
    assert report["status"] == "done" and report["verdict"] == "Inconclusive"
    assert "max_steps_exceeded on this site" in report["error"]


async def test_an_api_key_problem_gets_a_plain_message(monkeypatch, tmp_path):
    import httpx
    monkeypatch.setenv("CACHE_BASELINES", "0")
    request = httpx.Request("POST", "https://agent.tinyfish.ai/v1/automation/run-sse")
    denied = httpx.HTTPStatusError("401", request=request, response=httpx.Response(401, request=request))
    report, _ = await run("fixed", monkeypatch, tmp_path, failing_agent(denied))
    assert report["error"] == "TinyFish rejected the API key. Check TINYFISH_API_KEY in .env."


async def test_a_label_mismatch_is_explained(monkeypatch, tmp_path):
    monkeypatch.setenv("CACHE_BASELINES", "0")
    agent = counting([{"action": "click", "element_text": "Book a holiday"}])
    report, _ = await run("fixed", monkeypatch, tmp_path, agent)
    assert report["verdict"] == "Inconclusive" and "“Book a holiday”" in report["error"]


async def test_a_clean_run_has_no_error(monkeypatch, tmp_path):
    report, _ = await run("fixed", monkeypatch, tmp_path)
    assert report["error"] is None
