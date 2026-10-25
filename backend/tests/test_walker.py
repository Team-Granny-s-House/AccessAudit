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


async def test_same_text_links_in_a_ticker_are_not_a_trap(open_fixture):
    page = await open_fixture("ticker.html")
    hit, stops = await walk_to(page, "Apply now")
    assert hit["status"] == "found"
    assert sum(s["text"] == "Click here" for s in stops) == 13


async def test_a_short_label_does_not_match_a_longer_link(open_fixture):
    page = await open_fixture("ticker.html")
    hit, _ = await walk_to(page, "Fees")
    assert hit["status"] == "found" and hit["element"]["text"] == "Fees"      # not "Fee Portal"


def test_label_similarity():
    from backend.walker import similar
    assert similar("Find trains", "Find trains") and similar("find  Trains", "Find trains")
    assert similar("Find trains button", "Find trains")          # long label with an extra word
    assert similar("Passenger name", "Passenger Name")
    assert not similar("Fees", "Fee Portal")
    assert not similar("Admission", "International Admission")
    assert not similar("Select", "") and not similar("", "Select")


def test_one_word_of_a_long_label_does_not_match():
    from backend.walker import similar
    assert not similar("B.Tech. Lateral Entry Admissions 2026", "Admissions")
    assert similar("SkyRail Swift", "SkyRail Swift Train 2101 · Chair car 06:10")   # card link with extra text


async def test_big_pages_get_more_tab_presses(open_fixture):
    from backend.walker import MAX_TABS, MAX_TABS_CEILING, tab_limit
    page = await open_fixture("form.html")
    assert await tab_limit(page) == MAX_TABS                                   # small page: the spec's 120
    await page.set_content("".join(f'<a href="#{i}">Link {i}</a> ' for i in range(300)))
    assert await tab_limit(page) == 310
    await page.set_content("".join(f'<a href="#{i}">Link {i}</a> ' for i in range(1000)))
    assert await tab_limit(page) == MAX_TABS_CEILING
