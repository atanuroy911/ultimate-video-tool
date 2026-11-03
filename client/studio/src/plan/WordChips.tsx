import { useT } from "../i18n";
import type { Moment } from "./types";

/* The words of a moment, with dots for how strongly each one is stressed. The filled chip is where the picture changes; choosing another word moves the change there. */
export default function WordChips({ moment, onPick, disabled }: { moment: Moment; onPick: (wordId: string) => void; disabled?: boolean }) {
  const tt = useT();
  return (
    <div className="pl-words bn" role="group" aria-label={tt("pl.chooseword")}>
      {moment.words.map((w) => {
        const dots = w.stress >= 0.9 ? 3 : w.stress >= 0.5 ? 2 : w.stress >= 0.2 ? 1 : 0;
        const on = w.id === moment.beat.word_id;
        return (
          <button key={w.id} type="button" className={`pl-chip ${on ? "on" : ""}`} aria-pressed={on} disabled={disabled} onClick={() => !on && onPick(w.id)} title={on ? tt("pl.here") : tt("pl.onword")}>
            {w.text}
            {dots > 0 && <span className="pl-dots" aria-label={`stress ${dots} of 3`}>{"●".repeat(dots)}</span>}
          </button>
        );
      })}
    </div>
  );
}
