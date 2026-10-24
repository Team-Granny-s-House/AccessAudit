# backend/issues.py
"""Turns walker results and axe violations into issue objects."""
import re

NO_NAME_RE = re.compile(r"^- (button|link|textbox|combobox|checkbox|radio|tab|menuitem)\s*$")
ROLE_RE = re.compile(r"^- (\w+)")
NAME_RE = re.compile(r'^- \w+ "(.*)"')
WCAG_TAG_RE = re.compile(r"wcag(\d)(\d)(\d+)")
JUMP_PX = 400
SEVERITY_ORDER = ["Blocker", "Critical", "Serious", "Moderate"]
IMPACT_SEVERITY = {"critical": "Critical", "serious": "Serious", "moderate": "Moderate", "minor": "Moderate"}

KB_USERS = "Keyboard-only and screen-reader users"
UNDERSTANDING = "https://www.w3.org/WAI/WCAG21/Understanding/"

WALKER_CHECKS = {
    "kb_unreachable": {
        "wcag": "2.1.1", "severity": "Blocker",
        "title": "'{name}' can't be reached with the keyboard",
        "fix": 'Use a native `<button>` or `<a href>`, or add `tabindex="0"`, `role="button"` and an Enter/Space key handler',
        "help_url": UNDERSTANDING + "keyboard.html"},
    "kb_trap": {
        "wcag": "2.1.2", "severity": "Blocker",
        "title": "Keyboard focus gets stuck in a loop on this page",
        "fix": "Let Tab and Shift+Tab leave the widget. Inside a group of controls use one tab stop and arrow "
               "keys (roving tabindex); in dialogs support Escape and return focus to the trigger",
        "help_url": UNDERSTANDING + "no-keyboard-trap.html"},
    "kb_no_response": {
        "wcag": "2.1.1", "severity": "Blocker",
        "title": "'{name}' does nothing when activated with the keyboard",
        "fix": "Use a native control, or handle Enter and Space in a `keydown` listener",
        "help_url": UNDERSTANDING + "keyboard.html"},
    "no_name": {
        "wcag": "4.1.2", "severity": "Critical",
        "title": "A {role} has no name, so screen readers only say '{role}'",
        "fix": "Add an `aria-label` or visually hidden text",
        "help_url": UNDERSTANDING + "name-role-value.html"},
    "focus_invisible": {
        "wcag": "2.4.7", "severity": "Serious",
        "title": "Keyboard focus is invisible on '{name}'",
        "fix": "Add a `:focus-visible` style with a clear outline",
        "help_url": UNDERSTANDING + "focus-visible.html"},
    "focus_jump": {
        "wcag": "2.4.3", "severity": "Moderate",
        "title": "Focus jumps back up the page after '{name}'",
        "fix": "Make the source order match the visual order and avoid positive `tabindex` values",
        "help_url": UNDERSTANDING + "focus-order.html"},
}
AXE_FIXES = {"label": "Add a `<label for>` or `aria-label`"}


def who(check: str) -> str:
    if not check.startswith("axe:"):
        return KB_USERS                             # every keyboard and name check
    rule = check[4:]
    if rule == "color-contrast":
        return "Low-vision users"
    if rule in ("image-alt", "svg-img-alt", "role-img-alt", "html-has-lang"):
        return "Blind users"
    if rule == "label" or rule.endswith("-name"):
        return KB_USERS
    return "Screen-reader users"


def role_of(announce: str) -> str:
    m = ROLE_RE.match(announce or "")
    return m.group(1) if m else ""


def name_of(stop: dict) -> str:
    """The element's text or, if empty, its announced name."""
    if stop.get("text"):
        return stop["text"]
    m = NAME_RE.match(stop.get("announce") or "")
    return m.group(1) if m else ""


def wcag_from_tags(tags: list[str]) -> str:
    found = [f"{a}.{b}.{c}" for a, b, c in (m.groups() for m in map(WCAG_TAG_RE.fullmatch, tags) if m)]
    return ", ".join(dict.fromkeys(found))


def stop_findings(stop: dict, prev: dict | None = None) -> list[dict]:
    """Checks one focus stop: no_name, focus_invisible, focus_jump. Each finding has a dedupe key."""
    element = (stop["page_url"], stop["tag"], stop["text"], stop["page_x"], stop["page_y"])
    found = []
    if NO_NAME_RE.match(stop.get("announce") or ""):
        found.append({"check": "no_name", "key": ("no_name",) + element, "name": name_of(stop)})
    if not stop["focus_ring"]:
        found.append({"check": "focus_invisible", "key": ("focus_invisible",) + element, "name": name_of(stop)})
    if (prev and prev["page_url"] == stop["page_url"] and not stop.get("after_gap")
            and prev["page_y"] - stop["page_y"] > JUMP_PX):
        found.append({"check": "focus_jump", "key": ("focus_jump",) + element, "name": name_of(prev)})
    return found


def walker_issue(check: str, *, step_index, page_url, name="", announce="", element_html="",
                 screenshot=None, count=1) -> dict:
    spec = WALKER_CHECKS[check]
    role = role_of(announce) or "control"
    return {
        "check": check, "step_index": step_index, "page_url": page_url,
        "wcag": spec["wcag"], "severity": spec["severity"],
        "title": spec["title"].format(name=name or role, role=role),
        "who": who(check), "announce": announce, "element_html": (element_html or "")[:300],
        "screenshot": screenshot, "fix": spec["fix"], "help_url": spec["help_url"], "count": count,
    }


def axe_issue(v: dict, *, step_index, page_url, screenshot=None) -> dict:
    """One issue per axe rule per page; count is the number of failing elements."""
    rule = v["rule"]
    return {
        "check": f"axe:{rule}", "step_index": step_index, "page_url": page_url,
        "wcag": wcag_from_tags(v.get("tags", [])), "severity": IMPACT_SEVERITY.get(v.get("impact"), "Moderate"),
        "title": v["help"], "who": who(f"axe:{rule}"), "announce": "",
        "element_html": (v["nodes"][0]["html"] if v.get("nodes") else "")[:300],
        "screenshot": screenshot, "fix": AXE_FIXES.get(rule, v["help"]), "help_url": v["help_url"],
        "count": v.get("count", len(v.get("nodes", []))),
    }


def drop_named_duplicates(axe_issues: list[dict], issues: list[dict]) -> list[dict]:
    """Skips axe:button-name and axe:link-name on a page that already has a no_name issue."""
    named_pages = {i["page_url"] for i in issues if i["check"] == "no_name"}
    return [i for i in axe_issues
            if not (i["check"] in ("axe:button-name", "axe:link-name") and i["page_url"] in named_pages)]


def sort_issues(issues: list[dict]) -> list[dict]:
    return sorted(issues, key=lambda i: (SEVERITY_ORDER.index(i["severity"]),
                                         i["step_index"] if i["step_index"] is not None else 10**6))


class IssueLog:
    """Holds the audit's issues, gives each an id, and remembers dedupe keys."""

    def __init__(self):
        self.items: list[dict] = []
        self.keys: set = set()

    def seen(self, key) -> bool:
        return key in self.keys

    def add(self, issue: dict, key=None) -> dict:
        if key is not None:
            self.keys.add(key)
        issue = {"id": f"i{len(self.items) + 1}", **issue}
        self.items.append(issue)
        return issue
