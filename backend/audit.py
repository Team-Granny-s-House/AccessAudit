# backend/audit.py
"""Orchestrator: baseline -> keyboard walker -> scans -> score."""
import asyncio, hashlib, json, logging, os
from pathlib import Path

from backend.axe_scan import AxeError, axe_scan
from backend.issues import (IssueLog, axe_issue, drop_named_duplicates, name_of, sort_issues,
                            stop_findings, walker_issue)
from backend.scoring import BLOCKED, score_audit
import httpx

from backend.tinyfish_agent import AgentFailed, normalize_result, run_baseline
from backend.tinyfish_browser import close_page, open_page
from backend.tinyfish_fetch import accessibility_statement
from backend.walker import Screenshots, activate, reach

log = logging.getLogger("accessaudit")
BASELINES = Path(__file__).parent / "baselines"
TRANSCRIPT_FIELDS = ("seq", "tag", "text", "announce", "focus_ring", "page_url")
BLOCKED_CHECK = {"unreachable": "kb_unreachable", "trap": "kb_trap", "no_response": "kb_no_response"}
SHOTS_PER_CHECK_PER_PAGE = 3    # later issues of the same kind on the same page are reported without a screenshot


def load_override(url: str) -> dict | None:
    """Hand-checked baseline for this URL, from backend/baselines/index.json."""
    index = json.loads((BASELINES / "index.json").read_text(encoding="utf-8"))
    name = index.get(url) or index.get(url.rstrip("/"))
    return json.loads((BASELINES / name).read_text(encoding="utf-8")) if name else None


def cache_path(url: str, task: str) -> Path:
    """DATA_DIR/cache/baselines/{sha1(url + task)}.json: the exact task string is part of the key."""
    key = hashlib.sha1((url + task).encode("utf-8")).hexdigest()
    return Path(os.getenv("DATA_DIR", "./data")) / "cache" / "baselines" / f"{key}.json"


def load_cached(url: str, task: str) -> dict | None:
    """A saved Agent baseline for this URL and task, if CACHE_BASELINES=1 and it is still valid."""
    path = cache_path(url, task)
    if os.getenv("CACHE_BASELINES", "1") != "1" or not path.exists():
        return None
    try:
        return normalize_result(json.loads(path.read_text(encoding="utf-8")))
    except ValueError:
        log.warning("ignoring unreadable cached baseline %s", path.name)
        return None


def save_cached(url: str, task: str, baseline: dict) -> None:
    path = cache_path(url, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("saved the Agent baseline to the cache (%s)", path.name)


def planned_baseline(audit: dict, use_override: bool, override: dict | None):
    """A baseline that needs no Agent call, as (baseline, source, cached), or None to run the live Agent."""
    if use_override and override:
        return override, "override", False         # CLI --override
    cached = load_cached(audit["url"], audit["task"])
    if not cached:
        return None
    if override and os.getenv("FORCE_BASELINE_OVERRIDE", "0") == "1":
        return override, "override", False
    log.info("using the cached Agent baseline; the Agent is not called")
    return cached, "agent", True


def friendly_error(e: Exception) -> str:
    """A plain-English reason for an exception, for the UI and the report."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            return "TinyFish rejected the API key. Check TINYFISH_API_KEY in .env."
        if status == 402:
            return "TinyFish says the account is out of credits."
        if status == 429:
            return "TinyFish is rate-limiting requests. Wait a minute and try again."
        return f"TinyFish returned an error ({status})."
    if isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
        return "Couldn't reach TinyFish. Check the internet connection."
    return str(e) or type(e).__name__


NO_BASELINE = ("The sighted agent didn't report finishing the task, so there's nothing to compare against. "
               "Check that the task can be done without logging in or paying.")


async def run_agent(audit: dict, emit, override: dict | None):
    """The live Agent baseline, with a stealth retry and the hand-checked fallback.

    Returns (baseline or None, source, reason): `reason` explains a missing baseline."""

    async def on_event(e):
        if e.get("type") == "STREAMING_URL":
            await emit("streaming_url", {"url": e.get("streaming_url")})
        elif e.get("type") == "PROGRESS":
            await emit("baseline_progress", {"text": e.get("purpose", "")})

    baseline, reason = None, None
    try:
        baseline = await run_baseline(audit["url"], audit["task"], on_event)
    except AgentFailed as e:
        if e.code == "SITE_BLOCKED":
            log.info("the site blocked the agent; retrying once with the stealth browser")
            await emit("baseline_progress", {"text": "The site blocked the agent. Retrying once with "
                                                     "TinyFish's stealth browser."})
            try:
                baseline = await run_baseline(audit["url"], audit["task"], on_event, profile="stealth")
            except AgentFailed:
                reason = ("The site blocked TinyFish's agent, even with its stealth browser, "
                          "so there's nothing to compare against.")
            except Exception as e2:
                reason = friendly_error(e2)
        else:
            reason = f"The sighted agent couldn't complete the task ({e}), so there's nothing to compare against."
    except Exception as e:
        reason = friendly_error(e)
    if baseline is None:
        reason = reason or NO_BASELINE
        log.warning("agent baseline unusable: %s%s", reason, "; using the hand-checked steps" if override else "")
    if override and (baseline is None or os.getenv("FORCE_BASELINE_OVERRIDE", "0") == "1"):
        return override, "override", None
    return baseline, "agent", reason


async def walk(audit: dict, steps: list[dict], emit, report: dict, issues: IssueLog) -> list[dict]:
    """Replays the baseline with the keyboard only. Stops at the first blocked step."""
    shots = Screenshots(audit["id"], os.getenv("DATA_DIR", "./data"))
    stops, results, scanned, pending_axe = [], [], set(), {}
    state = {"step": 0, "prev": None}
    shot_counts: dict[tuple, int] = {}              # (page, check) -> screenshots taken so far

    async def flush(url):                           # axe issues wait until the page's walker stops are known
        for issue in drop_named_duplicates(pending_axe.pop(url, []), issues.items):
            await emit("issue", issues.add(issue))

    async def on_stop(stop):
        await emit("walker_stop", {k: stop[k] for k in TRANSCRIPT_FIELDS})
        for f in stop_findings(stop, state["prev"]):
            if issues.seen(f["key"]):
                continue
            # each screenshot costs ~10 s in a cloud browser: keep the first few of a kind per page
            counted = (stop["page_url"], f["check"])
            shot = None
            if shot_counts.get(counted, 0) < SHOTS_PER_CHECK_PER_PAGE:
                shot_counts[counted] = shot_counts.get(counted, 0) + 1
                shot = await shots.take(page, outline=True)
            issue = walker_issue(f["check"], step_index=state["step"], page_url=stop["page_url"], name=f["name"],
                                 announce=stop["announce"], element_html=stop["html"], screenshot=shot)
            await emit("issue", issues.add(issue, key=f["key"]))
        state["prev"] = stop

    pw, browser, page, session_id = await open_page(audit["url"])
    try:
        last_url = None
        for i, step in enumerate(steps):
            state["step"] = i
            if page.url != last_url:
                if last_url:
                    await flush(last_url)
                last_url = page.url
                if page.url not in scanned:           # axe-core once per page
                    scanned.add(page.url)
                    shot = await shots.take(page)
                    try:
                        violations, error = await axe_scan(page), None
                    except AxeError as e:
                        violations, error = [], str(e)
                    scan = {"url": page.url, "violations": violations, "error": error}
                    report["page_scans"].append(scan)
                    await emit("page_scan", scan)
                    pending_axe[page.url] = [axe_issue(v, step_index=i, page_url=page.url, screenshot=shot)
                                             for v in violations]

            hit = await reach(page, step["element_text"], stops, on_stop)
            element = hit.get("element")
            if hit["status"] == "found":
                hit = {**await activate(page, step, element), "presses": hit["presses"]}
            status, shot = hit["status"], None
            if status in BLOCKED:
                el = element or (stops[-1] if status == "trap" and stops else {})
                shot = await shots.take(page, outline=True)
                name = (name_of(el) if el else "") or step["element_text"]
                issue = walker_issue(BLOCKED_CHECK[status], step_index=i, page_url=page.url, name=name,
                                     announce=el.get("announce", ""), element_html=el.get("html", ""),
                                     screenshot=shot)
                await emit("issue", issues.add(issue))
            result = {"index": i, "status": status, "presses": hit.get("presses", 0), "screenshot": shot}
            results.append(result)
            report["steps"].append({"index": i, "action": step.get("action"), "element_text": step["element_text"],
                                    "description": step.get("description"), "status": status,
                                    "presses": result["presses"], "screenshot": shot})
            await emit("step_result", result)
            if status not in ("activated", "typed"):
                break       # stuck (unreachable, trap, no_response), wrong baseline, or safely at the final submit
        for url in list(pending_axe):
            await flush(url)
    finally:
        report["transcript"] = [{k: s[k] for k in TRANSCRIPT_FIELDS} for s in stops]
        await close_page(pw, browser, session_id)
    return results


async def run_audit(audit: dict, emit, use_override: bool = False) -> dict:
    """audit: id, url, task, persona, created_at. emit: async (type, data). Returns the report JSON."""
    report = {**{k: audit[k] for k in ("id", "url", "task", "persona", "created_at")},
              "status": "running", "verdict": None, "score": None, "blocked_at": None, "total_steps": 0,
              "baseline_source": None, "cached": False, "error": None, "steps": [], "issues": [],
              "transcript": [], "page_scans": [], "notes": []}
    issues = IssueLog()
    note_task = None
    try:
        override = load_override(audit["url"])
        plan = planned_baseline(audit, use_override, override)
        await emit("baseline_started", {"source": plan[1] if plan else "agent", "cached": bool(plan and plan[2])})

        async def statement_note():
            try:
                note = await accessibility_statement(audit["url"])
            except Exception as e:
                log.warning("accessibility statement check failed: %s", e)
                return
            report["notes"].append(note)
            await emit("note", note)
        note_task = asyncio.create_task(statement_note())

        reason = None
        if plan:
            baseline, source, cached = plan
        else:
            (baseline, source, reason), cached = await run_agent(audit, emit, override), False
        report.update(baseline_source=source, cached=cached)
        steps = baseline["steps"] if baseline else []
        report["total_steps"] = len(steps)
        results = []
        if baseline:
            await emit("baseline_done", {"steps": steps, "source": source, "cached": cached})
            results = await walk(audit, steps, emit, report, issues)
            mismatch = next((r for r in results if r["status"] == "baseline_mismatch"), None)
            if mismatch:
                reason = (f"The keyboard walker couldn't find “{steps[mismatch['index']]['element_text']}” on the "
                          "page. The sighted agent may have recorded the wrong label, so this audit is "
                          "Inconclusive rather than a failure of the site.")
            elif source == "agent" and not cached and results:   # only baselines the walker could follow
                save_cached(audit["url"], audit["task"], baseline)
        if reason:
            report["error"] = reason
            await emit("error", {"message": reason})
        await note_task
        outcome = score_audit(steps, results, issues.items, baseline_ok=bool(baseline))
        report.update(outcome, status="done", issues=sort_issues(issues.items))
        await emit("done", outcome)
    except Exception as e:
        log.exception("audit %s failed", audit["id"])
        if note_task:
            note_task.cancel()
        message = f"The audit stopped: {friendly_error(e)}"
        await emit("error", {"message": message})
        outcome = {"verdict": "Inconclusive", "score": None, "blocked_at": None,
                   "total_steps": report["total_steps"]}
        report.update(outcome, status="error", error=message, issues=sort_issues(issues.items))
        await emit("done", outcome)
    return report
