import type { Note, PageScan } from "@/lib/api";

export function PageScanSummary({ scans, open = false }: { scans: PageScan[]; open?: boolean }) {
  if (scans.length === 0) return <p className="text-ink-soft">No pages were scanned.</p>;
  return (
    <div className="space-y-2">
      {scans.map((scan) => (
        <details key={scan.url} open={open} className="break-inside-avoid rounded-xl border border-border p-3">
          <summary className="cursor-pointer font-bold">
            {scan.url}{" "}
            <span className="font-normal text-ink-soft">
              — {scan.error ? scan.error : `${scan.violations.length} rule${scan.violations.length === 1 ? "" : "s"} failed`}
            </span>
          </summary>
          {scan.violations.length > 0 && (
            <ul className="mt-2 space-y-1">
              {scan.violations.map((v) => (
                <li key={v.rule}>
                  <span className="font-bold capitalize">{v.impact ?? "unknown"}</span>{" "}
                  <a href={v.help_url} target="_blank" rel="noreferrer" className="text-link underline underline-offset-2">
                    {v.help}
                    <span className="sr-only"> (opens in a new tab)</span>
                  </a>{" "}
                  <span className="text-ink-soft">
                    ({v.rule}, {v.count} element{v.count === 1 ? "" : "s"})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </details>
      ))}
    </div>
  );
}

export function Notes({ notes }: { notes: Note[] }) {
  const statement = notes.find((n) => n.type === "accessibility_statement");
  if (!statement) return null;
  return (
    <p className="rounded-xl border border-border bg-muted p-3">
      <span className="font-bold">Accessibility statement: </span>
      {statement.found ? (
        <>
          found,{" "}
          <a href={statement.url ?? "#"} className="text-link underline underline-offset-2">
            {statement.url}
          </a>
        </>
      ) : (
        "the home page doesn't link to one."
      )}{" "}
      <span className="text-ink-soft">(Not scored.)</span>
    </p>
  );
}
