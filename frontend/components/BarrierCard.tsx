"use client";

import { useState } from "react";
import { fileUrl, spoken, type Issue } from "@/lib/api";
import { speak, useCanSpeak } from "@/lib/speech";

const SEVERITY_STYLE: Record<string, string> = {
  Blocker: "bg-fail text-white",
  Critical: "border border-fail text-fail",
  Serious: "border border-warn text-warn",
  Moderate: "border border-slate-500 text-slate-700",
};

export default function BarrierCard({ issue }: { issue: Issue }) {
  const [copied, setCopied] = useState(false);
  const speechOk = useCanSpeak();
  const shot = fileUrl(issue.screenshot);
  const heard = issue.announce ? spoken(issue.announce) : null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(issue.fix);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article className="break-inside-avoid space-y-3 rounded-xl border border-border p-4" aria-labelledby={`issue-${issue.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 id={`issue-${issue.id}`} className="text-lg font-bold">
          {issue.title}
        </h3>
        <span className={`rounded-full px-3 py-0.5 text-sm font-bold ${SEVERITY_STYLE[issue.severity] ?? ""}`}>
          {issue.severity}
        </span>
      </div>

      {shot && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={shot}
          alt={`Screenshot of the page at this barrier${issue.check.startsWith("axe:") ? "" : ", with the element outlined in magenta"}`}
          className="w-full rounded-lg border border-border"
        />
      )}

      <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-[max-content_1fr]">
        {heard !== null && (
          <>
            <dt className="font-bold">What a screen reader heard</dt>
            <dd className="flex flex-wrap items-center gap-2">
              <q className="font-mono">{heard}</q>
              {speechOk && (
                <button
                  type="button"
                  onClick={() => speak([heard])}
                  className="no-print rounded-md border border-navy px-2 py-0.5 text-sm font-bold text-navy hover:bg-accent"
                  aria-label={`Play what a screen reader heard: ${heard}`}
                >
                  ▶ Play
                </button>
              )}
            </dd>
          </>
        )}
        <dt className="font-bold">Who this blocks</dt>
        <dd>{issue.who}</dd>
        <dt className="font-bold">WCAG</dt>
        <dd>
          <a href={issue.help_url} className="text-link underline underline-offset-2" target="_blank" rel="noreferrer">
            {issue.wcag ? `Success criterion ${issue.wcag}` : "Rule details"}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
          {issue.count > 1 && <span className="text-ink-soft"> · found on {issue.count} elements</span>}
        </dd>
        <dt className="font-bold">Page</dt>
        <dd className="break-all text-ink-soft">{issue.page_url}</dd>
      </dl>

      <div>
        <div className="mb-1 flex items-center justify-between gap-2">
          <h4 className="font-bold">Suggested fix</h4>
          <button
            type="button"
            onClick={copy}
            className="no-print rounded-md border border-navy px-2 py-0.5 text-sm font-bold text-navy hover:bg-accent"
          >
            {copied ? "Copied" : "Copy fix"}
          </button>
        </div>
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-3 text-sm text-slate-100">
          <code>{issue.fix}</code>
        </pre>
        {issue.element_html && (
          <details className="mt-2">
            <summary className="cursor-pointer text-sm font-bold text-navy">Element HTML</summary>
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded-lg bg-muted p-2 text-xs">
              <code>{issue.element_html}</code>
            </pre>
          </details>
        )}
      </div>
      <p className="sr-only" aria-live="polite">{copied ? "Fix copied to the clipboard" : ""}</p>
    </article>
  );
}
