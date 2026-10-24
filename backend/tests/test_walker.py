from backend.issues import stop_findings
from backend.walker import activate, reach


async def walk_to(page, target):
    stops = []

    async def on_stop(stop):
        on_stop.calls += 1

    on_stop.calls = 0
    hit = await reach(page, target, stops, on_stop)
    assert on_stop.calls == len(stops)              # on_stop runs for every recorded stop
    return hit, stops


async def test_keyboard_trap(open_fixture):
    page = await open_fixture("trap.html")
    hit, stops = await walk_to(page, "Search")
    assert hit["status"] == "trap"
    assert {s["text"] for s in stops[-3:]} == {"Mon", "Tue", "Wed"}


async def test_div_button_is_unreachable(open_fixture):
    page = await open_fixture("unreachable.html")
    hit, stops = await walk_to(page, "Search")
    assert hit["status"] == "unreachable"
    assert "Search" not in [s["text"] for s in stops]


async def test_missing_target_is_baseline_mismatch(open_fixture):
    page = await open_fixture("form.html")
    hit, _ = await walk_to(page, "Checkout now")
    assert hit["status"] == "baseline_mismatch"


async def test_unnamed_icon_button_is_announced_as_just_button(open_fixture):
    page = await open_fixture("unnamed.html")
    hit, stops = await walk_to(page, "More options")
    assert hit["status"] == "found"
    assert stops[0]["announce"] == "- button"
    assert [f["check"] for f in stop_findings(stops[0])] == ["no_name"]
    assert (await activate(page, {"action": "click"}, hit["element"]))["status"] == "activated"


async def test_button_that_ignores_enter_is_no_response(open_fixture):
    page = await open_fixture("unnamed.html")
    hit, _ = await walk_to(page, "Refresh")
    assert hit["status"] == "found"
    assert (await activate(page, {"action": "click"}, hit["element"]))["status"] == "no_response"


async def test_zero_size_skip_link_is_ignored(open_fixture):
    page = await open_fixture("form.html")
    hit, stops = await walk_to(page, "Email")
    assert hit["status"] == "found"
    assert all(s["text"] != "Skip to content" for s in stops)


async def test_types_into_labelled_field(open_fixture):
    page = await open_fixture("form.html")
    hit, _ = await walk_to(page, "Email")
    step = {"action": "type", "element_text": "Email", "value": "asha@example.com"}
    assert (await activate(page, step, hit["element"]))["status"] == "typed"
    assert await page.input_value("#email") == "asha@example.com"


async def test_checkbox_matches_by_announced_name_and_toggles_with_space(open_fixture):
    page = await open_fixture("form.html")
    hit, _ = await walk_to(page, "Send me news")
    assert hit["status"] == "found"
    assert (await activate(page, {"action": "click"}, hit["element"]))["status"] == "activated"
    assert await page.is_checked("#news")


async def test_dropdown_already_on_the_wanted_option_passes(open_fixture):
    page = await open_fixture("form.html")
    hit, _ = await walk_to(page, "City")
    step = {"action": "select", "element_text": "City", "value": "Delhi"}
    assert (await activate(page, step, hit["element"]))["status"] == "activated"
    assert await page.input_value("#city") == "Delhi"


async def test_dropdown_option_is_chosen_by_typing(open_fixture):
    page = await open_fixture("form.html")
    hit, _ = await walk_to(page, "City")
    step = {"action": "select", "element_text": "City", "value": "Pune"}
    assert (await activate(page, step, hit["element"]))["status"] == "activated"
    assert await page.input_value("#city") == "Pune"


async def test_link_that_changes_the_page_is_activated(open_fixture):
    page = await open_fixture("form.html")
    hit, _ = await walk_to(page, "Show details")
    assert (await activate(page, {"action": "click"}, hit["element"]))["status"] == "activated"
    assert await page.is_visible("#details")


async def test_never_presses_a_submit_control(open_fixture):
    page = await open_fixture("form.html")
    hit, _ = await walk_to(page, "Submit order")
    assert (await activate(page, {"action": "click"}, hit["element"]))["status"] == "stopped_safely"
