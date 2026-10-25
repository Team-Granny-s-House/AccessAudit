"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  BLOCKED,
  getReplay,
  getReport,
  PASSED,
  spoken,
  STATUS_TEXT,
  stepLabel,
  wsUrl,
  type AuditEvent,
  type BaselineStep,
  type Report as ReportData,
} from "@/lib/api";
import { StepLog, StreamPanel, type LogLine } from "./LivePanel";
import Report from "./Report";
import StepTimeline from "./StepTimeline";

interface Live {
  cached: boolean;
  streamingUrl: string | null;
  steps: BaselineStep[];
  statuses: Record<number, string>;
  log: LogLine[];
  walking: boolean;
  screenshot: string | null;
  announcement: string;
  barriers: number;
}

const initialLive: Live = {
  cached: false, streamingUrl: null, steps: [], statuses: {}, log: [], walking: false,
  screenshot: null, announcement: "", barriers: 0,
};

function line(state: Live, kind: LogLine["kind"], text: string): LogLine[] {
  return [...state.log, { key: `${state.log.length}`, kind, text }];
}

/** Folds each audit event into the live view's state. */
function reduce(state: Live, event: AuditEvent): Live {
  const d = event.data;
  switch (event.type) {
    case "baseline_started":
      return {
        ...state,
        cached: Boolean(d.cached),
        log: line(state, "info", d.cached
          ? "Using a saved baseline from an earlier sighted-agent run."
          : d.source === "override" ? "Using hand-checked steps." : "Sighted agent running…"),
      };
    case "streaming_url":
      return { ...state, streamingUrl: d.url };
    case "baseline_progress":
      return { ...state, log: line(state, "progress", d.text) };
    case "baseline_done":
      return {
        ...state,
        steps: d.steps,
        log: line(state, "info", `Baseline ready: ${d.steps.length} steps. The keyboard walker starts now.`),
      };
    case "page_scan":
      return {
        ...state,
        walking: true,
        log: line(state, "info", d.error
          ? `Page scan failed on ${d.url}: ${d.error}`
          : `Scanned ${d.url}: ${d.violations.length} rule(s) failed.`),
      };
    case "walker_stop":
      return {
        ...state,
        walking: true,
        log: line(state, "stop", `Tab ${d.seq}: "${spoken(d.announce) || d.tag}"${d.focus_ring ? "" : " (no visible focus)"}`),
      };
    case "issue":
      return {
        ...state,
        barriers: state.barriers + 1,
        screenshot: d.screenshot ?? state.screenshot,
        log: line(state, "issue", `Barrier: ${d.title}`),
      };
    case "step_result": {
      const n = d.index + 1;
      const label = stepLabel(state.steps[d.index], n);
      const text = `Step ${n} of ${state.steps.length || "?"}, ${label}: ${STATUS_TEXT[d.status] ?? d.status}.`;
      return {
        ...state,
        statuses: { ...state.statuses, [d.index]: d.status },
        screenshot: d.screenshot ?? state.screenshot,
        announcement: text,
        log: line(state, BLOCKED.includes(d.status) ? "issue" : "info", text),
      };
    }
    case "note":
      return {
        ...state,
        log: line(state, "info", d.found ? "The site links an accessibility statement." : "No accessibility statement link found."),
      };
    case "error":
      return { ...state, log: line(state, "error", `Error: ${d.message}`) };
    case "done":
      return {
        ...state,
        announcement: `Audit finished: ${d.verdict}${d.score === null ? "" : `, score ${d.score} out of 100`}.`,
        log: line(state, "info", `Finished: ${d.verdict}.`),
      };
    default:
      return state;
  }
}

export default function AuditView({ id, replay, print }: { id: string; replay: boolean; print: boolean }) {
  const [live, dispatch] = useReducer(reduce, initialLive);
  const [report, setReport] = useState<ReportData | null>(null);
  const [baselineSteps, setBaselineSteps] = useState<BaselineStep[] | null>(null);
  const [phase, setPhase] = useState<"loading" | "live" | "report">("loading");
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<number[]>([]);
  const cancelled = useRef(false);

  const showReport = useCallback(async () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    try {
      const [r, events] = await Promise.all([getReport(id), getReplay(id).catch(() => [] as AuditEvent[])]);
      if (cancelled.current) return;
      setBaselineSteps(events.find((e) => e.type === "baseline_done")?.data.steps ?? null);
      setReport(r);
      setPhase("report");
    } catch {
      if (!cancelled.current) setError("The report couldn't be loaded. Is the backend running?");
    }
  }, [id]);

  useEffect(() => {
    cancelled.current = false;
    let socket: WebSocket | null = null;
    if (print) document.body.dataset.print = "1";

    async function start() {
      let current: ReportData;
      try {
        current = await getReport(id);
      } catch (e) {
        setError(e instanceof Error && e.message === "not-found"
          ? "There is no audit with this ID."
          : "Couldn't reach the AccessAudit backend. Is it running?");
        return;
      }
      if (cancelled.current) return;

      if (replay) {                                  // saved events with their original timing
        const events = await getReplay(id);
        if (cancelled.current) return;
        setPhase("live");
        for (const e of events) {
          timers.current.push(window.setTimeout(() => {
            dispatch(e);
            if (e.type === "done") showReport();
          }, e.t * 1000));
        }
        return;
      }
      if (print || current.status !== "running") {   // already finished: skip the WebSocket
        await showReport();
        return;
      }

      setPhase("live");
      let finished = false;
      socket = new WebSocket(wsUrl(id));
      socket.onmessage = (m) => {
        const e: AuditEvent = JSON.parse(m.data);
        dispatch(e);
        if (e.type === "done") {
          finished = true;
          showReport();
        }
      };
      socket.onclose = () => {
        if (!finished && !cancelled.current) {
          setError("Lost the live connection. The audit may still be running: reload the page to follow it.");
        }
      };
    }

    start();
    return () => {
      cancelled.current = true;
      socket?.close();
      timers.current.forEach(clearTimeout);
      timers.current = [];
      if (print) delete document.body.dataset.print;
    };
  }, [id, replay, print, showReport]);

  const timeline = live.steps.map((s, i) => ({ label: stepLabel(s, i + 1), status: live.statuses[i] ?? null }));
  const passed = Object.values(live.statuses).filter((s) => PASSED.includes(s)).length;

  return (
    <main
      id="main"
      className="mx-auto w-full max-w-6xl px-4 py-8"
      data-report-ready={phase === "report" && report ? "" : undefined}
    >
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {live.announcement}
      </div>

      {error && (
        <p role="alert" className="mb-6 rounded-lg border border-fail bg-red-50 px-4 py-3 font-bold text-fail">
          {error}
        </p>
      )}

      {phase === "loading" && !error && <p className="text-lg">Loading the audit…</p>}

      {phase === "live" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h1 className="text-3xl font-bold text-navy">{replay ? "Replaying audit" : "Audit in progress"}</h1>
            {replay && (
              <button
                type="button"
                onClick={showReport}
                className="rounded-lg border border-navy px-4 py-2 font-bold text-navy hover:bg-accent"
              >
                Skip to the report
              </button>
            )}
          </div>
          <p className="text-ink-soft">
            {live.walking
              ? `Keyboard walker: ${passed} of ${live.steps.length} steps passed, ${live.barriers} barrier(s) so far.`
              : "Step 1: a sighted agent completes the task to prove it's possible. Step 2: the keyboard walker repeats it."}
          </p>
          <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
            <section aria-labelledby="view-title">
              <h2 id="view-title" className="mb-2 text-lg font-bold text-navy">
                {live.walking ? "Keyboard walker" : "Sighted agent"}
              </h2>
              <StreamPanel streamingUrl={live.streamingUrl} cached={live.cached} walking={live.walking} screenshot={live.screenshot} />
            </section>
            <div className="space-y-6">
              <section aria-labelledby="timeline-title">
                <h2 id="timeline-title" className="mb-2 text-lg font-bold text-navy">
                  Steps
                </h2>
                <StepTimeline steps={timeline} running />
              </section>
              <section aria-labelledby="log-title">
                <h2 id="log-title" className="mb-2 text-lg font-bold text-navy">
                  Log
                </h2>
                <StepLog lines={live.log} />
              </section>
            </div>
          </div>
        </div>
      )}

      {phase === "report" && report && <Report report={report} baselineSteps={baselineSteps} print={print} />}
    </main>
  );
}
