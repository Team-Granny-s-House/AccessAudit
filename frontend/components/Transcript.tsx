"use client";

import { useEffect, useState } from "react";
import { spoken, type Stop } from "@/lib/api";
import { speak, stopSpeaking, useCanSpeak } from "@/lib/speech";

/** Every focus stop, as a screen reader would announce it; "Play all" reads them aloud. */
export default function Transcript({ stops }: { stops: Stop[] }) {
  const [playing, setPlaying] = useState(false);
  const speechOk = useCanSpeak();

  useEffect(() => stopSpeaking, []);                 // stop talking when the report unmounts

  if (stops.length === 0) return <p className="text-ink-soft">No focus stops were recorded.</p>;

  function toggle() {
    if (playing) {
      stopSpeaking();
      setPlaying(false);
    } else {
      setPlaying(true);
      speak(stops.map((s) => spoken(s.announce) || s.tag), () => setPlaying(false));
    }
  }

  return (
    <div className="space-y-3">
      {speechOk && (
        <button
          type="button"
          onClick={toggle}
          aria-pressed={playing}
          className="no-print rounded-lg bg-navy px-4 py-2 font-bold text-white hover:bg-navy-soft"
        >
          {playing ? "■ Stop" : "▶ Play all"}
        </button>
      )}
      <ol
        tabIndex={0}
        aria-label="Screen-reader transcript"
        className="max-h-96 space-y-1 overflow-y-auto rounded-xl border border-border p-3 font-mono text-sm print:max-h-none print:overflow-visible"
      >
        {stops.map((s) => (
          <li key={s.seq} className="flex gap-3">
            <span className="w-8 shrink-0 text-right text-ink-soft">{s.seq}</span>
            <span className="flex-1">{spoken(s.announce) || s.tag}</span>
            {!s.focus_ring && <span className="shrink-0 font-sans text-xs font-bold text-fail">no visible focus</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}
