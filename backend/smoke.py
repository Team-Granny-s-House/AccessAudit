"""P0 smoke test: one call to each TinyFish API against example.com.

Usage: python -m backend.smoke [agent] [browser] [fetch]   (default: all three)
Agent and Browser are metered; Fetch is free up to 1,000 URLs a day.
"""
import asyncio, json, os, sys

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

TARGET = "https://example.com"
HEADERS = {"X-API-Key": os.environ.get("TINYFISH_API_KEY", "")}
AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"
BROWSER_API = "https://api.browser.tinyfish.ai"
FETCH_API = "https://api.fetch.tinyfish.ai"


async def check_agent() -> str:
    payload = {"url": TARGET, "goal": "Return the main heading of this page",
               "browser_profile": "lite", "agent_config": {"max_duration_seconds": 240}}
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", AGENT_URL, headers=HEADERS, json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event.get("type") == "COMPLETE":
                    if event.get("status") != "COMPLETED" or not event.get("result"):
                        raise RuntimeError(f"run did not succeed: {event}")
                    return f"result {json.dumps(event['result'])}"
    raise RuntimeError("stream ended without a COMPLETE event")


async def check_browser() -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BROWSER_API, headers=HEADERS,
                              json={"url": TARGET, "timeout_seconds": 300})
        r.raise_for_status()
        session = r.json()
        try:
            pw = await async_playwright().start()
            try:
                browser = await pw.chromium.connect_over_cdp(session["cdp_url"])
                await asyncio.sleep(2)                  # let startup navigation settle
                page = browser.contexts[0].pages[0]
                await page.wait_for_load_state("domcontentloaded")
                title = await page.title()
                await browser.close()
            finally:
                await pw.stop()
        finally:
            d = await client.delete(f"{BROWSER_API}/{session['session_id']}", headers=HEADERS)
    if d.status_code != 204:
        raise RuntimeError(f"title {title!r}, but session DELETE returned {d.status_code}")
    return f"title {title!r}, session deleted (204)"


async def check_fetch() -> str:
    async with httpx.AsyncClient(timeout=150) as client:
        r = await client.post(FETCH_API, headers=HEADERS,
                              json={"urls": [TARGET], "format": "markdown"})
        r.raise_for_status()
        data = r.json()
    if not data.get("results"):
        raise RuntimeError(f"no results: {data.get('errors')}")
    return f"title {data['results'][0]['title']!r}"


CHECKS = {"agent": check_agent, "browser": check_browser, "fetch": check_fetch}


async def main(names: list[str]) -> int:
    if not HEADERS["X-API-Key"]:
        print("FAIL  TINYFISH_API_KEY is not set in .env")
        return 1
    failed = 0
    for name in names:
        try:
            print(f"OK    {name}: {await CHECKS[name]()}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    names = sys.argv[1:] or list(CHECKS)
    unknown = [n for n in names if n not in CHECKS]
    if unknown:
        sys.exit(f"unknown check(s): {', '.join(unknown)}; choose from {', '.join(CHECKS)}")
    sys.exit(asyncio.run(main(names)))
