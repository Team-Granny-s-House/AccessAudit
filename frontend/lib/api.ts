// Types and helpers for the AccessAudit backend (shapes from the spec's Data contracts).

export const API = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type Severity = "Blocker" | "Critical" | "Serious" | "Moderate";
export type Persona = "screen_reader" | "keyboard";

export interface BaselineStep {
  action: string;
  element_text: string;
  element_role?: string;
  value?: string;
  description?: string | null;
  page_url?: string;
}

export interface StepResult {
  index: number;
  action: string | null;
  element_text: string;
  description?: string | null;
  status: string;
  presses: number;
  screenshot: string | null;
}

export interface Issue {
  id: string;
  check: string;
  step_index: number | null;
  page_url: string;
  wcag: string;
  severity: Severity;
  title: string;
  who: string;
  announce: string;
  element_html: string;
  screenshot: string | null;
  fix: string;
  help_url: string;
  count: number;
}

export interface Stop {
  seq: number;
  tag: string;
  text: string;
  announce: string;
  focus_ring: boolean;
  page_url: string;
}

export interface Violation {
  rule: string;
  impact: string | null;
  help: string;
  help_url: string;
  tags: string[];
  count: number;
  nodes: { target: string[]; html: string }[];
}

export interface PageScan {
  url: string;
  violations: Violation[];
  error: string | null;
}

export interface Note {
  type: string;
  found: boolean;
  url: string | null;
}

export interface Report {
  id: string;
  url: string;
  task: string;
  persona: Persona;
  created_at: string;
  status: "running" | "done" | "error";
  verdict: string | null;
  score: number | null;
  blocked_at: number | null;
  total_steps: number;
  baseline_source: "agent" | "override" | null;
  cached: boolean;
  steps: StepResult[];
  issues: Issue[];
  transcript: Stop[];
  page_scans: PageScan[];
  notes: Note[];
}

export interface AuditSummary {
  id: string;
  url: string;
  task: string;
  persona: Persona;
  created_at: string;
  status: string;
  verdict: string | null;
  score: number | null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface AuditEvent { type: string; t: number; data: any }

export const PASSED = ["activated", "typed", "stopped_safely"];
export const BLOCKED = ["unreachable", "trap", "no_response"];

export const STATUS_TEXT: Record<string, string> = {
  activated: "passed",
  typed: "passed",
  stopped_safely: "passed (stopped before a submit button)",
  unreachable: "blocked: can't be reached with the keyboard",
  trap: "blocked: keyboard trap",
  no_response: "blocked: ignores the keyboard",
  baseline_mismatch: "inconclusive: the agent's label isn't on the page",
};

export const PERSONA_TEXT: Record<Persona, string> = {
  screen_reader: "Screen-reader user",
  keyboard: "Keyboard-only user",
};

/** The spec's demo task: the presets must use it word for word so they hit the baseline cache. */
export const SKYRAIL_TASK = "Find trains, select the first train, and enter the passenger name Asha Verma.";

export const PRESETS = [
  { label: "SkyRail (broken)", url: "https://skyrail-demo.vercel.app/broken/index.html", task: SKYRAIL_TASK },
  { label: "SkyRail (fixed)", url: "https://skyrail-demo.vercel.app/fixed/index.html", task: SKYRAIL_TASK },
];

export function fileUrl(path: string | null | undefined): string | null {
  return path ? `${API}${path}` : null;
}

export function wsUrl(id: string): string {
  return `${API.replace(/^http/, "ws")}/audits/${id}/events`;
}

/** What a screen reader says: '- button "Search"' becomes 'button Search', '- button' becomes 'button'. */
export function spoken(announce: string): string {
  return announce.replace(/^-\s*/, "").replace(/["[\]]/g, "").replace(/\s+/g, " ").trim();
}

export function stepLabel(step: { description?: string | null; element_text: string } | undefined, n: number): string {
  if (!step) return `Step ${n}`;
  return step.description || step.element_text || `Step ${n}`;
}

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(r.status === 404 ? "not-found" : `HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

export const getReport = (id: string) => getJson<Report>(`/audits/${id}`);
export const getReplay = (id: string) => getJson<AuditEvent[]>(`/audits/${id}/replay`);
export const listAudits = () => getJson<AuditSummary[]>("/audits");

export async function startAudit(body: { url: string; task: string; persona: Persona }): Promise<string> {
  const r = await fetch(`${API}/audits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.status === 409) throw new Error("Another audit is running. Wait for it to finish, then try again.");
  if (!r.ok) {
    const detail = await r.json().then((d) => d.detail).catch(() => null);
    throw new Error(typeof detail === "string" ? detail : "The audit couldn't start. Check the URL and task.");
  }
  return (await r.json()).id;
}
