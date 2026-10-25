"""Phase P3 check: start an audit through the API, print its live events, then compare report and replay.

python -m backend.ws_client <url> "<task>" [--api http://localhost:8000] [--persona screen_reader|keyboard]
"""
import argparse, asyncio, json, sys

import httpx
import websockets

REPORT_KEYS = {"id", "url", "task", "persona", "created_at", "status", "verdict", "score", "blocked_at",
               "total_steps", "baseline_source", "cached", "error", "steps", "issues", "transcript", "page_scans", "notes"}


async def main(api: str, url: str, task: str, persona: str) -> int:
    async with httpx.AsyncClient(base_url=api, timeout=30) as http:
        r = await http.post("/audits", json={"url": url, "task": task, "persona": persona})
        print(f"POST /audits -> {r.status_code} {r.text}")
        r.raise_for_status()
        audit_id = r.json()["id"]

        second = await http.post("/audits", json={"url": url, "task": task, "persona": persona})
        print(f"second POST while running -> {second.status_code}")

        events = []
        ws_url = api.replace("http", "ws", 1) + f"/audits/{audit_id}/events"
        async with websockets.connect(ws_url, max_size=None) as ws:
            async for message in ws:              # ends when the server closes the socket after "done"
                event = json.loads(message)
                events.append(event)
                line = json.dumps(event["data"], ensure_ascii=False)
                print(f"[{event['t']:7.2f}s] {event['type']:<17} {line[:150]}")
        print(f"socket closed after {events[-1]['type']!r} ({len(events)} events)")

        report = (await http.get(f"/audits/{audit_id}")).json()
        replay = (await http.get(f"/audits/{audit_id}/replay")).json()
        missing = REPORT_KEYS - set(report)
        print(f"GET /audits/{audit_id}: status={report['status']} verdict={report['verdict']!r} "
              f"score={report['score']} missing keys={sorted(missing) or 'none'}")
        print(f"GET /audits/{audit_id}/replay: {len(replay)} events, same as the socket: {replay == events}")
        ok = second.status_code == 409 and events[-1]["type"] == "done" and not missing and replay == events
        print("P3 check:", "PASS" if ok else "FAIL")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m backend.ws_client")
    p.add_argument("url")
    p.add_argument("task")
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--persona", choices=["screen_reader", "keyboard"], default="screen_reader")
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.api, a.url, a.task, a.persona)))
