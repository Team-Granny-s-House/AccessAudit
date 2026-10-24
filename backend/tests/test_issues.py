from backend.issues import (IssueLog, axe_issue, drop_named_duplicates, sort_issues, stop_findings,
                            walker_issue, wcag_from_tags, who)

PAGE = "https://example.com/results.html"


def stop(**kw):
    base = {"page_url": PAGE, "tag": "button", "text": "Go", "announce": '- button "Go"',
            "focus_ring": True, "page_x": 10, "page_y": 500, "html": "<button>Go</button>"}
    return {**base, **kw}


def violation(rule, impact="serious", tags=("wcag2a", "wcag143"), nodes=2):
    return {"rule": rule, "impact": impact, "help": f"{rule} help", "help_url": f"https://axe/{rule}",
            "tags": list(tags), "count": nodes,
            "nodes": [{"target": ["#x"], "html": "<p>" + "x" * 400 + "</p>"}][:nodes]}


def checks(findings):
    return [f["check"] for f in findings]


def test_who_groups():
    assert who("kb_trap") == who("focus_jump") == who("no_name") == "Keyboard-only and screen-reader users"
    for rule in ("label", "button-name", "link-name", "input-button-name", "select-name", "aria-dialog-name"):
        assert who(f"axe:{rule}") == "Keyboard-only and screen-reader users"
    assert who("axe:color-contrast") == "Low-vision users"
    for rule in ("image-alt", "svg-img-alt", "role-img-alt", "html-has-lang"):
        assert who(f"axe:{rule}") == "Blind users"
    assert who("axe:list") == "Screen-reader users"


def test_wcag_from_axe_tags():
    assert wcag_from_tags(["cat.color", "wcag2aa", "wcag143"]) == "1.4.3"
    assert wcag_from_tags(["wcag2a", "wcag131", "wcag412"]) == "1.3.1, 4.1.2"
    assert wcag_from_tags(["wcag21aa", "wcag1410"]) == "1.4.10"


def test_no_name_only_when_announcement_is_just_a_role():
    assert checks(stop_findings(stop(text="", announce="- button"))) == ["no_name"]
    assert checks(stop_findings(stop(text="", announce="- link"))) == ["no_name"]
    assert checks(stop_findings(stop())) == []


def test_focus_invisible():
    assert checks(stop_findings(stop(focus_ring=False))) == ["focus_invisible"]


def test_focus_jump_same_page_only():
    prev = stop(page_y=1000, text="Next")
    assert checks(stop_findings(stop(page_y=500), prev)) == ["focus_jump"]
    assert checks(stop_findings(stop(page_y=700), prev)) == []                       # 300 px: not a jump
    assert checks(stop_findings(stop(page_y=500, page_url="https://example.com/other"), prev)) == []
    assert checks(stop_findings(stop(page_y=500, after_gap=True), prev)) == []       # wrapped to the top


def test_walker_issue_titles_and_fields():
    i = walker_issue("no_name", step_index=1, page_url=PAGE, name="", announce="- button",
                     element_html="<button>" + "y" * 400, screenshot="/files/screens/a/001.png")
    assert i["title"] == "A button has no name, so screen readers only say 'button'"
    assert (i["wcag"], i["severity"], i["count"]) == ("4.1.2", "Critical", 1)
    assert len(i["element_html"]) == 300
    assert walker_issue("kb_unreachable", step_index=0, page_url=PAGE, name="Search")["title"] == \
        "'Search' can't be reached with the keyboard"
    assert walker_issue("kb_trap", step_index=1, page_url=PAGE)["severity"] == "Blocker"


def test_axe_issue_mapping():
    i = axe_issue(violation("color-contrast", "serious", nodes=4), step_index=0, page_url=PAGE)
    assert (i["check"], i["wcag"], i["severity"], i["count"]) == ("axe:color-contrast", "1.4.3", "Serious", 4)
    assert i["title"] == i["fix"] == "color-contrast help"
    assert len(i["element_html"]) == 300
    assert axe_issue(violation("image-alt", "critical"), step_index=0, page_url=PAGE)["severity"] == "Critical"
    assert axe_issue(violation("list", "minor"), step_index=0, page_url=PAGE)["severity"] == "Moderate"
    assert axe_issue(violation("label"), step_index=0, page_url=PAGE)["fix"] == "Add a `<label for>` or `aria-label`"


def test_axe_name_rules_skipped_when_walker_found_no_name():
    no_name = walker_issue("no_name", step_index=1, page_url=PAGE, announce="- button")
    axe = [axe_issue(violation(r), step_index=1, page_url=PAGE) for r in ("button-name", "link-name", "label")]
    other_page = axe_issue(violation("button-name"), step_index=0, page_url="https://example.com/")
    kept = drop_named_duplicates(axe + [other_page], [no_name])
    assert [(i["check"], i["page_url"]) for i in kept] == [("axe:label", PAGE), ("axe:button-name", "https://example.com/")]


def test_sort_by_severity_then_step():
    items = [{"severity": "Moderate", "step_index": 0}, {"severity": "Blocker", "step_index": 2},
             {"severity": "Critical", "step_index": None}, {"severity": "Critical", "step_index": 1}]
    assert [(i["severity"], i["step_index"]) for i in sort_issues(items)] == \
        [("Blocker", 2), ("Critical", 1), ("Critical", None), ("Moderate", 0)]


def test_issue_log_ids_and_dedupe_keys():
    log = IssueLog()
    first = log.add({"check": "focus_invisible"}, key=("focus_invisible", PAGE, "Go"))
    assert first["id"] == "i1" and log.seen(("focus_invisible", PAGE, "Go"))
    assert log.add({"check": "kb_trap"})["id"] == "i2"
