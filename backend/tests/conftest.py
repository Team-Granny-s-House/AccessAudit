from pathlib import Path

import httpx
import pytest

from backend.tinyfish_browser import close_page, open_page

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests must never call TinyFish (it spends credits): any httpx request fails."""
    async def blocked(*args, **kwargs):
        raise RuntimeError("tests must not make HTTP calls")
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)


@pytest.fixture
async def open_fixture(monkeypatch):
    """Opens a fixture page in a local Chromium (WALKER_MODE=local, never TinyFish)."""
    monkeypatch.setenv("WALKER_MODE", "local")
    opened = []

    async def _open(name: str):
        pw, browser, page, session_id = await open_page((FIXTURES / name).as_uri())
        opened.append((pw, browser, session_id))
        return page

    yield _open
    for pw, browser, session_id in opened:
        await close_page(pw, browser, session_id)
