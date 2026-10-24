# backend/tinyfish_browser.py
import os, asyncio, logging, httpx
from playwright.async_api import async_playwright

log = logging.getLogger("accessaudit")
BROWSER_API = "https://api.browser.tinyfish.ai"
HEADERS = {"X-API-Key": os.environ.get("TINYFISH_API_KEY", "")}

async def create_session(url: str) -> dict:
    body = {"url": url, "timeout_seconds": 900}
    if os.getenv("TF_BROWSER_PROXY", "default") == "direct":
        body["proxy_config"] = {"enabled": False}
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            r = await client.post(BROWSER_API, headers=HEADERS, json=body)
            if r.status_code == 429:
                await asyncio.sleep(float(r.headers.get("Retry-After", 5)))
                continue
            r.raise_for_status()
            session = r.json()                  # session_id, cdp_url, base_url
            log.info("browser session %s created", session["session_id"])
            return session
    raise RuntimeError("TinyFish Browser API rate-limited three times")

async def end_session(session_id: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BROWSER_API}/{session_id}", headers=HEADERS)
    log.info("browser session %s DELETE -> %s", session_id, r.status_code)

async def open_page(url: str):
    """Returns (pw, browser, page, session_id). session_id is None in local mode."""
    pw = await async_playwright().start()
    if os.getenv("WALKER_MODE", "tinyfish") == "local":    # development only
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        return pw, browser, page, None
    s = await create_session(url)
    browser = await pw.chromium.connect_over_cdp(s["cdp_url"])
    await asyncio.sleep(2)                      # let startup navigation settle
    page = browser.contexts[0].pages[0]
    await page.wait_for_load_state("domcontentloaded")
    return pw, browser, page, s["session_id"]

async def close_page(pw, browser, session_id) -> None:
    try:
        await browser.close()
    finally:
        await pw.stop()
        if session_id:
            await end_session(session_id)
