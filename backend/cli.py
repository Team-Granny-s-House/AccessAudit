"""Command-line tools.

python -m backend.cli scan <url>                         axe-core scan of one page
python -m backend.cli audit <url> "<task>" [--override]  full audit; prints each event, then the report JSON

WALKER_MODE=local uses a local Chromium (free); otherwise a TinyFish Browser session is used.
--override uses the hand-checked steps in backend/baselines/ instead of calling the Agent.
"""
import argparse, asyncio, json, logging, os, sys, time, uuid
from datetime import datetime, timezone

from backend.audit import run_audit
from backend.axe_scan import AxeError, axe_scan
from backend.tinyfish_browser import close_page, open_page

IMPACT_ORDER = ["critical", "serious", "moderate", "minor"]


async def scan(url: str) -> int:
    print(f"scan {url}  (WALKER_MODE={os.getenv('WALKER_MODE', 'tinyfish')})")
    pw, browser, page, session_id = await open_page(url)
    try:
        violations = await axe_scan(page)
    except AxeError as e:
        print(f"error: {e}")
        return 1
    finally:
        await close_page(pw, browser, session_id)
    violations.sort(key=lambda v: IMPACT_ORDER.index(v["impact"]) if v["impact"] in IMPACT_ORDER else 9)
    for v in violations:
        print(f"{v['impact']:<9} {v['rule']:<24} {v['count']:>3} element(s)  {v['help']}")
    print(f"{len(violations)} rule(s) violated")
    return 0


async def audit(url: str, task: str, override: bool, persona: str) -> int:
    print(f"audit {url}  (WALKER_MODE={os.getenv('WALKER_MODE', 'tinyfish')}, "
          f"baseline={'override' if override else 'agent'})")
    record = {"id": uuid.uuid4().hex[:8], "url": url, "task": task, "persona": persona,
              "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    start = time.monotonic()

    async def emit(type_: str, data: dict):
        line = json.dumps(data, ensure_ascii=False)
        if len(line) > 200 and type_ != "baseline_done":   # the baseline's steps are printed in full
            line = line[:200] + "…"
        print(f"[{time.monotonic() - start:6.1f}s] {type_:<17} {line}", flush=True)

    report = await run_audit(record, emit, use_override=override)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "done" else 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")       # ₹ and quotes in output on a Windows console
    logging.basicConfig(level=logging.INFO, format="  log: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="python -m backend.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan", help="axe-core scan of one page")
    p_scan.add_argument("url")
    p_audit = sub.add_parser("audit", help="full audit: baseline, keyboard walker, scans, score")
    p_audit.add_argument("url")
    p_audit.add_argument("task")
    p_audit.add_argument("--override", action="store_true", help="use the hand-checked baseline, skip the Agent")
    p_audit.add_argument("--persona", choices=["screen_reader", "keyboard"], default="screen_reader")
    args = parser.parse_args()
    if args.command == "scan":
        return asyncio.run(scan(args.url))
    return asyncio.run(audit(args.url, args.task, args.override, args.persona))


if __name__ == "__main__":
    sys.exit(main())
