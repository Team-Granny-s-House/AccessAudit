# backend/store.py
"""SQLite storage: one Audit row per audit (with the full report JSON) plus its steps, issues and stops."""
import json
import os
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select


class Audit(SQLModel, table=True):
    id: str = Field(primary_key=True)
    url: str
    task: str
    persona: str
    status: str                                 # running | done | error
    created_at: str
    baseline_json: str | None = None
    verdict: str | None = None
    score: int | None = None
    report_json: str | None = None


class Step(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    audit_id: str = Field(index=True)
    index: int
    action: str | None = None
    element_text: str
    description: str | None = None
    walker_status: str
    presses: int
    screenshot: str | None = None


class Issue(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    audit_id: str = Field(index=True)
    issue_id: str                               # the report's id, e.g. "i3"
    step_index: int | None = None
    check: str
    page_url: str
    wcag: str
    severity: str
    title: str
    who: str
    element_html: str
    screenshot: str | None = None
    announce: str
    fix: str
    help_url: str
    count: int


class Stop(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    audit_id: str = Field(index=True)
    seq: int
    tag: str
    text: str
    announce: str
    focus_ring: bool
    page_url: str


_engines = {}


def engine():
    """One engine per DATA_DIR, so tests can point at a temporary folder."""
    path = Path(os.getenv("DATA_DIR", "./data")).resolve() / "accessaudit.db"
    if path not in _engines:
        path.parent.mkdir(parents=True, exist_ok=True)
        _engines[path] = create_engine(f"sqlite:///{path}")
        SQLModel.metadata.create_all(_engines[path])
    return _engines[path]


def init_db() -> None:
    """Creates the tables and marks audits left running by a previous server run as errors."""
    with Session(engine()) as s:
        for audit in s.exec(select(Audit).where(Audit.status == "running")):
            audit.status = "error"
            s.add(audit)
        s.commit()


def create_audit(record: dict) -> None:
    with Session(engine()) as s:
        s.add(Audit(**{k: record[k] for k in ("id", "url", "task", "persona", "created_at")}, status="running"))
        s.commit()


def save_report(report: dict, baseline: dict | None) -> None:
    with Session(engine()) as s:
        audit = s.get(Audit, report["id"])
        audit.status = report["status"]
        audit.verdict = report["verdict"]
        audit.score = report["score"]
        audit.baseline_json = json.dumps(baseline) if baseline else None
        audit.report_json = json.dumps(report, ensure_ascii=False)
        s.add(audit)
        for st in report["steps"]:
            s.add(Step(audit_id=report["id"], index=st["index"], action=st["action"],
                       element_text=st["element_text"], description=st.get("description"),
                       walker_status=st["status"], presses=st["presses"], screenshot=st["screenshot"]))
        for i in report["issues"]:
            s.add(Issue(audit_id=report["id"], issue_id=i["id"],
                        **{k: i[k] for k in ("step_index", "check", "page_url", "wcag", "severity", "title", "who",
                                             "element_html", "screenshot", "announce", "fix", "help_url", "count")}))
        for t in report["transcript"]:
            s.add(Stop(audit_id=report["id"], **t))
        s.commit()


def get_report(audit_id: str) -> dict | None:
    """The saved report JSON, or a skeleton with status 'running' while the audit is still going."""
    with Session(engine()) as s:
        audit = s.get(Audit, audit_id)
        if audit is None:
            return None
        if audit.report_json:
            return json.loads(audit.report_json)
        return {"id": audit.id, "url": audit.url, "task": audit.task, "persona": audit.persona,
                "created_at": audit.created_at, "status": audit.status, "verdict": None, "score": None,
                "blocked_at": None, "total_steps": 0, "baseline_source": None, "cached": False, "steps": [], "issues": [],
                "transcript": [], "page_scans": [], "notes": []}


def list_audits(limit: int = 20) -> list[dict]:
    with Session(engine()) as s:
        rows = s.exec(select(Audit).order_by(Audit.created_at.desc()).limit(limit))
        return [{"id": a.id, "url": a.url, "task": a.task, "persona": a.persona, "created_at": a.created_at,
                 "status": a.status, "verdict": a.verdict, "score": a.score} for a in rows]
