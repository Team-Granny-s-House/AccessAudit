# backend/scoring.py
WEIGHTS = {"Blocker": 25, "Critical": 10, "Serious": 5, "Moderate": 2}
PASSED = ("activated", "typed", "stopped_safely")
BLOCKED = ("unreachable", "trap", "no_response")


def score_audit(steps: list[dict], results: list[dict], issues: list[dict], baseline_ok: bool = True) -> dict:
    """Verdict and score. A blocked task can never score above 40."""
    total = len(steps)
    if not baseline_ok or any(r["status"] == "baseline_mismatch" for r in results):
        return {"verdict": "Inconclusive", "score": None, "blocked_at": None, "total_steps": total}
    penalty = sum(WEIGHTS[i["severity"]] * min(i["count"], 3) for i in issues)
    blocked_at = next((n for n, r in enumerate(results, 1) if r["status"] in BLOCKED), None)
    if blocked_at is None:
        cap = 100
        severe = any(i["severity"] in ("Blocker", "Critical") for i in issues)
        verdict = "Completed with barriers" if severe else "Completed"
    else:
        cap = 40
        verdict = f"Blocked at step {blocked_at} of {total}"
    score = round(max(0, min(cap, 100 - penalty)))
    return {"verdict": verdict, "score": score, "blocked_at": blocked_at, "total_steps": total}
