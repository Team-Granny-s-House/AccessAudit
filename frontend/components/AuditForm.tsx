"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PERSONA_TEXT, PRESETS, startAudit, type Persona } from "@/lib/api";

export default function AuditForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [task, setTask] = useState("");
  const [persona, setPersona] = useState<Persona>("screen_reader");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const id = await startAudit({ url: url.trim(), task: task.trim(), persona });
      router.push(`/audit/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The audit couldn't start.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl border border-border bg-muted p-5" aria-describedby="form-help">
      <p id="form-help" className="text-ink-soft">
        Give a public page and a task in plain language. A sighted agent does the task first, then the keyboard
        walker tries to repeat it.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-bold" id="presets-label">Try a demo:</span>
        <div role="group" aria-labelledby="presets-label" className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => {
                setUrl(p.url);
                setTask(p.task);
              }}
              className="rounded-full border border-navy bg-white px-3 py-1.5 text-sm font-bold text-navy hover:bg-accent"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label htmlFor="url" className="mb-1 block font-bold">
          Website URL
        </label>
        <input
          id="url"
          name="url"
          type="url"
          required
          inputMode="url"
          placeholder="https://example.gov.in/admissions"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="w-full rounded-lg border border-input bg-white px-3 py-2"
        />
      </div>

      <div>
        <label htmlFor="task" className="mb-1 block font-bold">
          Task
        </label>
        <textarea
          id="task"
          name="task"
          required
          rows={3}
          placeholder="Find the fee for B.Tech admission"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          className="w-full rounded-lg border border-input bg-white px-3 py-2"
        />
      </div>

      <fieldset>
        <legend className="mb-1 font-bold">Test as</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {(Object.keys(PERSONA_TEXT) as Persona[]).map((p) => (
            <label key={p} className="inline-flex items-center gap-2">
              <input
                type="radio"
                name="persona"
                value={p}
                checked={persona === p}
                onChange={() => setPersona(p)}
                className="size-4 accent-navy"
              />
              {PERSONA_TEXT[p]}
            </label>
          ))}
        </div>
      </fieldset>

      {error && (
        <p role="alert" className="rounded-lg border border-fail bg-red-50 px-3 py-2 font-bold text-fail">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="rounded-lg bg-navy px-5 py-2.5 font-bold text-white hover:bg-navy-soft disabled:opacity-70"
      >
        {busy ? "Starting…" : "Run audit"}
      </button>
    </form>
  );
}
