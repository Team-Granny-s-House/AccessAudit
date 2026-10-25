import { BLOCKED, PASSED, STATUS_TEXT } from "@/lib/api";

export interface TimelineStep {
  label: string;
  status: string | null; // null = not reached (yet)
}

/** One dot per baseline step: green passed, red blocked, grey not reached. */
export default function StepTimeline({ steps, running = false }: { steps: TimelineStep[]; running?: boolean }) {
  if (steps.length === 0) {
    return <p className="text-ink-soft">{running ? "Waiting for the sighted agent's steps…" : "No steps were recorded."}</p>;
  }
  return (
    <ol className="space-y-2">
      {steps.map((s, i) => {
        const passed = s.status !== null && PASSED.includes(s.status);
        const blocked = s.status !== null && BLOCKED.includes(s.status);
        const dot = passed ? "bg-pass" : blocked ? "bg-fail" : s.status ? "bg-slate-500" : "bg-slate-300";
        const text = s.status ? STATUS_TEXT[s.status] ?? s.status : running ? "waiting" : "not reached";
        return (
          <li key={i} className="flex items-start gap-3">
            <span aria-hidden="true" className={`mt-1 size-4 shrink-0 rounded-full ${dot} ${blocked ? "ring-4 ring-red-200" : ""}`} />
            <span>
              <span className="font-bold">Step {i + 1}:</span> {s.label}{" "}
              <span className={passed ? "text-pass" : blocked ? "font-bold text-fail" : "text-ink-soft"}>— {text}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
