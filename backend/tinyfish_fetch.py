import os, re, httpx
HEADERS = {"X-API-Key": os.environ.get("TINYFISH_API_KEY", "")}

async def fetch_markdown(urls: list[str]) -> dict:
    async with httpx.AsyncClient(timeout=150) as client:
        r = await client.post("https://api.fetch.tinyfish.ai", headers=HEADERS,
                              json={"urls": urls[:10], "format": "markdown"})
        r.raise_for_status()
        return r.json()                         # {"results": [...], "errors": [...]}

async def accessibility_statement(home_url: str) -> dict:
    data = await fetch_markdown([home_url])
    text = data["results"][0]["text"] if data.get("results") else ""
    m = re.search(r"\[([^\]]*accessib[^\]]*)\]\(([^)]+)\)", text, re.I)
    return {"type": "accessibility_statement", "found": bool(m), "url": m.group(2) if m else None}
