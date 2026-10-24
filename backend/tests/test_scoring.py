from backend.scoring import score_audit

STEPS = [{"element_text": "A"}, {"element_text": "B"}, {"element_text": "C"}]


def issue(severity, count=1):
    return {"severity": severity, "count": count}


def results(*statuses):
    return [{"status": s} for s in statuses]


def test_failed_baseline_is_inconclusive():
    out = score_audit([], [], [], baseline_ok=False)
    assert out == {"verdict": "Inconclusive", "score": None, "blocked_at": None, "total_steps": 0}


def test_baseline_mismatch_is_inconclusive():
    out = score_audit(STEPS, results("activated", "baseline_mismatch"), [issue("Blocker")])
    assert out["verdict"] == "Inconclusive" and out["score"] is None


def test_clean_completion_scores_100():
    out = score_audit(STEPS, results("activated", "activated", "typed"), [])
    assert out == {"verdict": "Completed", "score": 100, "blocked_at": None, "total_steps": 3}


def test_serious_issues_still_completed():
    out = score_audit(STEPS, results("activated", "activated", "typed"), [issue("Serious"), issue("Moderate")])
    assert out["verdict"] == "Completed" and out["score"] == 93


def test_critical_issue_means_completed_with_barriers():
    out = score_audit(STEPS, results("activated", "activated", "typed"), [issue("Critical")])
    assert out["verdict"] == "Completed with barriers" and out["score"] == 90


def test_stopped_safely_counts_as_passed():
    out = score_audit(STEPS, results("activated", "stopped_safely"), [])
    assert out["verdict"] == "Completed" and out["score"] == 100


def test_blocked_task_is_capped_at_40():
    out = score_audit(STEPS, results("activated", "trap"), [])
    assert out == {"verdict": "Blocked at step 2 of 3", "score": 40, "blocked_at": 2, "total_steps": 3}


def test_blocked_score_drops_below_cap_with_penalties():
    out = score_audit(STEPS, results("unreachable"), [issue("Blocker"), issue("Critical"), issue("Serious", 3)])
    assert out["verdict"] == "Blocked at step 1 of 3" and out["score"] == 40   # 100 - 50 = 50, capped at 40
    out = score_audit(STEPS, results("no_response"), [issue("Blocker", 3)])
    assert out["score"] == 25


def test_each_issue_counts_at_most_three_times():
    out = score_audit(STEPS, results("activated", "activated", "typed"), [issue("Serious", 10)])
    assert out["score"] == 85


def test_score_never_negative():
    out = score_audit(STEPS, results("trap"), [issue("Blocker", 3), issue("Blocker", 3)])
    assert out["score"] == 0
