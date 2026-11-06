import { RotateCcw, Sparkles } from "lucide-react";
import { useId, type ReactNode } from "react";

export interface MixValues {
  music_volume: number;
  duck: boolean;
  duck_amount: number;
  duck_release: number;
  target_lufs: number;
  music_fade_in: number;
  music_fade_out: number;
}

/* What the system decides when nobody chooses. Every control below shows whether it is still on this setting ("Automatic") or has been changed by you ("Yours"). */
export const MIX_DEFAULTS: MixValues = { music_volume: 0.1, duck: true, duck_amount: 0.4, duck_release: 0.35, target_lufs: -14, music_fade_in: 1, music_fade_out: 2 };

export const mixOf = (o: Partial<MixValues> | undefined): MixValues => ({ ...MIX_DEFAULTS, ...Object.fromEntries(Object.entries(o ?? {}).filter(([k, v]) => k in MIX_DEFAULTS && v != null)) });

const toDb = (v: number) => Math.round(20 * Math.log10(Math.max(v, 0.001)));
const fromDb = (db: number) => +Math.pow(10, db / 20).toFixed(4);
const same = (a: number, b: number) => Math.abs(a - b) < 0.011;

/* One setting: its name, the value in words, who set it (system or you), and a way back to automatic. */
function Row({ title, value, hint, mine, onReset, disabled, children }: { title: string; value: string; hint: string; mine: boolean; onReset: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <div className={`mix-row${disabled ? " is-off" : ""}`}>
      <div className="mix-head">
        <span className="mix-title">{title}</span>
        <span className="mix-value">{value}</span>
        {mine ? (
          <button type="button" className="mix-tag yours" onClick={onReset} disabled={disabled} title="Go back to the automatic setting"><RotateCcw size={11} aria-hidden /> Yours, reset</button>
        ) : (
          <span className="mix-tag auto" title="The system chooses this for you"><Sparkles size={11} aria-hidden /> Automatic</span>
        )}
      </div>
      {children}
      <p className="mix-hint">{hint}</p>
    </div>
  );
}

/* Everything about the sound that the system sets by itself, shown and adjustable: music level (dB), ducking under speech, overall loudness, music fades. Used in the editor and on the export page. */
export default function MusicMix({ value: v, onChange, disabled }: { value: MixValues; onChange: (patch: Partial<MixValues>) => void; disabled?: boolean }) {
  const id = useId();
  const D = MIX_DEFAULTS;
  const db = toDb(v.music_volume);
  const off = !!disabled;
  const duckOff = off || !v.duck;
  return (
    <div className="mix" data-testid="music-mix">
      <Row title="Music level" value={`${db} dB`} mine={db !== toDb(D.music_volume)} onReset={() => onChange({ music_volume: D.music_volume })} disabled={off}
        hint={`0 dB is the track as it is. ${db <= -26 ? "A quiet bed under the voice." : db <= -16 ? "Clearly behind the voice." : "Up front: the voice may struggle."} Automatic: ${toDb(D.music_volume)} dB.`}>
        <input type="range" min={-40} max={-6} step={1} value={db} disabled={off} aria-label="Music level in dB" onChange={(e) => onChange({ music_volume: fromDb(+e.target.value) })} />
      </Row>

      <Row title="Ducking" value={v.duck ? `${Math.round(v.duck_amount * 100)}%` : "Off"} mine={v.duck !== D.duck || (v.duck && !same(v.duck_amount, D.duck_amount))}
        onReset={() => onChange({ duck: D.duck, duck_amount: D.duck_amount })} disabled={off}
        hint="The music sinks while someone speaks and returns in the pauses. Higher = it sinks further.">
        <label className="mix-switch" htmlFor={`${id}-duck`}>
          <input id={`${id}-duck`} type="checkbox" checked={v.duck} disabled={off} onChange={(e) => onChange({ duck: e.target.checked })} />
          <span>Lower the music under speech</span>
        </label>
        <input type="range" min={0} max={1} step={0.05} value={v.duck_amount} disabled={duckOff} aria-label="Ducking strength" onChange={(e) => onChange({ duck_amount: +e.target.value })} />
      </Row>

      <Row title="Music returns after" value={`${v.duck_release.toFixed(2)} s`} mine={!same(v.duck_release, D.duck_release)} onReset={() => onChange({ duck_release: D.duck_release })} disabled={duckOff}
        hint="How long the music waits after a phrase before it swells back. Short = lively, long = smooth.">
        <input type="range" min={0.1} max={1.5} step={0.05} value={v.duck_release} disabled={duckOff} aria-label="Seconds before the music comes back" onChange={(e) => onChange({ duck_release: +e.target.value })} />
      </Row>

      <Row title="Overall loudness" value={`${v.target_lufs} LUFS`} mine={!same(v.target_lufs, D.target_lufs)} onReset={() => onChange({ target_lufs: D.target_lufs })}
        hint="The finished video is set to this level. -14 is what social platforms play at; quieter is gentler, louder risks being turned down.">
        <input type="range" min={-23} max={-9} step={1} value={v.target_lufs} aria-label="Overall loudness in LUFS" onChange={(e) => onChange({ target_lufs: +e.target.value })} />
      </Row>

      <Row title="Music fade in" value={`${v.music_fade_in.toFixed(1)} s`} mine={!same(v.music_fade_in, D.music_fade_in)} onReset={() => onChange({ music_fade_in: D.music_fade_in })} disabled={off} hint="How slowly the music starts.">
        <input type="range" min={0} max={6} step={0.5} value={v.music_fade_in} disabled={off} aria-label="Music fade in, seconds" onChange={(e) => onChange({ music_fade_in: +e.target.value })} />
      </Row>

      <Row title="Music fade out" value={`${v.music_fade_out.toFixed(1)} s`} mine={!same(v.music_fade_out, D.music_fade_out)} onReset={() => onChange({ music_fade_out: D.music_fade_out })} disabled={off} hint="How slowly the music ends.">
        <input type="range" min={0} max={8} step={0.5} value={v.music_fade_out} disabled={off} aria-label="Music fade out, seconds" onChange={(e) => onChange({ music_fade_out: +e.target.value })} />
      </Row>
    </div>
  );
}
