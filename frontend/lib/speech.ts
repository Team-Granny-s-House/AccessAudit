// Plays announcements aloud with the browser's built-in speechSynthesis.
import { useSyncExternalStore } from "react";

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

const noSubscription = () => () => {};

/** false while rendering on the server, then whether this browser can speak. */
export function useCanSpeak(): boolean {
  return useSyncExternalStore(noSubscription, canSpeak, () => false);
}

export function speak(texts: string[], onEnd?: () => void): void {
  if (!canSpeak() || texts.length === 0) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  texts.forEach((text, i) => {
    const u = new SpeechSynthesisUtterance(text);
    if (i === texts.length - 1 && onEnd) {
      u.onend = onEnd;
      u.onerror = onEnd;
    }
    synth.speak(u);
  });
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel();
}
