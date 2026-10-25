# backend/walker.py
import re
from pathlib import Path

from rapidfuzz import fuzz

FOCUS_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const r = el.getBoundingClientRect(), s = getComputedStyle(el);
  return {
    tag: el.tagName.toLowerCase(),
    text: (el.getAttribute('aria-label') || el.innerText || el.value || el.title || '').trim().slice(0, 120),
    rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
    page_x: Math.round(r.left + window.scrollX),
    page_y: Math.round(r.top + window.scrollY),
    html: el.outerHTML.slice(0, 300),
    path: (() => {                         // DOM path: tells apart links with the same text and position
      const parts = [];
      for (let n = el; n && n.nodeType === 1 && n !== document.documentElement; n = n.parentElement) {
        let i = 1;
        for (let s = n.previousElementSibling; s; s = s.previousElementSibling) i++;
        parts.unshift(n.tagName.toLowerCase() + ':' + i);
      }
      return parts.join('>');
    })(),
    focus_ring: (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none'
  };
}"""

MAX_TABS = 120              # at least this many presses...
MAX_TABS_CEILING = 400      # ...or the page's focusable-element count plus a margin, up to this ceiling
MATCH_SCORE = 85
PARTIAL_MIN_LEN = 12        # partial (substring) matches only for labels this long: "Fees" must not match "Fee Portal"
COVERAGE = 0.6              # an element's text must cover this much of a longer label to match it
STOP_WORDS = ("pay", "submit", "confirm", "place order", "book now")
TEXT_TYPES = ("text", "search", "email", "tel", "number", "textarea")
PASSED = ("activated", "typed", "stopped_safely")


def announcement(snapshot: str) -> str:
    """First line of Playwright's aria snapshot, e.g. '- button "Search trains"' or '- button'."""
    first = snapshot.strip().splitlines()[0] if snapshot.strip() else ""
    return first.rstrip(":").rstrip()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def similar(target: str, text: str) -> bool:
    """Whole-label similarity, plus two kinds of substring match:
    the element's text contains a long label (a card link with extra text), or the label is the element's
    text plus a little (the agent added a word). A single word of a long label never matches."""
    target, text = _norm(target), _norm(text)
    if not target or not text:
        return False
    if target == text or fuzz.ratio(target, text) >= MATCH_SCORE:
        return True
    if fuzz.partial_ratio(target, text) < 90:
        return False
    if len(text) >= len(target):
        return len(target) >= PARTIAL_MIN_LEN
    return len(text) >= COVERAGE * len(target)


def matches(target_text: str, info: dict) -> bool:
    """Match against the visible text and the announced name (a checkbox's text is just its value)."""
    named = re.match(r'^- \w+ "(.*)"', info["announce"] or "")
    return similar(target_text, info["text"]) or bool(named and similar(target_text, named.group(1)))


def signature(info: dict) -> tuple:
    """Which element has focus: its DOM path (falls back to tag, text and position)."""
    return (info.get("path"),) if info.get("path") else (info["tag"], info["text"], info["page_x"], info["page_y"])


async def focus_stop(page):
    info = await page.evaluate(FOCUS_JS)
    if info:
        # what a screen reader announces, e.g. '- button "Search trains"' or just '- button'
        try:
            info["announce"] = announcement(await page.locator(":focus").aria_snapshot(timeout=5000))
        except Exception:                           # focus moved away before the snapshot
            info["announce"] = ""
    return info


async def target_exists(page, target_text: str) -> bool:
    return (await page.get_by_text(target_text).count() > 0
            or await page.get_by_label(target_text).count() > 0)


FOCUSABLE_COUNT_JS = """() => Array.from(
  document.querySelectorAll('a[href], button, input, select, textarea, summary, iframe, [tabindex]')
).filter(e => e.tabIndex >= 0 && !e.disabled).length"""


async def tab_limit(page) -> int:
    """At least MAX_TABS presses; on big pages one per focusable element plus a margin, up to the ceiling."""
    try:
        count = await page.evaluate(FOCUSABLE_COUNT_JS)
    except Exception:
        return MAX_TABS
    return max(MAX_TABS, min(MAX_TABS_CEILING, count + 10))


async def reach(page, target_text, transcript, on_stop):
    """Tabs until the target has focus. Returns status found, unreachable, trap or baseline_mismatch."""
    seen, gap = [], False
    limit = await tab_limit(page)
    for presses in range(1, limit + 1):
        await page.keyboard.press("Tab")
        info = await focus_stop(page)
        if not info:
            gap = True                              # focus left the page content (end of the tab order)
            continue
        if info["rect"][2] == 0 or info["rect"][3] == 0:
            continue                                # skip links and off-screen helpers
        info["seq"] = len(transcript) + 1
        info["page_url"] = page.url
        info["after_gap"], gap = gap, False         # a wrap to the top is not a focus jump
        transcript.append(info)
        await on_stop(info)
        sig = signature(info)
        if matches(target_text, info):
            return {"status": "found", "element": info, "presses": presses}
        if seen and sig == seen[0] and presses > 3:
            break                                   # full cycle without finding the target
        seen.append(sig)
        if len(seen) >= 12 and len(set(seen[-12:])) <= 3:
            return {"status": "trap", "loop": list(set(seen[-12:])), "presses": presses}
    else:
        presses = limit
    if not await target_exists(page, target_text):
        return {"status": "baseline_mismatch", "presses": presses}   # the baseline was wrong, not the site
    return {"status": "unreachable", "presses": presses}


async def page_state(page):
    js = """() => {
        const el = document.activeElement;
        return {
            url: location.href,
            text_len: document.body.innerText.length,
            expanded: el ? el.getAttribute('aria-expanded') : null,
            value: el && 'value' in el ? String(el.value) : null,
            checked: el && 'checked' in el ? el.checked : null
        };
    }"""
    try:
        return await page.evaluate(js)
    except Exception:                               # mid-navigation: wait and read the new page
        await page.wait_for_load_state("domcontentloaded")
        return await page.evaluate(js)


SELECTED_TEXT_JS = """() => {
  const el = document.activeElement;
  return el && el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : '';
}"""


async def activate(page, step, element):
    name = (element["text"] or element["announce"]).lower()
    if any(w in name for w in STOP_WORDS):
        return {"status": "stopped_safely"}          # final submit reached: never press it
    kind = await page.evaluate("() => document.activeElement.type || ''")
    if step["action"] == "type" or kind in TEXT_TYPES:
        await page.keyboard.type(step.get("value") or "test")
        return {"status": "typed"}
    before = await page_state(page)
    wanted = (step.get("value") or "").strip()
    if kind in ("checkbox", "radio"):
        await page.keyboard.press("Space")
    elif element["tag"] == "select" and wanted:
        chosen = await page.evaluate(SELECTED_TEXT_JS)
        if chosen.strip().lower() == wanted.lower():
            return {"status": "activated"}            # the right option is already chosen
        await page.keyboard.type(wanted)               # type-ahead picks the matching option
    elif step["action"] == "select" or element["tag"] == "select":
        await page.keyboard.press("ArrowDown")
    else:
        await page.keyboard.press("Enter")
    await page.wait_for_timeout(800)
    after = await page_state(page)
    if after["url"] != before["url"]:
        await page.wait_for_load_state("domcontentloaded")
    return {"status": "activated" if after != before else "no_response"}


OUTLINE_ON = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return;
  window.__aaOutline = [el, el.style.outline];
  el.style.outline = '3px solid magenta';
}"""
OUTLINE_OFF = """() => {
  if (!window.__aaOutline) return;
  const [el, prev] = window.__aaOutline;
  el.style.outline = prev;
  delete window.__aaOutline;
}"""


class Screenshots:
    """Saves DATA_DIR/screens/{audit_id}/{seq:03d}.png and returns its /files URL."""

    def __init__(self, audit_id: str, data_dir: str):
        self.audit_id = audit_id
        self.dir = Path(data_dir) / "screens" / audit_id
        self.seq = 0

    async def take(self, page, outline: bool = False):
        self.seq += 1
        name = f"{self.seq:03d}.png"
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            if outline:
                await page.evaluate(OUTLINE_ON)
            await page.screenshot(path=str(self.dir / name))
        except Exception:
            return None
        finally:
            if outline:
                try:
                    await page.evaluate(OUTLINE_OFF)
                except Exception:
                    pass
        return f"/files/screens/{self.audit_id}/{name}"
