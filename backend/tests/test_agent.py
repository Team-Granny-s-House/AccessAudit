from backend.tinyfish_agent import STEP_SCHEMA, baseline_goal, normalize_result

# TinyFish's structured-output allowlist (docs.tinyfish.ai/key-concepts/structured-output); anything else is a 400
ALLOWED_KEYWORDS = {"anyOf", "enum", "format", "items", "maxItems", "maximum", "minItems", "minimum",
                    "nullable", "properties", "propertyOrdering", "required", "type"}


def keywords(schema):
    """Every JSON Schema keyword used, without the property names under `properties`."""
    found = set(schema)
    for key, value in schema.items():
        if key == "properties":
            for sub in value.values():
                found |= keywords(sub)
        elif key == "items":
            found |= keywords(value)
        elif key == "anyOf":
            for sub in value:
                found |= keywords(sub)
    return found

STEPS = [{"action": "click", "element_text": "Find trains"}]


def test_plain_result_is_kept():
    assert normalize_result({"task_completed": True, "steps": STEPS})["steps"] == STEPS


def test_result_nested_under_result_is_unwrapped():
    assert normalize_result({"result": {"task_completed": True, "steps": STEPS}})["steps"] == STEPS


def test_result_given_as_json_text_is_parsed():
    text = '{"task_completed": true, "steps": [{"action": "click", "element_text": "Find trains"}]}'
    assert normalize_result({"result": text})["steps"] == STEPS


def test_failed_baselines_are_none():
    assert normalize_result(None) is None
    assert normalize_result({"result": "The main heading is Example Domain"}) is None
    assert normalize_result({"task_completed": False, "steps": STEPS}) is None
    assert normalize_result({"task_completed": True, "steps": []}) is None


def test_schema_uses_only_keywords_tinyfish_accepts():
    assert keywords(STEP_SCHEMA) <= ALLOWED_KEYWORDS


def test_schema_limits_actions_and_has_a_description_field():
    step = STEP_SCHEMA["properties"]["steps"]["items"]["properties"]
    assert step["action"] == {"type": "string", "enum": ["click", "type", "select"]}
    assert step["description"] == {"type": "string"}


def test_goal_carries_the_field_instructions():
    goal = baseline_goal("Find trains and enter the name Asha Verma.")
    assert "Asha Verma. Do not submit" in goal                    # no doubled full stop
    assert "exact visible text or label" in goal and "description is a short plain-English note" in goal


def test_error_codes_are_read_from_the_complete_event():
    from backend.tinyfish_agent import describe_error
    assert describe_error({"code": "SITE_BLOCKED", "message": "Access denied"}) == ("SITE_BLOCKED", "Access denied")
    assert describe_error({"code": "TASK_FAILED", "help_message": "Try again"}) == ("TASK_FAILED", "Try again")
    assert describe_error("SITE_BLOCKED: captcha")[0] == "SITE_BLOCKED"
    assert describe_error(None) == ("TASK_FAILED", "the agent couldn't complete the task")
