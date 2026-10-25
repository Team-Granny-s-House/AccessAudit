"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API, listAudits, type AuditSummary } from "@/lib/api";
import ScoreRing from "./ScoreRing";

export default function RecentAudits() {
  const [audits, setAudits] = useState<AuditSummary[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    listAudits().then(setAudits).catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <p role="alert" className="text-fail">
        Couldn&apos;t reach the AccessAudit backend at {API}. Is it running?
      </p>
    );
  }
  if (audits === null) return <p className="text-ink-soft">Loading recent audits…</p>;
  if (audits.length === 0) return <p className="text-ink-soft">No audits yet. Run one above.</p>;

  return (
    <ul className="divide-y divide-border rounded-xl border border-border">
      {audits.map((a) => (
        <li key={a.id} className="flex items-center gap-4 p-3">
          <ScoreRing score={a.score} size={48} />
          <div className="min-w-0 flex-1">
            <Link href={`/audit/${a.id}`} className="font-bold text-link underline underline-offset-2">
              {a.verdict ?? (a.status === "running" ? "Running…" : "Inconclusive")}
            </Link>
            <p className="truncate text-sm text-ink-soft">{a.url}</p>
            <p className="truncate text-sm">{a.task}</p>
          </div>
          <time dateTime={a.created_at} className="shrink-0 text-sm text-ink-soft">
            {new Date(a.created_at).toLocaleString()}
          </time>
        </li>
      ))}
    </ul>
  );
}
