export default function VerdictBadge({ verdict }: { verdict: string | null }) {
  const text = verdict ?? "Running…";
  const style = text === "Completed"
    ? "border-pass bg-green-50 text-pass"
    : text.startsWith("Blocked")
      ? "border-fail bg-red-50 text-fail"
      : text === "Completed with barriers"
        ? "border-warn bg-amber-50 text-warn"
        : "border-slate-400 bg-slate-50 text-slate-700";
  return (
    <p className={`inline-block rounded-full border-2 px-4 py-1 text-lg font-bold ${style}`}>
      <span className="sr-only">Verdict: </span>
      {text}
    </p>
  );
}
