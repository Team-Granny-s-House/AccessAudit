# backend/app.py
"""FastAPI routes + WebSocket. Run: uvicorn backend.app:app --port 8000 (no --reload on Windows)."""
import asyncio, json, logging, os, time, uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from playwright.async_api import TimeoutError as PlaywrightTimeout, async_playwright
from pydantic import BaseModel

from backend import store
from backend.audit import run_audit
from backend.tinyfish_browser import end_open_sessions

log = logging.getLogger("accessaudit")


def data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "./data")).resolve()


def replay_path(audit_id: str) -> Path:
    return data_dir() / "replays" / f"{audit_id}.jsonl"


class AuditRun:
    """One audit's events: an in-memory log, a replay file, and a queue per connected WebSocket."""

    def __init__(self, audit_id: str):
        self.start = time.monotonic()
        self.log: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.baseline: dict | None = None
        self.pending_done: dict | None = None
        self.path = replay_path(audit_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def publish(self, event: dict) -> None:
        self.log.append(event)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        for q in self.subscribers:
            q.put_nowait(event)

    async def emit(self, type_: str, data: dict) -> None:
        event = {"type": type_, "t": round(time.monotonic() - self.start, 3), "data": data}
        if type_ == "baseline_done":
            self.baseline = {"task_completed": True, "steps": data["steps"]}
        if type_ == "done":
            self.pending_done = event               # sent after the report is saved
            return
        self.publish(event)


RUNS: dict[str, AuditRun] = {}
audit_lock = asyncio.Lock()                         # one audit at a time in the MVP
background: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    data_dir().mkdir(parents=True, exist_ok=True)
    store.init_db()
    yield
    for task in list(background):                   # an audit still running when the server stops
        task.cancel()
    await asyncio.gather(*background, return_exceptions=True)
    await end_open_sessions()                       # never leave a TinyFish session running


app = FastAPI(title="AccessAudit", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
                   allow_methods=["*"], allow_headers=["*"])


class AuditIn(BaseModel):
    url: str
    task: str
    persona: Literal["screen_reader", "keyboard"] = "screen_reader"


async def run_in_background(record: dict, run: AuditRun) -> None:
    try:
        report = await run_audit(record, run.emit)
        store.save_report(report, run.baseline)
    except Exception:                               # run_audit handles its own errors; this is a last resort
        log.exception("audit %s could not be saved", record["id"])
    finally:
        if run.pending_done:
            run.publish(run.pending_done)
        audit_lock.release()


@app.post("/audits")
async def create_audit(body: AuditIn):
    schemes = ("http://", "https://") + (("file://",) if os.getenv("WALKER_MODE") == "local" else ())
    if not body.url.startswith(schemes) or not body.task.strip():
        raise HTTPException(422, "Give a public http(s) URL and a task")
    if audit_lock.locked():
        raise HTTPException(409, "Another audit is running; try again when it finishes")
    await audit_lock.acquire()
    record = {"id": uuid.uuid4().hex[:8], "url": body.url, "task": body.task.strip(), "persona": body.persona,
              "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    try:
        store.create_audit(record)
        run = RUNS[record["id"]] = AuditRun(record["id"])
    except Exception:
        audit_lock.release()
        raise
    task = asyncio.create_task(run_in_background(record, run))
    background.add(task)
    task.add_done_callback(background.discard)
    return {"id": record["id"]}


@app.get("/audits")
async def list_audits(limit: int = 20):
    return store.list_audits(limit)


@app.get("/audits/{audit_id}")
async def get_audit(audit_id: str):
    report = store.get_report(audit_id)
    if report is None:
        raise HTTPException(404, "No such audit")
    return report


def read_replay(audit_id: str) -> list[dict] | None:
    path = replay_path(audit_id)
    if not path.exists():
        return None
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.get("/audits/{audit_id}/replay")
async def get_replay(audit_id: str):
    events = read_replay(audit_id)
    if events is None:
        raise HTTPException(404, "No events saved for this audit")
    return events


@app.websocket("/audits/{audit_id}/events")
async def audit_events(ws: WebSocket, audit_id: str):
    await ws.accept()
    run = RUNS.get(audit_id)
    if run is None:                                 # finished before this server started: send the saved events
        for event in read_replay(audit_id) or []:
            await ws.send_json(event)
        await ws.close()
        return
    queue: asyncio.Queue = asyncio.Queue()
    backlog = list(run.log)                         # the log so far, then live events (no await in between)
    run.subscribers.add(queue)
    try:
        for event in backlog:
            await ws.send_json(event)
            if event["type"] == "done":
                return
        while True:
            event = await queue.get()
            await ws.send_json(event)
            if event["type"] == "done":
                return
    except WebSocketDisconnect:
        pass
    finally:
        run.subscribers.discard(queue)
        try:
            await ws.close()
        except RuntimeError:
            pass                                    # already closed by the client


@app.get("/audits/{audit_id}/pdf")
async def audit_pdf(audit_id: str):
    """Renders the frontend's print view in a local Chromium (never TinyFish) and caches the PDF."""
    report = store.get_report(audit_id)
    if report is None:
        raise HTTPException(404, "No such audit")
    if report["status"] == "running":
        raise HTTPException(409, "The audit is still running")
    path = data_dir() / "pdf" / f"{audit_id}.pdf"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        frontend = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page()
                await page.goto(f"{frontend}/audit/{audit_id}?print=1")
                await page.wait_for_selector("[data-report-ready]", state="attached", timeout=30_000)
                await page.wait_for_load_state("networkidle")       # screenshots loaded
                await page.pdf(path=str(tmp), format="A4", print_background=True,
                               margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"})
            except PlaywrightTimeout:
                raise HTTPException(503, f"Couldn't render the report; is the frontend running at {frontend}?")
            finally:
                await browser.close()
        tmp.replace(path)
    return FileResponse(path, media_type="application/pdf", filename=f"accessaudit-{audit_id}.pdf")


@app.get("/files/{path:path}")
async def files(path: str):
    """Serves DATA_DIR (screenshots) without letting a path escape it."""
    root = data_dir()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(target)
