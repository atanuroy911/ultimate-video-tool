// Video Tool: OpenChatCut's timeline on our editor page (docs/plans/PLAN-OPENCHATCUT.MD). Our project is shown on its tracks (fromProject.ts),
// driven by our preview player (playerAdapter.ts), and every finished edit is saved to our project (toProject.ts → onSave). After a save the
// project reloads and the timeline is rebuilt from it, so what is shown is what was saved; undo then goes to our server's history.
import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import type { PlayerRef } from '@remotion/player';
import '../occ.css';
import { useEditor } from '../src/editor/store';
import type { EditorCommands } from '../src/editor/store';
import type { ProjectDoc } from '../src/editor/projectTypes';
import { activeEditorState } from '../src/editor/types';
import { Timeline } from '../src/components/timeline/Timeline';
import { useEditorActions } from '../src/shortcuts/useEditorActions';
import type { TimelineShortcutApi } from '../src/shortcuts/timelineApi';
import type { PlayerHandle } from '../../review/Preview';
import type { LDoc } from '../../types';
import { fromProject, VOICE_ID, type ProjectView } from './fromProject';
import { makePlayerAdapter } from './playerAdapter';
import { planSave, type SaveOp } from './toProject';

export interface OccTimelineProps {
  view: ProjectView;
  /** changes when our project changes on the server: the view is rebuilt from it */
  revision: string;
  player: RefObject<PlayerHandle>;
  playing: boolean;
  /** applies the edits to our project (the same calls the classic timeline makes); resolves when they are saved */
  onSave: (ops: SaveOp[]) => Promise<void>;
  /** our project's undo / redo (the server's history) */
  onUndo: () => void;
  onRedo: () => void;
  /** the Director owns the plan while it works; keep the timeline visible but disable every editing shortcut */
  disabled?: boolean;
  /** scenes the Director just changed; their scene and element clips glow briefly */
  highlightScenes?: string[];
  /** double-click on the narration: the time under the pointer, so the page can open that word's caption (W11.1, the classic word lane) */
  onWordAt?: (t: number) => void;
  /** double-click on a cut mark: bring that cut back */
  onRestoreCut?: (index: number) => void;
}

const SAVE_AFTER_MS = 450;           // an edit is saved once the pointer is up and nothing changed for this long

export default function OccTimeline({ view, revision, player, playing, onSave, onUndo, onRedo, disabled = false, highlightScenes = [], onWordAt, onRestoreCut }: OccTimelineProps) {
  const doc = useMemo(() => fromProject(view), [revision]); // eslint-disable-line react-hooks/exhaustive-deps -- rebuilt when the project changes
  const adapter = useMemo(() => makePlayerAdapter(player, view.fps), [player, view.fps]);
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => adapter.setPlaying(playing), [adapter, playing]);
  useEffect(() => {
    const root = host.current;
    if (!root || !highlightScenes.length) return;
    const clips = highlightScenes.flatMap((scene) => [
      ...root.querySelectorAll<HTMLElement>(`[data-item-id="scene:${CSS.escape(scene)}"]`),
      ...root.querySelectorAll<HTMLElement>(`[data-item-id^="el:${CSS.escape(scene)}:"]`),
    ]);
    clips.forEach((clip) => clip.classList.add('is-director-changed'));
    const timer = window.setTimeout(() => clips.forEach((clip) => clip.classList.remove('is-director-changed')), 7000);
    return () => { window.clearTimeout(timer); clips.forEach((clip) => clip.classList.remove('is-director-changed')); };
  }, [highlightScenes.join('|'), revision]); // eslint-disable-line react-hooks/exhaustive-deps
  const [status, setStatus] = useState<Status>({ kind: 'idle' });      // kept here: the board is rebuilt after each save
  return (
    <div className="occ-host" data-testid="occ-timeline" ref={host}>
      {status.kind !== 'idle' && (
        <p className={`occ-status ${status.kind}`} role="status" data-testid="occ-status">
          {status.kind === 'saving' ? 'Saving…'
            : status.kind === 'saved' ? 'Saved.'
            : status.kind === 'error' ? `Not saved: ${status.message}`
            : `Not saved from the timeline yet: ${status.what.join(', ')}.`}
        </p>
      )}
      <Board key={revision} base={doc} layers={view.layers ?? null} adapter={adapter} projectId={view.projectId} onSave={onSave} onUndo={onUndo} onRedo={onRedo} disabled={disabled} setStatus={setStatus} onWordAt={onWordAt} onRestoreCut={onRestoreCut} />
    </div>
  );
}

type Status = { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved' } | { kind: 'ignored'; what: string[] } | { kind: 'error'; message: string };

function Board({ base, layers, adapter, projectId, onSave, onUndo, onRedo, disabled, setStatus, onWordAt, onRestoreCut }: {
  base: ProjectDoc; layers: LDoc | null; adapter: PlayerRef & { fps: number }; projectId: string;
  onSave: (ops: SaveOp[]) => Promise<void>; onUndo: () => void; onRedo: () => void; disabled: boolean; setStatus: (s: Status) => void;
  onWordAt?: (t: number) => void;
  onRestoreCut?: (index: number) => void;
}) {
  const { state, commands, doc: live } = useEditor(base);
  const playerRef = useRef<PlayerRef | null>(adapter);
  playerRef.current = adapter;
  // undo: a change not saved yet is undone here; a saved one through our project's history
  const dirty = live !== base;
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const wrapped = useMemo<EditorCommands>(() => ({
    ...commands,
    undo: () => (dirtyRef.current ? commands.undo() : onUndo()),
    redo: () => (dirtyRef.current ? commands.redo() : onRedo()),
  }), [commands, onUndo, onRedo]);

  // OpenChatCut's keyboard shortcuts (Delete, split, undo, nudge, select all…), bound the way its editor binds them
  const docRef = useRef<ProjectDoc>(live);
  docRef.current = live;
  const shortcutApiRef = useRef<TimelineShortcutApi | null>(null);
  useEditorActions({
    commands: wrapped, docRef, fps: adapter.fps, projectId: `vt-${projectId}`, timelineRef: shortcutApiRef,
    openExport: () => {}, openDesign: () => {}, openHistory: () => {}, openShortcuts: () => {}, toggleLayout: () => {},
    focusAgent: () => {},
    selectAll: () => commands.selectAll(),
  }, { enabled: !disabled });
  useEffect(() => {
    const select = (event: Event) => {
      const item = (event as CustomEvent<string>).detail;
      if (typeof item === 'string') commands.selectItem(item);
    };
    window.addEventListener('vt-occ-select-item', select);
    return () => window.removeEventListener('vt-occ-select-item', select);
  }, [commands]);

  // save a finished edit: not while the pointer is down (a drag in progress), and only what changed in our project
  const pointerDown = useRef(false);
  useEffect(() => {
    const down = () => { pointerDown.current = true; };
    const up = () => { pointerDown.current = false; };
    window.addEventListener('pointerdown', down, true);
    window.addEventListener('pointerup', up, true);
    window.addEventListener('pointercancel', up, true);
    return () => { window.removeEventListener('pointerdown', down, true); window.removeEventListener('pointerup', up, true); window.removeEventListener('pointercancel', up, true); };
  }, []);
  const saving = useRef(false);
  useEffect(() => {
    if (disabled || !dirty || saving.current) return;
    const timer = setInterval(() => {
      if (pointerDown.current || saving.current) return;
      clearInterval(timer);
      const plan = planSave(activeEditorState(base), activeEditorState(docRef.current), adapter.fps, layers);
      if (!plan.ops.length) {
        if (plan.ignored.length) setStatus({ kind: 'ignored', what: plan.ignored });
        return;
      }
      saving.current = true;
      setStatus({ kind: 'saving' });
      onSave(plan.ops)
        .then(() => setStatus(plan.ignored.length ? { kind: 'ignored', what: plan.ignored } : { kind: 'saved' }))
        .catch((e: unknown) => setStatus({ kind: 'error', message: e instanceof Error ? e.message : String(e) }))
        .finally(() => { saving.current = false; });
    }, SAVE_AFTER_MS);
    return () => clearInterval(timer);
  }, [live, disabled]); // eslint-disable-line react-hooks/exhaustive-deps

  // double-click on a narration clip: the time under the pointer (the narration is the cut voice, so clip time is video time)
  const wordAt = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest<HTMLElement>('[data-item-id]');
    if (el?.dataset.itemId?.startsWith('cut:')) { onRestoreCut?.(Number(el.dataset.itemId.slice(4))); return; }
    if (!onWordAt) return;
    const cue = (e.target as HTMLElement).closest<HTMLElement>('.cc-caption-track-cue');          // a caption line or word: the word under the pointer
    if (cue && cue.dataset.startMs) {
      const r = cue.getBoundingClientRect(), a0 = Number(cue.dataset.startMs), a1 = Number(cue.dataset.endMs);
      onWordAt((a0 + Math.max(0, Math.min(1, (e.clientX - r.left) / Math.max(1, r.width))) * (a1 - a0)) / 1000);
      return;
    }
    const s = activeEditorState(docRef.current);
    const voiceTrack = s.items.find((i) => i.id === VOICE_ID)?.track ?? activeEditorState(base).items.find((i) => i.id === VOICE_ID)?.track;
    const item = el && s.items.find((i) => i.id === el.dataset.itemId);
    if (!el || !item || item.track !== voiceTrack) return;
    const r = el.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - r.left) / Math.max(1, r.width)));
    onWordAt((item.startFrame + frac * item.durationInFrames) / adapter.fps);
  };
  return <div className="occ-board" onDoubleClick={wordAt}><Timeline state={state} commands={wrapped} playerRef={playerRef} projectId={`vt-${projectId}`} shortcutApiRef={shortcutApiRef} /></div>;
}
