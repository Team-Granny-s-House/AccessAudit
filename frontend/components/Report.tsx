import Link from "next/link";
import { API, PERSONA_TEXT, stepLabel, type BaselineStep, type Report as ReportData } from "@/lib/api";
import BarrierCard from "./BarrierCard";
import { Notes, PageScanSummary } from "./PageScanSummary";
import ScoreRing from "./ScoreRing";
import StepTimeline from "./StepTimeline";
import Transcript from "./Transcript";
import VerdictBadge from "./VerdictBadge";

export default function Report({
  report,
  baselineSteps,
  print = false,
}: {
  report: ReportData;
  baselineSteps: BaselineStep[] | null;
  print?: boolean;
}) {
  const total = Math.max(report.total_steps, baselineSteps?.length ?? 0, report.steps.length);
  const timeline = Array.from({ length: total }, (_, i) => {
    const walked = report.steps.find((s) => s.index === i);
    return { label: stepLabel(walked ?? baselineSteps?.[i], i + 1), status: walked?.status ?? null };
  });
  const source =
    report.baseline_source === "override"
      ? "hand-checked steps"
      : report.cached
        ? "a saved sighted-agent baseline"
        : "a live sighted-agent run";

  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-center gap-6">
        <ScoreRing score={report.score} />
        <div className="min-w-0 flex-1 space-y-2">
          <h1 className="text-3xl font-bold text-navy">Audit report</h1>
          <VerdictBadge verdict={report.status === "error" ? "Inconclusive" : report.verdict} />
          <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
            <dt className="font-bold">Site</dt>
            <dd className="break-all">{report.url}</dd>
            <dt className="font-bold">Task</dt>
            <dd>{report.task}</dd>
            <dt className="font-bold">Tested as</dt>
            <dd>{PERSONA_TEXT[report.persona] ?? report.persona}</dd>
            <dt className="font-bold">Date</dt>
            <dd>
              <time dateTime={report.created_at}>{new Date(report.created_at).toLocaleString()}</time>
            </dd>
            <dt className="font-bold">Baseline</dt>
            <dd>{source}</dd>
          </dl>
        </div>
      </header>

      {report.error && (
        <div role="alert" className="rounded-xl border-2 border-slate-400 bg-slate-50 p-4">
          <h2 className="font-bold text-navy">
            {report.status === "error" ? "The audit stopped" : "Why this audit is inconclusive"}
          </h2>
          <p>{report.error}</p>
        </div>
      )}

      {!print && (
        <div className="no-print flex flex-wrap gap-3">
          <a
            href={`${API}/audits/${report.id}/pdf`}
            className="rounded-lg bg-navy px-4 py-2 font-bold text-white no-underline hover:bg-navy-soft"
          >
            Download PDF
          </a>
          <Link href="/" className="rounded-lg border border-navy px-4 py-2 font-bold text-navy hover:bg-accent">
            New audit
          </Link>
        </div>
      )}

      <section aria-labelledby="steps-title" className="break-inside-avoid">
        <h2 id="steps-title" className="mb-3 text-xl font-bold text-navy">
          Task steps, tried with the keyboard only
        </h2>
        <StepTimeline steps={timeline} />
      </section>

      <section aria-labelledby="barriers-title">
        <h2 id="barriers-title" className="mb-3 text-xl font-bold text-navy">
          Barriers ({report.issues.length})
        </h2>
        {report.issues.length === 0 ? (
          <p className="text-pass font-bold">No barriers found on the path the walker took.</p>
        ) : (
          <div className="space-y-4">
            {report.issues.map((issue) => (
              <BarrierCard key={issue.id} issue={issue} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="transcript-title">
        <h2 id="transcript-title" className="mb-3 text-xl font-bold text-navy">
          What a screen reader heard
        </h2>
        <Transcript stops={report.transcript} />
      </section>

      <section aria-labelledby="scans-title">
        <h2 id="scans-title" className="mb-3 text-xl font-bold text-navy">
          Page scans
        </h2>
        <PageScanSummary scans={report.page_scans} open={print} />
      </section>

      <Notes notes={report.notes} />
    </div>
  );
}
