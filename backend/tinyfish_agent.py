# backend/tinyfish_agent.py
import os, json, httpx

AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"
HEADERS = {"X-API-Key": os.environ.get("TINYFISH_API_KEY", "")}

# Only TinyFish's structured-output keywords are allowed (type, properties, items, required, enum, ...);
# "description" is rejected with a 400, so the field instructions live in the goal instead.
STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "task_completed": {"type": "boolean"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["click", "type", "select"]},
                    "element_text": {"type": "string"},  # exact visible label: the walker matches on it
                    "element_role": {"type": "string"},  # link, button, textbox, combobox...
                    "value": {"type": "string"},         # text typed or option chosen
                    "description": {"type": "string"},   # plain-English note for people; never matched
                    "page_url": {"type": "string"}
                },
                "required": ["action", "element_text"]
            }
        }
    },
    "required": ["task_completed", "steps"]
}

def baseline_goal(task: str) -> str:
    return (
        f"Complete this task as a normal user: {task.strip().rstrip('.')}. "
        "Do not submit payments, log in, or send any form that creates a real record; "
        "stop on the final review page instead. "
        "Record every click, every field you type into and every dropdown you change, in order, as steps. "
        "For each step: action is click (links, buttons, checkboxes, radio buttons), type (text fields) "
        "or select (dropdowns); element_text is the element's exact visible text or label, copied "
        "character for character with nothing added (for a text field or dropdown, its label; empty if "
        "it has no visible text); element_role is link, button, textbox, combobox, checkbox or radio; "
        "value is the text typed or the option chosen; description is a short plain-English note on "
        "what the step does, for a person reading the report."
    )

def normalize_result(result):
    """Returns the baseline dict, or None if the baseline failed (Correction 3)."""
    if isinstance(result, dict) and "steps" not in result and "result" in result:
        result = result["result"]                   # a non-object answer arrives under result.result
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return None
    if not isinstance(result, dict) or not result.get("task_completed") or not result.get("steps"):
        return None
    return result

async def run_baseline(url: str, task: str, on_event):
    payload = {"url": url, "goal": baseline_goal(task),
               "output_schema": STEP_SCHEMA, "browser_profile": "lite",
               "agent_config": {"max_duration_seconds": 240}}
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", AGENT_URL, headers=HEADERS, json=payload) as r:
            if r.status_code >= 400:                # e.g. a schema TinyFish rejects: show why
                body = (await r.aread()).decode(errors="replace")[:500]
                raise RuntimeError(f"Agent API {r.status_code}: {body}")
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                await on_event(event)              # forwarded to the frontend as events
                if event.get("type") == "COMPLETE":
                    if event.get("status") != "COMPLETED":
                        return None
                    return normalize_result(event.get("result"))   # check result, not just status
    return None
