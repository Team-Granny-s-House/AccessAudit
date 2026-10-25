import { fileUrl } from "@/lib/api";

export interface LogLine {
  key: string;
  kind: "progress" | "stop" | "issue" | "info" | "error";
  text: string;
}

/** Left: the TinyFish live stream, the cached-baseline notice, or the walker's latest screenshot. */
export function StreamPanel({
  streamingUrl,
  cached,
  walking,
  screenshot,
  replay = false,
}: {
  streamingUrl: string | null;
  cached: boolean;
  walking: boolean;
  screenshot: string | null;
  replay?: boolean;
}) {
  const shot = fileUrl(screenshot);
  let body: React.ReactNode;
  if (walking && shot) {
    // eslint-disable-next-line @next/next/no-img-element
    body = <img src={shot} alt="Latest screenshot from the keyboard walker" className="w-full rounded-lg" />;
  } else if (walking) {
    body = <Notice>The keyboard walker is running in a TinyFish cloud browser. Screenshots appear here at each barrier.</Notice>;
  } else if (cached) {
    body = <Notice>Using a saved baseline — no live stream for this run</Notice>;
  } else if (replay) {                               // the original stream has ended, and replays work offline
    body = <Notice>Replay: the sighted agent&apos;s live stream isn&apos;t saved. Its steps appear in the log.</Notice>;
  } else if (streamingUrl) {
    body = (
      <iframe
        src={streamingUrl}
        title="Live view of the sighted agent's browser"
        className="aspect-video w-full rounded-lg border-0 bg-slate-100"
      />
    );
  } else {
    body = <Notice>Starting the sighted agent… its live browser view appears here.</Notice>;
  }
  return <div className="rounded-xl border border-border bg-muted p-2">{body}</div>;
}

function Notice({ children }: { children: React.ReactNode }) {
  return <p className="flex aspect-video items-center justify-center p-6 text-center text-lg font-bold text-navy">{children}</p>;
}

/** Right: the sighted agent's progress lines, then what the screen reader announces at each focus stop. */
export function StepLog({ lines }: { lines: LogLine[] }) {
  const style: Record<LogLine["kind"], string> = {
    progress: "",
    stop: "font-mono",
    issue: "font-bold text-fail",
    info: "font-bold text-navy",
    error: "font-bold text-fail",
  };
  return (
    // tabIndex: a scrollable region must be reachable by keyboard so arrow keys can scroll it
    <ol tabIndex={0} className="max-h-80 space-y-1 overflow-y-auto rounded-xl border border-border p-3 text-sm" aria-label="Audit log">

      {lines.length === 0 && <li className="text-ink-soft">Waiting for events…</li>}
      {lines.slice(-300).map((l) => (
        <li key={l.key} className={style[l.kind]}>
          {l.text}
        </li>
      ))}
    </ol>
  );
}
