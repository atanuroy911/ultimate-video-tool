"""Runs the stages for a project. Every stage hashes its inputs, so re-running only redoes what changed."""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Optional

from . import layout_check, paths
from .compose import FORMATS, compose_project, to_srt
from .compose.composer import AI_PLANNERS
from .planner import plan_rules
from .planner.catalogue import all_icon_names
from .project import Project, load_theme
from .schema import Beats, Cuts, ProjectMeta, ScenesFile, Transcript, validate_scenes
from .stages import audio as A
from .stages.align import snap_words
from .stages.chunks import plan_chunks
from .stages import words as W
from .util import Cancelled, ProgressFn, file_hash, noop_progress, now_iso, read_json, write_json

log = logging.getLogger(__name__)
REEL_HOLD_S = 3.0                     # the three-second rule: something changes on screen at least this often (longer videos breathe: x1.6, see vt/reel/slots.py)
AUTO_LANGUAGES = ["bn", "en"]          # what "auto" chooses between: the two languages the whole app (speech, captions, voices) is built for
LEAD_IN_MAX, LEAD_IN_KEEP = 3.0, 0.6       # seconds of non-speech allowed before the first word, and how much of it is kept
# what each stage usually takes on a first run, in seconds: the pace of the bar while a stage has nothing to report (Pipeline._tick_progress)
STAGE_SECONDS = {"voice": 60, "preprocess": 6, "silence": 3, "asr": 120, "cuts": 4, "sounds": 5, "aroll": 5, "words": 3, "context": 60, "tighten": 3, "plan": 120, "compose": 40}
ORDER = ["voice", "preprocess", "silence", "asr", "cuts", "sounds", "aroll", "words", "context", "tighten", "plan", "compose"]
LABELS = {
    "voice": "Speaking the script",
    "preprocess": "Cleaning audio",
    "silence": "Finding silences",
    "asr": "Transcribing",
    "cuts": "Cutting",
    "sounds": "Listening for sounds",
    "aroll": "Cutting the speaker's picture",
    "context": "Understanding the video",
    "tighten": "Tightening the story",
    "words": "Aligning words",
    "plan": "Planning scenes",
    "compose": "Composing",
}


class NoSpeechError(RuntimeError):
    """The recording contains no recognisable speech."""


class InvalidRecordingError(RuntimeError):
    """The source cannot be decoded; a person can replace or convert it."""


NO_SPEECH_MESSAGE = ("No speech was found in this recording. Check that the microphone is on and not too quiet, "
                     "or that you chose the right file, then try again.")


def tighten_signature(p: Project) -> str:
    """What the tighten stage decided to drop (source-time ranges), as text for the cuts stage's input hash. Not the file itself: tighten.json does not exist
    before the stage has run and exists, with nothing to drop, afterwards, which used to make the cuts stage redo its work on the second run."""
    drops = (read_json(p.dir / "tighten.json") or {}).get("cuts", [])
    return json.dumps([d.get("src") for d in drops], sort_keys=True)


class Pipeline:
    def __init__(self, project: Project, progress: ProgressFn = noop_progress):
        self.p = project
        self.progress = progress
        self.pause_reason: Optional[str] = None                      # set by a stage that must wait for the person (the plan review): the later stages do not run
        self._say_lock = threading.Lock()
        self._stage, self._frac, self._msg = "", 0.0, ""
        self._reported, self._reported_frac = time.time(), 0.0
        self._failed: dict[str, str] = {}                            # directors that did not finish this video, and why: the next one takes it (a plan is never left half made)

    def _say(self, stage: str, frac: float, msg: str = "") -> None:
        """A stage's progress never runs backward, whichever step inside it reports."""
        from .ai import talk

        with self._say_lock:
            if stage != self._stage:
                self._stage, self._frac, self._msg = stage, 0.0, ""
                talk.set_stage(stage)
            self._frac = max(self._frac, float(frac))
            self._msg = msg or self._msg
            self._reported = time.time()
            self._reported_frac = self._frac
            frac = self._frac
        self.progress(stage, frac, msg)

    def _tick_progress(self, stop: threading.Event) -> None:
        """While a stage works with nothing to report (a model reading, a file being cut) the bar keeps moving toward what the stage usually takes.
        It slows as it nears the end and stays below it: only the stage itself says done."""
        while not stop.wait(1.0):
            with self._say_lock:
                stage, msg = self._stage, self._msg
                waited = time.time() - self._reported
                if not stage or self._frac >= 1.0:
                    continue
                base = self._reported_frac
                frac = max(self._frac, base + (0.95 - base) * (1 - math.exp(-waited / STAGE_SECONDS.get(stage, 30))))
                self._frac = frac
            try:
                self.progress(stage, frac, msg)
            except (Cancelled, Exception):  # noqa: BLE001 — the heartbeat thread: the stage itself stops at its next report
                return

    def director(self) -> str:
        """The one who directs this video: what the person chose, or the first available in their order when they left it on Best."""
        from . import directors

        requested = self.p.meta().options.director or "best"
        available = {d["id"]: d for d in directors.listing()["directors"]}
        return next((d for d in directors.candidates(requested) if available.get(d, {}).get("available") and d not in self._failed), "local")

    @staticmethod
    def _why_not_requested(requested: str, chosen: str, available: dict) -> str:
        """Empty, unless the person picked a director who could not take the video: then one plain line saying so and who directed it instead."""
        if requested in ("", "best", chosen):
            return ""
        asked = available.get(requested) or {}
        note = str(asked.get("note") or "").strip().rstrip(".")
        instead = (available.get(chosen) or {}).get("label") or chosen
        return f"{asked.get('label') or requested} was not available{' (' + note + ')' if note else ''}, so {instead} directed this video."

    def _director_provider(self, chosen: str):
        """Every AI step of the video (understanding it, directing the voice, planning) asks this one, so one mind directs the whole video."""
        from .ai import providers as AIP

        return AIP.provider_for(chosen)

    # ------------------------------------------------------------------ driver
    def run(self, from_stage: Optional[str] = None, to_stage: Optional[str] = None, force: bool = False) -> None:
        from .modules.recipes import load_classic, run_classic

        stages = load_classic() if self.p.script_path.exists() else [x for x in load_classic() if x != "voice"]
        if from_stage == "voice" and not self.p.script_path.exists():
            from_stage = "preprocess"
        if from_stage:
            if from_stage not in ORDER:
                raise ValueError(f"unknown stage '{from_stage}', choose from {ORDER}")
            stages = [x for x in stages if ORDER.index(x) >= ORDER.index(from_stage)]
            force = True
        if to_stage:
            stages = [x for x in stages if ORDER.index(x) <= ORDER.index(to_stage)]
        from . import gpu

        gpu.prepare()                          # one set of CUDA libraries (torch's) before any stage loads a GPU library in its own order
        from .ai import providers as AIP, talk

        self.p.update_meta(status="processing")
        provider = self._director_provider(self.director())
        stop = threading.Event()
        threading.Thread(target=self._tick_progress, args=(stop,), daemon=True).start()
        try:
            with talk.for_project(self.p.dir), (AIP.use_provider(provider) if provider is not None else nullcontext()):
                run_classic(self, stages, force=force)
            self.p.update_meta(status="review" if self.pause_reason == "plan" else "planned")
        except Cancelled:
            self.p.update_meta(status="cancelled")
            raise
        except Exception:                        # noqa: BLE001 — marks the project and raises again
            self.p.update_meta(status="error")   # the job keeps the failing stage as its current stage, so the UI can mark it
            raise
        finally:
            stop.set()

    def _fresh(self, name: str, h: str, force: bool, *outputs: Path) -> bool:
        return (not force) and self.p.stage_done(name, h) and all(o.exists() for o in outputs)

    # ------------------------------------------------------------------ stages
    def stage_voice(self, force: bool = False) -> None:
        """Script projects only: speak the text. Records exact sentence/word times so no speech recognition is needed."""
        from . import tts

        p = self.p
        spec = read_json(p.script_path) or {}
        meta = p.meta()
        directing = meta.options.voice_direction
        engine, voice = spec.get("engine", "edge"), spec.get("voice", "bn-BD-NabanitaNeural")
        language = meta.language if meta.language in ("en", "bn", "zh", "hi") else "en"
        can_direct = tts.dialect_for(engine, voice, language, True) != "none"
        tag = f"tts-v2|direction={directing}" if can_direct else "tts-v1"      # a voice that cannot follow direction keeps the old key: nothing already made is spoken again
        if tts.VL.reseeds(engine):
            tag += "|one-voice-v1"                                             # these engines are now cast once and checked (vt/voice_lock.py): speak them again once
        h = file_hash(p.script_path, extra=tag) if p.script_path.exists() else ""
        if self._fresh("voice", h, force, p.input_audio) and spec.get("sentences"):
            return
        notes = None
        if directing == "auto":                                       # the director's delivery notes, only for a voice that can follow them
            from . import voice_direction as VD

            if can_direct:
                self._say("voice", 0.01, "Directing the delivery")
                plain = [VD.strip(s["text"]) for s in tts.split_script(spec.get("text", ""))]
                notes = VD.suggest(plain, language, events=tuple(VD.DIALECTS[tts.dialect_for(engine, voice, language, True)]["events"]))
        res = tts.synthesize(spec.get("text", ""), p.input_audio, engine=engine, voice=voice, rate=float(spec.get("rate", 1.0)), direction=directing != "off", notes=notes,
                             language=meta.language, progress=lambda s, f, m: self._say("voice", f, m))
        spec.update({"duration": res["duration"], "sentences": res["sentences"], "steadiness": res.get("steadiness")})
        write_json(p.script_path, spec)
        st = res.get("steadiness") or {}
        p.mark_stage("voice", file_hash(p.script_path, extra=tag), seconds=res["duration"], engine=res["engine"],
                     respoken=len(st.get("respoken", [])), still_off=len(st.get("still_off", [])))

    def stage_preprocess(self, force: bool = False) -> None:
        p = self.p
        denoise = not p.script_path.exists() and p.meta().options.recording_edit == 'auto'
        h = file_hash(p.input_audio, extra=f"denoise={int(denoise)}")
        if self._fresh("preprocess", h, force, p.master, p.asr_wav):
            return
        if not p.input_audio.exists():
            raise FileNotFoundError(f"no input audio in {p.dir}")
        try:
            A.preprocess(p.input_audio, p.master, p.asr_wav, denoise=denoise)
        except RuntimeError as e:
            # Decode failures need a useful next step. Tool, storage and other infrastructure failures keep their actual reason.
            if any(marker in str(e).lower() for marker in ("invalid data found when processing input", "moov atom not found",
                                                           "does not contain any stream", "matches no streams", "error while decoding",
                                                           "could not find codec parameters")):
                raise InvalidRecordingError("This recording could not be read. It may be damaged, have no audio, or use an unsupported format. "
                                            "Try playing the original file, then export it as WAV or MP4 and choose it again.") from e
            raise
        p.mark_stage("preprocess", h)

    def stage_silence(self, force: bool = False) -> None:
        p = self.p
        meta = p.meta()
        h = file_hash(p.asr_wav, extra=f"pace={meta.pace}")
        sp = p.dir / "cuts.silence.json"
        if self._fresh("silence", h, force, sp):
            return
        cfg = A.PACE[meta.pace]
        silences, dur, thr = A.find_silences(p.asr_wav, cfg["min_silence"])
        cuts = A.silence_cuts(dur, silences, meta.pace)
        write_json(sp, {"cuts": cuts.model_dump(), "threshold_db": round(thr, 1), "silences": silences})
        p.mark_stage("silence", h, threshold_db=round(thr, 1), kept=round(cuts.output_duration, 2), source=round(dur, 2))

    def stage_asr(self, force: bool = False) -> None:
        p = self.p
        meta = p.meta()
        from .stages import asr as asr_mod

        script = read_json(p.script_path) if p.script_path.exists() else None
        if script and script.get("sentences"):
            # the words are already known (typed) and timed by the voice stage: no recognition needed
            from . import tts

            h = file_hash(p.script_path, p.asr_wav, extra="script-transcript-refit")
            if self._fresh("asr", h, force, p.raw_transcript_path):
                return
            raw = tts.raw_transcript(script, meta.language)
            from .stages.align import fit_script_words                   # the voice's word times drift: put every typed word back on the speech
            thr = (read_json(p.dir / "cuts.silence.json") or {}).get("threshold_db")
            silences, _dur, _, _ = A.find_silences(p.asr_wav, 0.2, thr, return_db=True)
            raw["words"], raw["refit"] = fit_script_words(raw["words"], silences)
            write_json(p.raw_transcript_path, raw)
            p.mark_stage("asr", h, words=len(raw["words"]), model=raw["model"], dropped=0)
            return
        subs = p.dir / "subs.raw.json"
        if subs.exists() and meta.options.use_subtitles != "off":
            # imported from a link whose page has subtitles: their words and timing replace speech recognition
            h = file_hash(subs, p.asr_wav, extra="subtitles")
            if self._fresh("asr", h, force, p.raw_transcript_path):
                return
            raw = read_json(subs)
            dropped = 0
            if not raw.get("exact"):                                     # the person's own subtitle file is followed as written (ingest.attach_subtitles)
                silences, dur, _, _ = A.find_silences(p.asr_wav, 0.2, (read_json(p.dir / "cuts.silence.json") or {}).get("threshold_db"), return_db=True)
                words, dropped = snap_words(raw["words"], silences, dur)
                raw["words"] = words or raw["words"]
                raw["snap_dropped"] = dropped
            write_json(p.raw_transcript_path, raw)
            p.mark_stage("asr", h, words=len(raw["words"]), model=raw.get("model") or "subtitles", dropped=dropped)
            return
        if meta.language == "auto":
            meta = self._detect_language()
        model = asr_mod.model_for_language(meta.options.asr_model, meta.language)
        h = file_hash(p.asr_wav, extra=f"{model}|{meta.language}|v4-junk")
        if self._fresh("asr", h, force, p.raw_transcript_path):
            return
        from .stages import asr

        # cut at real pauses into short chunks (the Bangla model loses words on long windows), transcribe each separately
        thr = (read_json(p.dir / "cuts.silence.json") or {}).get("threshold_db")
        silences, dur, _, db = A.find_silences(p.asr_wav, 0.2, thr, return_db=True)
        chunks = plan_chunks(dur, silences, db)
        res = asr.transcribe(p.asr_wav, model=model, language=meta.language, chunks=chunks,
                             progress=lambda s, f, m: self._say("asr", f, m))
        # snap word boundaries to the real speech and drop words "heard" inside silence (trailing hallucinations)
        res["words"], dropped = snap_words(res["words"], silences, dur)
        spoken = sum(max(0.0, w["end"] - w["start"]) for w in res["words"])
        if len(res["words"]) <= 3 and spoken < 0.1 * dur and self._captions_from_sounds(h):          # one stray "you" in a recording of laughter and rain is not speech
            return
        if not res["words"]:
            fallback = self._captions_from_sounds(h)               # a recording of laughter, rain or music: caption the sounds instead of failing
            if fallback is None:
                raise NoSpeechError(NO_SPEECH_MESSAGE)
            return
        res["snap_dropped"] = dropped
        write_json(p.raw_transcript_path, res)
        p.mark_stage("asr", h, words=len(res["words"]), model=model, dropped=dropped)

    def _detect_language(self) -> ProjectMeta:
        """language "auto": the person only spoke; the speech model decides between Bangla and English (Banglish counts as Bangla) and the project remembers it."""
        from . import langdetect

        self._say("asr", 0.01, "Working out the language")
        try:
            lang, _ = langdetect.from_audio(self.p.asr_wav, allowed=AUTO_LANGUAGES)
        except Exception as e:                                     # noqa: BLE001 — match the English-first creation defaults when detection is unavailable
            from .notices import record as record_notice
            record_notice(self.p, "asr", "The language could not be detected, so English was used. Change it in the video's settings if that is wrong.", e)
            lang = "en"
        self._say("asr", 0.03, f"Language: {langdetect.NAMES.get(lang, lang)}")
        return self.p.update_meta(language=lang)

    def _captions_from_sounds(self, h: str) -> Optional[bool]:
        p = self.p
        if p.meta().options.sound_events == "off":
            return None
        from . import sounds as SN

        if not SN.available():
            return None
        import soundfile as sf

        self._say("asr", 0.9, "No speech: listening for sounds")
        x, sr = sf.read(str(p.asr_wav), dtype="float32", always_2d=False)
        events = [e for e in SN.analyze_array(x, sr) if e["concept"] not in ("silence",)]
        words = SN.caption_words(events)
        if not words:
            return None
        write_json(p.raw_transcript_path, {"language": p.meta().language, "model": "sounds", "words": words, "snap_dropped": 0})
        p.mark_stage("asr", h, words=len(words), model="sounds", dropped=0)
        return True

    def stage_aroll(self, force: bool = False) -> None:
        """A video that was imported keeps the speaker's picture, cut like the voice (vt/aroll.py). Never stops the video: without it the video is made from graphics as before."""
        p = self.p
        from . import aroll as AR

        if p.meta().options.aroll == "off" or p.script_path.exists() or not p.cuts_path.exists():
            AR.remove(p) if p.meta().options.aroll == "off" else None
            return
        try:
            AR.build(p, lambda f, m: self._say("aroll", f, m), force=force)
            (p.dir / "aroll.error.json").unlink(missing_ok=True)          # an earlier failure is no longer true
        except Exception as e:                                     # noqa: BLE001 — the video is made without the speaker's picture
            write_json(p.dir / "aroll.error.json", {"at": now_iso(), "error": f"{type(e).__name__}: {str(e)[:200]}"})
            from .notices import record as record_notice
            record_notice(p, "aroll", "The speaker's own picture could not be prepared, so this video does not show the recording.", e)

    def stage_sounds(self, force: bool = False) -> None:
        """Find laughter, applause, music, animals ... in the voice track (output time). Never stops the video: a failure is recorded and the stage is skipped."""
        p = self.p
        from . import sounds as SN

        if p.meta().options.sound_events == "off" or not SN.available() or not p.cut_audio.exists():
            return
        try:
            SN.analyze_project(p, lambda f: self._say("sounds", f, "listening"), force=force)
        except Exception as e:                                     # noqa: BLE001 — sounds are an extra
            write_json(SN.path(p), {"hash": "", "model": SN.MODEL, "duration": 0, "events": [], "error": f"{type(e).__name__}: {str(e)[:160]}"})
            from .notices import record as record_notice
            record_notice(p, "sounds", "Listening for sounds (laughter, applause, music) was skipped.", e)

    def stage_cuts(self, force: bool = False) -> None:
        p = self.p
        meta = p.meta()
        sil = read_json(p.dir / "cuts.silence.json")
        protected = meta.options.recording_edit != 'auto'
        h = file_hash(p.dir / "cuts.silence.json", p.raw_transcript_path, p.dir / "audio_edits.json", extra=f"fillers={meta.options.remove_fillers}|retakes={meta.options.remove_retakes}|rt-v3|{tighten_signature(p)}|recording={meta.options.recording_edit}")
        if self._fresh("cuts", h, force, p.cuts_path, p.cut_audio):
            return
        from . import audio_edit as AE

        edits = AE.load(p)                                           # the user's own cuts, mutes and volume changes
        if not protected and sil and sil.get("cuts"):
            base = Cuts.model_validate(sil["cuts"])
        else:                                                        # no silence stage ran (a hand-built or imported project): keep the whole recording and apply only the edits
            import soundfile as sf

            total = float(sf.info(str(p.master)).duration)
            base = Cuts(source_duration=total, keep=[(0.0, total)])
        removed = A.removed_from_cuts(base) + [(a, b) for a, b in edits["cuts"]]
        raw = read_json(p.raw_transcript_path) or {"words": []}
        first = min((w["start"] for w in raw.get("words", [])), default=0.0)
        if not protected and first > LEAD_IN_MAX:                    # a tutorial's silent pointer demonstrations are intentional
            removed.append((0.0, first - LEAD_IN_KEEP))
        if not protected and meta.options.remove_fillers:
            for i in sorted(W.find_fillers(raw["words"])):
                w = raw["words"][i]
                removed.append((max(0.0, w["start"] - 0.02), w["end"] + 0.04))
        retakes = []
        if not protected and meta.options.remove_retakes and not p.script_path.exists():
            from .retakes import find_retakes

            retakes = find_retakes(raw.get("words", []))
            for r in retakes:
                removed.append((max(0.0, r["start"] - 0.03), r["end"] + 0.05))
        for d in ((read_json(p.dir / "tighten.json") or {}).get("cuts", []) if not protected else []):
            removed.extend((a, b) for a, b in d.get("src", []))
        write_json(p.dir / "retakes.json", {"cuts": [{k: v for k, v in r.items() if k != "words"} for r in retakes]})   # shown as "what the editor cut"
        cuts = A.cuts_from_removed(base.source_duration, removed)
        write_json(p.cuts_path, cuts.model_dump())
        dur = A.apply_cuts(p.master, cuts, p.cut_audio)
        AE.apply_to_cut_audio(p.cut_audio, cuts, edits)
        p.ensure_preview_audio()
        p.mark_stage("cuts", h, output_seconds=round(dur, 2), retakes=len(retakes))

    def stage_words(self, force: bool = False, preserve_structure: bool = False) -> None:
        p = self.p
        meta = p.meta()
        edits_path = p.dir / "edits.json"
        gloss = p.glossary()
        h = file_hash(p.raw_transcript_path, p.cuts_path, edits_path, p.dir / "speakers.json", extra=f"{sorted(gloss.items())}|{meta.options.script_policy}|{meta.options.speakers}" + (f"|hold{REEL_HOLD_S}" if meta.options.look == "reel" else ""))
        if self._fresh("words", h, force, p.transcript_path, p.beats_path):
            return
        raw = read_json(p.raw_transcript_path)
        cuts = p.cuts()
        edits = (read_json(edits_path, {}) or {}).get("words", {})
        tr = W.build_transcript(raw, cuts, gloss, meta.language, edits, meta.options.script_policy)
        hold = None if meta.options.look != "reel" else REEL_HOLD_S * (1.6 if tr.words and tr.words[-1].end > 180 else 1.0)          # a picture never holds longer than this: the three-second rule, kept at the sentence stage
        beats = W.build_beats(tr, max_seconds=hold)
        if meta.options.speakers == "auto" and meta.source != "script" and p.cut_audio.exists() and not any(w.speaker for w in tr.words):
            from .stages import speakers as SP
            from .visuals.emphasis import load_mono16k

            try:
                who = SP.assign(load_mono16k(p.cut_audio), tr, beats)
            except Exception as e:                             # noqa: BLE001 — a guess must never stop a video from being made
                from .notices import record as record_notice
                record_notice(p, "words", "Who speaks when could not be worked out, so every word is given to one speaker.", e)
                who = None
            if who:
                names = (read_json(p.dir / "speakers.json", {}) or {}).get("names", {})
                tr = SP.label_words(tr, beats, {b: names.get(n, n) for b, n in who.items()})
                beats = W.build_beats(tr, max_seconds=hold)    # sentences now also break where the speaker changes
        if preserve_structure and p.beats_path.exists():
            # Re-voicing is a caption/audio edit, not a request to regroup scenes.
            # Keep sentence IDs, visual anchors and exact scene boundaries.
            words_by_id = tr.by_id()
            beats = p.beats().model_copy(update={"beats": [b.model_copy(update={
                "text": " ".join(words_by_id[wid].text for wid in b.word_ids
                                 if wid in words_by_id and not words_by_id[wid].cut)
            }) for b in p.beats().beats]})
        p.save_transcript(tr)
        old = read_json(p.beats_path)
        if old and old != beats.model_dump():
            write_json(p.dir / "beats.prev.json", old)   # lets stage_plan remap scenes onto the new sentences
        write_json(p.beats_path, beats.model_dump())
        p.mark_stage("words", h, words=len(tr.words), beats=len(beats.beats))

    def stage_tighten(self, force: bool = False) -> None:
        """Bring a long vertical video down to the length the platforms reward by dropping the sentences the story can live without (vt/tighten.py).
        The choice is made once per recording and setting (kept in tighten.json with its own hash), so re-running stages never tightens twice."""
        from . import audio_edit as AE
        from . import context as CX
        from . import tighten as TG

        p = self.p
        meta = p.meta()
        if meta.options.recording_edit != 'auto':return
        tp = p.dir / "tighten.json"
        h = file_hash(p.raw_transcript_path, extra=f"{meta.options.target_length}|{meta.aspect}|tg-v2")
        prev = read_json(tp) or {}
        if prev.get("hash") == h:
            return
        if prev.get("cuts"):                                     # the setting changed: put everything back first, then choose again on the whole talk
            write_json(tp, {"hash": "", "cuts": []})
            self._recut()
        drops: list[dict] = []
        cuts0 = p.cuts()                                         # none for a hand-built project: nothing to tighten
        target = None if p.script_path.exists() or cuts0 is None else TG.target_seconds(meta.options.target_length, meta.aspect, cuts0.output_duration)
        if target:
            ctx = read_json(CX.path(p)) or {}
            beats = p.beats().beats
            sents = {x["beat"]: x for x in ctx.get("sentences", [])}
            drops = TG.choose([b.model_dump() for b in beats], sents, target, narrative=TG.is_narrative(ctx.get("mood"), sents, [b.text for b in beats]))
            by, cuts = {b.id: b for b in beats}, p.cuts()
            for d in drops:
                d["src"] = AE.src_ranges(cuts, by[d["beat"]].start, by[d["beat"]].end)
        write_json(tp, {"hash": h, "target": target, "cuts": drops})
        if drops:
            self._say("tighten", 0.5, f"Dropped {len(drops)} sentence(s) to reach about {int(target)} s")
            self._recut()
        p.mark_stage("tighten", h, dropped=len(drops), target=target)

    def _recut(self) -> None:
        for name in ORDER[ORDER.index("cuts"):ORDER.index("context") + 1]:
            getattr(self, f"stage_{name}")(True)

    def stage_context(self, force: bool = False) -> None:
        """One shared reading of the video (vt/context.py): topic, named things, sentence ideas, sections, facts. Rules always; the AI improves it when it is available. Never stops the video."""
        from . import context as CX
        from .ai import providers as AIP
        from .util import file_hash

        p = self.p
        meta = p.meta()
        use_ai = AIP.ai_enabled()
        ov = read_json(CX.overrides_path(p), None)
        h = file_hash(p.transcript_path, p.beats_path, CX.overrides_path(p), extra=f"ctx-v1|ai={AIP.fingerprint()}")
        if self._fresh("context", h, force, CX.path(p)):
            return
        try:
            if use_ai:
                self._say("context", 0.05, "Preparing the AI")
                try:
                    AIP.ensure_ai(lambda s_, f, m: self._say("context", 0.05 + 0.25 * f, m))
                except Exception as e:                         # noqa: BLE001 — the rules can still work out the topic
                    from .notices import record as record_notice
                    record_notice(p, "context", "The AI could not be prepared, so what the video is about was worked out by rules.", e)
                    use_ai = False
            ctx = CX.build(p.transcript(), p.beats(), meta.language, use_ai=use_ai, overrides=ov)
            ctx.hash = CX.current_hash(p)
            CX.save(p, ctx)
            p.mark_stage("context", h, source=ctx.source, entities=len(ctx.entities), sections=len(ctx.sections))
        except Exception as e:                                     # noqa: BLE001 — the plan can be made without the context
            from .notices import record as record_notice
            record_notice(p, "context", "What the video is about could not be worked out, so scenes are planned from the words alone.", e)
            write_json(CX.path(p), {"version": 1, "source": "failed", "notes": [f"{type(e).__name__}: {str(e)[:160]}"]})

    def _reel_plan_for_making(self, force: bool):
        """The plan to make from, or None when the person must look at it first. An approved plan is used as it is; otherwise a draft is made (no picture, no GPU) and shown
        when the setting says so (`plan_review`, per video `options.plan_review`); the rest are approved at once and kept, so 'How this was made' has them either way."""
        from .direction import plan_doc as PD

        from . import directors

        p = self.p
        meta = p.meta()
        plan = PD.load(p.dir)
        ids = [b.id for b in p.beats().beats]
        if plan is None or not PD.matches(plan, ids) or plan.state in ("declined", "done"):
            if plan is not None and plan.state == "done" and not force and PD.matches(plan, ids):
                return plan
            requested = meta.options.director or "best"
            fallback_reason = ""
            plan = None
            available = {d["id"]: d for d in directors.listing()["directors"]}
            for who in directors.candidates(requested):
                status = available.get(who, {"available": False})
                if who.startswith(("claude@", "codex@")) and status.get("available"):
                    plan = PD.build(p, use_ai=False)
                    PD.save(p.dir, plan)
                    self._say("plan", 0.1, f"Waiting for {status.get('label', 'Claude on this PC')}")
                    result = directors.broker.request(who.split("@", 1)[1], p.id, directors.client_prompt(p.id),
                                                      directors.direct_timeout(), assistant=who.split('@',1)[0])
                    plan = PD.load(p.dir) or plan
                    if result.get("ok") and plan.state in ("approved", "running"):
                        directors.record(p, who, requested=requested, fallback_reason=fallback_reason)
                        break
                    fallback_reason = result.get("reason") or result.get("error") or "The client director did not complete the plan."
                    self._say("plan", 0.12, f"{fallback_reason} Falling back.")
                    plan = None
                    (p.dir / PD.PLAN).unlink(missing_ok=True)
                    (p.dir / "reel_reading.json").unlink(missing_ok=True)
                    continue
                if who == "claude-server" and status.get("available"):
                    from .ai.providers import ClaudeCLIProvider

                    try:
                        plan = PD.build(p, provider=ClaudeCLIProvider())
                        directors.record(p, who, requested=requested, fallback_reason=fallback_reason)
                        break
                    except Exception as e:  # noqa: BLE001 — a CLI that disappears or loses login must not stop the video (the reason is recorded by directors.record)
                        fallback_reason = f"Claude on the server failed ({type(e).__name__}: {str(e)[:120]})."
                        self._say("plan", 0.12, f"{fallback_reason} Falling back.")
                        (p.dir / PD.PLAN).unlink(missing_ok=True)
                        (p.dir / "reel_reading.json").unlink(missing_ok=True)
                        plan = None
                        continue
                if who == "local" and status.get("available"):
                    try:
                        from .ai.providers import OllamaProvider

                        plan = PD.build(p, provider=OllamaProvider())
                        directors.record(p, who, requested=requested, fallback_reason=fallback_reason)
                        break
                    except Exception as e:  # noqa: BLE001 — the rules below are the engine-free final fallback (the reason is recorded)
                        fallback_reason = f"The local AI failed ({type(e).__name__}: {str(e)[:120]})."
                        (p.dir / PD.PLAN).unlink(missing_ok=True)
                        (p.dir / "reel_reading.json").unlink(missing_ok=True)
                        plan = None
                        continue
                fallback_reason = fallback_reason or str(status.get("note") or f"{who} is unavailable.")
            if plan is None:  # the rule director is the final, engine-free safety net
                plan = PD.build(p, use_ai=False)
                directors.record(p, "rules", requested=requested, fallback_reason=fallback_reason)
        if plan.state == "draft":
            setting = str((read_json(paths.SETTINGS, {}) or {}).get("plan_review", "when_expensive"))
            if PD.review_wanted(plan, setting, p.meta().options.plan_review):
                return None
            plan.state, plan.approved_by, plan.approved_at = "approved", "automatic", now_iso()
        plan.state = "running"
        PD.save(p.dir, plan)
        return plan

    def _plan_story(self, meta) -> None:
        """Cartoon 2: the rule draft, then the chosen director. An AI on the server redesigns it scene by scene; a director on the person's
        computer gets the draft as a task (get_story_task / submit_story) and submits the whole story. Whoever answered is recorded."""
        from contextlib import nullcontext

        from . import directors
        from .ai import providers as AIP
        from .story import service as ST

        p = self.p
        requested = meta.options.director or "best"
        available = {d["id"]: d for d in directors.listing()["directors"]}
        chosen = next((d for d in directors.candidates(requested) if available.get(d, {}).get("available")), "local")
        provider = None
        if chosen == "claude-server":
            provider = AIP.ClaudeCLIProvider()
        elif chosen == "local" and AIP.ai_enabled():
            provider = AIP.OllamaProvider()
        elif not chosen.startswith(("claude@", "codex@")) and AIP.ai_enabled():
            provider = AIP.current_provider()
        self._say("plan", 0.05, "Drawing the story")
        with (AIP.use_provider(provider) if provider is not None else nullcontext()):
            sf, how, notice = ST.plan_story(p, provider=provider, progress=lambda f, m: self._say("plan", 0.1 + 0.8 * f, m))
        p.save_scenes(sf)
        actual = "rules" if how == "rules" else chosen
        if chosen.startswith(("claude@", "codex@")):
            self._say("plan", 0.92, f"Waiting for {available[chosen].get('label', 'the director on your computer')}")
            result = directors.broker.request(chosen.split("@", 1)[1], p.id, directors.client_story_prompt(p.id), directors.direct_timeout(),
                                              assistant=chosen.split("@", 1)[0])
            outside = p.scenes()
            if result.get("ok") and outside is not None and outside.planner in ("claude", "assistant"):
                directors.record(p, chosen, requested=requested)
            else:
                reason = result.get("reason") or result.get("error") or "The director on your computer did not submit a story."
                directors.record(p, actual, requested=requested, fallback_reason=reason)
                notice = notice or reason
        else:
            directors.record(p, actual, requested=requested, fallback_reason=notice if actual == "rules" else "")
        write_json(p.dir / "ai_notice.json", {"at": now_iso(), "message": notice}) if notice else (p.dir / "ai_notice.json").unlink(missing_ok=True)
        (p.dir / "plan_notice.json").unlink(missing_ok=True)
        write_json(p.dir / "plan_basis.json", self._word_basis())
        p.mark_stage("plan", "story", scenes=len(sf.scenes), usecase="story")

    def stage_plan(self, force: bool = False) -> None:
        """Keep an existing plan (user edits / Claude), remapped if sentences moved; draft with rules only as a last resort."""
        p = self.p
        meta = p.meta()
        if meta.options.music == "auto":                        # the track that suits what the video is about (vt/musicpick.py)
            from . import context as CX
            from .musicpick import pick

            ctx = CX.load(p)
            meta.options.music = pick(ctx.mood if ctx else None, p.id)
            p.save_meta(meta)
        if meta.options.recording_edit != 'auto' and not p.scenes():
            from .screen_recording import base_plan, supporting_graphics
            if meta.theme == 'auto':                          # this path never designs a look: a recording keeps its own picture, so only the captions need one, and a quiet one
                meta = p.update_meta(theme='minimal')
            recording_plan=base_plan(p)
            if meta.options.recording_edit=='screen':
                try:recording_plan=supporting_graphics(p,recording_plan)
                except Exception as error:                     # noqa: BLE001 — said in ai_notice.json
                    write_json(p.dir/'ai_notice.json',{'at':now_iso(),'message':f'The supporting graphics could not be planned. Your original screen and captions were kept. {type(error).__name__}'})
            p.save_scenes(recording_plan)
            write_json(p.dir / 'plan_basis.json',self._word_basis())
            p.mark_stage('plan','protected-recording',scenes=1)
            return
        tr, beats = p.transcript(), p.beats()
        icons = all_icon_names()
        existing = p.scenes()
        stale = existing is not None and self._plan_is_stale(existing)
        if existing and stale:                                    # recognition ran again and the word ids now point at other words
            write_json(p.dir / "scenes.invalid.json", existing.model_dump(exclude_none=True))
            write_json(p.dir / "plan_notice.json", {
                "at": now_iso(), "planner": existing.planner,
                "message": "The speech was recognised again and the words moved, so the previous scene plan would show pictures at the wrong "
                           "moments. A fresh plan was made; the previous one is saved as scenes.invalid.json."})
            for f in ("video_script.json", "director.json"):
                (p.dir / f).unlink(missing_ok=True)
            existing = None
        if existing and (not force or existing.planner in ("claude", "manual")):
            old_beats = read_json(p.dir / "beats.prev.json")
            repaired = repair_scenes(existing, tr, beats, icons, Beats.model_validate(old_beats) if old_beats else None)
            if repaired is not None:
                if repaired != existing:
                    p.save_scenes(repaired)
                if not (p.dir / "plan_basis.json").exists():      # a plan from before the check: from now on it is tied to these words
                    write_json(p.dir / "plan_basis.json", self._word_basis())
                return
            write_json(p.dir / "scenes.invalid.json", existing.model_dump(exclude_none=True))
            write_json(p.dir / "plan_notice.json", {
                "at": now_iso(), "planner": existing.planner,
                "message": "The sentences changed so much that your previous scene plan no longer fits. A fresh automatic draft was made; "
                           "your previous plan is saved as scenes.invalid.json."})
        if meta.options.look == "reel":                              # one picture drawn for each stretch of speech (vt/reel/)
            from .direction import plan_doc as PD
            from .reel.plan import build_reel_plan

            plan = self._reel_plan_for_making(force)
            if plan is None:                                         # the person has to look at it first: stop here, nothing expensive has run
                self.pause_reason = "plan"
                self._say("plan", 1.0, "Your plan is ready to look at")
                return

            def moment_update(mid: str, info: dict) -> None:
                cur = PD.load(p.dir)
                if cur is not None:
                    m = next((x for x in cur.moments if x.id == mid), None)
                    if m is not None:
                        for k, v in info.items():
                            setattr(m, k, v)
                        PD.save(p.dir, cur)

            sf = build_reel_plan(p, progress=lambda f, m: self._say("plan", f, m), plan=plan, on_moment=moment_update)
            errs = validate_scenes(sf, tr, beats, icons)
            if errs:
                raise RuntimeError("the reel plan is invalid: " + "; ".join(errs[:5]))
            for stale_file in ("ai_notice.json", "plan_notice.json"):
                (p.dir / stale_file).unlink(missing_ok=True)
            fresh = p.meta()                                            # re-read: drawing the pictures added them to the media bin, and an older copy would erase them
            if fresh.options.motion == "auto":                          # a reel changes picture with a plain cut on the word, not with a flashy wipe
                fresh.options.motion = "cuts"
                p.save_meta(fresh)
            p.save_scenes(sf)
            write_json(p.dir / "plan_basis.json", self._word_basis())
            p.mark_stage("plan", "reel", scenes=len(sf.scenes), usecase="reel")
            done_plan = PD.load(p.dir)                                  # "done" only once the scenes are saved: a page that sees it may read them at once
            if done_plan is not None:
                done_plan.state = "done"
                PD.save(p.dir, done_plan)
            return
        if meta.options.look == "story":                             # Cartoon 2: the story engine (vt/story/)
            self._plan_story(meta)
            return
        audio = p.cut_audio if p.cut_audio.exists() else None
        sf, brief = None, None
        notice = None
        from . import directors, llm
        from .director import contrast as K
        from .director import plan as D
        from .director import profiles as PR
        from .director import roles as RL

        facts = RL.analyse(tr, beats, meta.language)
        usecase = meta.usecase if meta.usecase != "auto" else D.detect_usecase(facts, bool(meta.planner_media()))
        profile = PR.get(usecase)
        try:
            from .visuals.picker import pick_visuals

            picks = pick_visuals(tr, beats, audio)
        except Exception as e:                 # noqa: BLE001 — no dictionary/model: typography-only pictures
            from .notices import record as record_notice
            record_notice(p, "plan", "The picture dictionary could not be used, so scenes show words instead of pictures.", e)
            picks = {}

        def draw(brief_):
            meta2 = self._resolve_auto_theme(meta, tr, None, profile)
            scrim = lambda mid, aspect, layout, t0, t1: K.decide_for_media(p, mid, aspect, layout, t0, t1)   # noqa: E731
            base = D.plan(tr, beats, theme=meta2.theme, language=meta.language, usecase=usecase, picks=picks, media=meta.planner_media(),
                          seed=p.id, brief=brief_, aspect=meta.aspect, scrim_fn=scrim)
            return meta2, base

        from .ai import providers as AIP

        from .script import service as script_service

        requested = meta.options.director or "best"
        available = {d["id"]: d for d in directors.listing()["directors"]}
        chosen = self.director()
        unavailable = self._why_not_requested(requested, chosen, available)
        outside = chosen.startswith(("claude@", "codex@"))

        def after_failure(instead: str) -> str:                          # one that was asked first did not finish: one line saying why and who directed instead
            return f"{'; '.join(self._failed.values())}, so {instead} directed this video." if self._failed else ""
        scripted = script_service.uses_script(p, chosen)                # the AI writes the whole plan as a Video Script
        ai_directed = False                                              # True when an AI made this plan: the rule passes below do not rewrite its decisions
        retry = False
        # the local model's picture planner runs only when it is this video's director and no script will replace its work
        if chosen == "local" and not scripted and AIP.ai_enabled():
            try:
                self._say("plan", 0.02, "Preparing the local AI")
                llm.ensure_ready(lambda s_, f, m: self._say("plan", 0.02 + 0.2 * f, m))
                from .planner.llm_plan import plan_llm, story_brief
                from . import context as CX

                have = CX.load(p)
                brief = have.to_brief() if (have and have.source == "ai" and have.topic) else story_brief(tr, meta.language)          # the context already says what the video is about: no second AI call
                meta, base = draw(brief)
                sf = plan_llm(tr, beats, meta.theme, meta.language, audio, lambda f, m: self._say("plan", 0.25 + 0.7 * f, m), brief, base=base, picks=picks)
            except llm.LLMUnavailable as e:
                notice = str(e)
        local_planned = sf is not None
        if sf is None:
            meta, sf = draw(brief)
        try:
            how, actual = "plan", chosen
            if scripted and not outside:
                provider = self._director_provider(chosen)
                with (AIP.use_provider(provider) if provider is not None else nullcontext()):
                    sf, how = script_service.direct(p, sf, lambda f, m: self._say("plan", 0.3 + 0.65 * f, m), want_ai=True)
                ai_directed = not how.startswith("rules") and how != "plan"
                if not ai_directed:
                    actual = "rules"
            elif not outside and not local_planned:            # the local picture planner could not run: this is the rule draft
                actual = "rules"
            if how.startswith("rules"):
                notice = notice or "The AI script was not available; the rule director wrote it (" + how.split(" + ")[0][7:-1][:120] + ")"
            if outside:
                p.save_scenes(sf)                              # only so the project has a plan while it waits; the director writes the whole video itself
                self._say("plan", 0.1, f"Waiting for {available[chosen].get('label', 'Claude on this PC')}")
                result = directors.broker.request(chosen.split("@", 1)[1], p.id, directors.client_scene_prompt(p.id), directors.direct_timeout(), assistant=chosen.split('@',1)[0])
                returned = p.scenes()
                if result.get("ok") and returned is not None and returned.planner in ("claude", "assistant"):
                    sf = returned
                    ai_directed = True
                    fell = after_failure((available.get(chosen) or {}).get("label") or chosen)
                    directors.record(p, chosen, requested=requested, fallback_reason=fell)
                    notice = notice or fell or None
                else:
                    # it did not finish (its usage limit, its sign-in, a plan it never submitted): whatever it half did is taken back, and the next director takes the video
                    self._failed[chosen] = directors.failure_line(chosen, result, (available.get(chosen) or {}).get("label") or chosen)
                    p.save_scenes(sf)                                  # the draft again: nothing the director half made stays
                    retry = True
            else:
                unavailable = after_failure("the rule director" if actual == "rules" else (available.get(chosen) or {}).get("label") or chosen) or unavailable
                directors.record(p, actual, requested=requested,
                                 fallback_reason=unavailable or ("The selected AI was unavailable, so the rule director wrote the plan." if actual == "rules" else ""))
                notice = notice or unavailable
        except Exception as e:                  # noqa: BLE001 — the script step never breaks the video
            import logging
            logging.getLogger("pipeline.plan").warning("script step failed", exc_info=True)       # the traceback goes to the video's technical log
            notice = notice or f"Script step skipped: {type(e).__name__}: {str(e)[:120]}"
        if retry:
            return self.stage_plan(force=True)                           # the next director in the person's order (the Local AI, at the end of it), with one line saying why
        write_json(p.dir / "usecase.json", {"requested": meta.usecase, "used": usecase, "profile": profile.get("label")})
        write_json(p.dir / "ai_notice.json", {"at": now_iso(), "message": notice, "brief": brief}) if (notice or brief) else (p.dir / "ai_notice.json").unlink(missing_ok=True)
        try:
            from . import sounds as SN

            doc = SN.load(p) if meta.options.sound_events != "off" else None
            from . import aroll as AR

            speaker = next((m for m in p.meta().media if m.id == "aroll" and m.role == "a_roll"), None) if meta.options.aroll != "off" else None
            if speaker is not None:
                from . import talk_outline as TO
                outline = TO.ensure(p, progress=lambda f, m: self._say("plan", 0.96, m))       # a long talk: its examples, read ahead, get the B-roll (C10)
                AR.apply_speaker(sf, p, beats, meta.aspect, speaker, force=TO.speaker_scenes(outline, sf, beats))          # the speaker where nothing better illustrates the words
                TO.fill_examples(p, sf, beats, outline, lambda f, m: self._say("plan", 0.97, m))       # an example left with only words gets a picture
                if outline:                                                    # in a long talk a scene of words alone on an empty background is worse than the speaker
                    bare = {sc.id for sc in sf.scenes if sc.backdrop is None and not TO._is_broll(sc)}
                    if bare:
                        AR.apply_speaker(sf, p, beats, meta.aspect, speaker, force=bare)
            raw = read_json(p.raw_transcript_path) or {}
            if raw.get("model") == "sounds":                           # nobody speaks: the sounds are the story
                sf, _ = SN.plan_from_sounds(sf, (doc or {}).get("events", []), tr, beats)
            elif doc and doc.get("events") and not ai_directed:
                SN.add_stickers(sf, doc["events"], tr, beats)          # a picture where a sound happens
        except Exception as e:                                          # noqa: BLE001 — extras on top of a valid plan
            from .notices import record as record_notice
            record_notice(p, "plan", "The speaker's picture, the read-ahead B-roll or the sound stickers could not be added to every scene.", e)
        if not ai_directed:                                               # these passes finish the rule draft; an AI's plan is its own direction (craft.check below still reports on it)
            try:
                from . import craft as CR

                CR.fix_hook(sf, tr, p)                                     # the first frame shows what the video is about (vt/craft.py hook.topic)
                CR.fix_numbers(sf, tr, beats, meta.language)               # never a figure nobody said
            except Exception as e:                                         # noqa: BLE001 — checks on top of a valid plan
                from .notices import record as record_notice
                record_notice(p, "plan", "The opening and the numbers were not checked.", e)
            try:
                from .director import heartbeat as HB

                HB.add_heartbeats(sf, tr, beats, meta.aspect)             # no scene sits still for long: a related visual at a spoken word where a gap would be too long
                spk = next((m for m in p.meta().media if m.id == "aroll" and m.role == "a_roll"), None) if meta.options.aroll != "off" else None
                if spk is not None:                                       # still too still and no real word to show: the speaker is the better picture
                    from . import aroll as AR2

                    left = HB.still_scenes(sf, tr, beats, meta.aspect)
                    if left:
                        AR2.apply_speaker(sf, p, beats, meta.aspect, spk, force=set(left))
            except Exception as e:                                         # noqa: BLE001 — an extra on top of a valid plan
                from .notices import record as record_notice
                record_notice(p, "plan", "Still stretches could not be given the speaker's picture.", e)
        try:
            from . import aroll as AR3
            AR3.keep_screen_clear(sf, p)                                # a slide recording shows only itself and the captions
        except Exception as e:                                          # noqa: BLE001 — the plan is valid without it
            from .notices import record as record_notice
            record_notice(p, "plan", "Words over the screen recording could not be cleared.", e)
        errs = validate_scenes(sf, tr, beats, icons)
        if errs:
            raise RuntimeError("rule planner produced an invalid plan: " + "; ".join(errs[:5]))
        p.save_scenes(sf)
        write_json(p.dir / "plan_basis.json", self._word_basis())
        try:
            from . import craft as CR

            write_json(p.dir / "craft.json", CR.check(p))                  # the craft rules this plan still breaks, for the Review page and the director
        except Exception as e:                                             # noqa: BLE001 — a report, not the plan
            from .notices import record as record_notice
            record_notice(p, "plan", "The craft check was skipped, so the Review page has no craft notes for this plan.", e)
        p.mark_stage("plan", "rules", scenes=len(sf.scenes), usecase=usecase)

    def _word_basis(self) -> dict[str, str]:
        """What each word id meant when the plan was made: the recognised (raw) text, so the person's own spelling fixes do not count as a change."""
        raw = (read_json(self.p.raw_transcript_path) or {}).get("words", [])
        return {f"w{i}": w.get("text", "") for i, w in enumerate(raw, 1)}

    def _plan_is_stale(self, sf: ScenesFile) -> bool:
        """Word ids are positions in the recognised transcript; when recognition runs again (a new model, a filter) they can shift, and a kept
        plan would show its pictures at other words. True when any word the plan refers to now says something else."""
        basis = read_json(self.p.dir / "plan_basis.json")
        if not basis:
            return False                                        # a plan from before this check: nothing to compare with
        now = self._word_basis()
        ids = {el.at_word for sc in sf.scenes for el in sc.elements} | {c.get("at_word") for sc in sf.scenes for c in sc.sfx}
        ids |= {a.get("at_word") for sc in sf.scenes for a in ((sc.stick or {}).get("actions") or [])}
        return any(basis.get(i) != now.get(i) for i in ids if i)

    def _resolve_auto_theme(self, meta, tr, mood, profile=None):
        """theme "auto": design a look from what the video is about, save it as a theme of its own, and use it."""
        if meta.theme != "auto":
            return meta
        from . import designer, paths
        from .util import write_json as wj

        mood = mood if mood in designer.MOOD_LOOKS else designer.mood_from_text(" ".join(w.text for w in tr.words))
        t = designer.auto_theme(self.p.id, mood, name=f"auto-{self.p.id[-24:].strip('-')}"[:40].lower(), looks=(profile or {}).get("looks"))
        (paths.THEMES / t.name).mkdir(parents=True, exist_ok=True)
        wj(paths.THEMES / t.name / "theme.json", t.model_dump(exclude_none=True))
        return self.p.update_meta(theme=t.name)

    def stage_compose(self, force: bool = False) -> None:
        compose_all(self.p)
        sf = self.p.scenes()
        if sf is None or sf.planner not in AI_PLANNERS:
            if sf is not None:
                try:
                    layout_check.record(self.p)                          # no AI directs this plan: the rules keep the layout guard, and what it did goes to Details, Problems
                except Exception as e:                                   # noqa: BLE001  a report, never a reason to stop a video
                    log.warning("could not read the layout guard of %s: %s", self.p.id, e)
            return                                                       # a rule draft or the person's own edits: nobody to ask
        from .ai import providers as AIP

        chosen = self._director_provider(self.director())
        with (AIP.use_provider(chosen) if chosen is not None else nullcontext()):
            if not AIP.ai_enabled():
                return
            from .director_review import review

            try:
                review(self.p, lambda f, m: self._say("compose", 0.05 + 0.9 * f, m))
            except Exception as e:                                       # noqa: BLE001 — the cut as planned is still a video
                from .notices import record as record_notice
                record_notice(self.p, "compose", "The director's look at the finished cut was skipped, so it was not revised.", e)
                write_json(self.p.dir / "director_review.json", {"at": now_iso(), "error": f"{type(e).__name__}: {str(e)[:300]}"})


# ---------------------------------------------------------------------- helpers


@contextmanager
def directing(project: Project):
    """Inside the block, every AI step belongs to this video's director and is written on the video's record (Details): the pipeline's own stages, and
    every later job on the video (checking its frames, writing its title, ...). One mind directs the whole video."""
    from .ai import providers as AIP, talk

    provider = None
    try:
        pipeline = Pipeline(project)
        provider = pipeline._director_provider(pipeline.director())
    except Exception as e:                                           # noqa: BLE001 — a director that cannot be worked out never stops a job: the AI setting in Settings applies
        log.warning("could not work out the director of %s: %s", project.id, e)
    with talk.for_project(project.dir), (AIP.use_provider(provider) if provider is not None else nullcontext()):
        yield provider


_COMPOSE_LOCKS: dict[str, "threading.RLock"] = {}


def compose_all(project: Project) -> list[Path]:
    """Compose both aspects (cheap, pure Python); the Studio previews either one. One composition per project at a time: edits that arrive together
    (a slider dragged, two clicks) queue up instead of writing the same files at once."""
    import threading

    lock = _COMPOSE_LOCKS.setdefault(project.id, threading.RLock())
    with lock:
        return [compose_project(project, aspect) for aspect in FORMATS]


def remap_scenes(sf: ScenesFile, old: Beats, new: Beats) -> Optional[ScenesFile]:
    """Re-attach scenes to new sentence boundaries: each new beat joins the scene that owned most of its words before."""
    from collections import Counter

    old_by = {b.id: b for b in old.beats}
    word_scene: dict[str, str] = {}
    for sc in sf.scenes:
        for bid in sc.beats:
            for w in old_by.get(bid, type("E", (), {"word_ids": []})).word_ids:
                word_scene[w] = sc.id
    if not word_scene:
        return None
    order = {sc.id: i for i, sc in enumerate(sf.scenes)}
    assigned: list[str] = []
    last = sf.scenes[0].id
    for nb in new.beats:
        votes = Counter(word_scene[w] for w in nb.word_ids if w in word_scene)
        sid = votes.most_common(1)[0][0] if votes else last
        if order[sid] < order[last]:       # scenes stay in order
            sid = last
        assigned.append(sid)
        last = sid
    scenes = []
    for sc in sf.scenes:
        ids = [nb.id for nb, s in zip(new.beats, assigned) if s == sc.id]
        if ids or sc.start is not None:       # manually timed visual scenes survive transcript edits
            scenes.append(sc.model_copy(update={"beats": ids}))
    if not scenes:
        return None
    return sf.model_copy(update={"scenes": scenes})


def repair_scenes(sf: ScenesFile, tr: Transcript, beats: Beats, icons: set[str], old_beats: Optional[Beats] = None) -> Optional[ScenesFile]:
    """Make a plan fit edited/re-cut material: remap beats, then move/drop elements whose anchor word disappeared.
    Returns the (possibly unchanged) plan, or None if it cannot be saved."""
    if not validate_scenes(sf, tr, beats, icons):
        return sf
    beat_ids = {b.id for b in beats.beats}
    if any(b not in beat_ids for sc in sf.scenes for b in sc.beats) or {b for sc in sf.scenes for b in sc.beats} != beat_ids:
        if old_beats is None:
            return None
        sf = remap_scenes(sf, old_beats, beats)
        if sf is None:
            return None
    beat_by = {b.id: b for b in beats.beats}
    data = sf.model_dump()
    for sc in data["scenes"]:
        wids = [w for b in sc["beats"] if b in beat_by for w in beat_by[b].word_ids]
        wset = set(wids)
        if not wids and sc.get("start") is None:
            return None
        for el in sc["elements"]:
            if el["at_word"] not in tr.by_id() or (el["at_word"] not in wset and sc.get("start") is None and el.get("start") is None):
                el["at_word"] = (wids or [w.id for w in tr.kept()])[0]
        sc["caption"]["highlight_words"] = [w for w in sc["caption"]["highlight_words"] if w in wset]
    from pydantic import ValidationError

    try:
        fixed = ScenesFile.model_validate(data)
    except ValidationError:                                          # the remapped plan no longer fits: the caller plans again
        return None
    return fixed if not validate_scenes(fixed, tr, beats, icons) else None


def export(project: Project, aspect: Optional[str] = None, *, quality: str = "looks", gpu: bool = True,
           music: Optional[str] = "__project__", fps: Optional[int] = None, short_side: Optional[int] = None,
           captions: bool = True, clean_voice: bool = False, progress: ProgressFn = noop_progress) -> dict:
    """Render one aspect to a finished MP4 (+ .srt). Returns paths and timings."""
    from .render import build_sfx_track, mix_and_mux, render_silent, sfx_level
    from .render.mux import resolve_music

    t0 = time.time()
    meta = project.meta()
    aspect = aspect or meta.aspect
    fmt = FORMATS[aspect]
    progress("compose", 0.0, "composing")
    index = compose_project(project, aspect, captions=captions)
    comp_dir = index.parent
    data = read_json(comp_dir / "data.json")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = project.exports_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    silent = out_dir / f".render-{fmt['tag']}.mp4"
    from .render.hyperframes import check as hf_check

    progress("render", 0.0, "checking the composition")
    verdict = hf_check(comp_dir)
    write_json(out_dir / f".check-{fmt['tag']}.json", verdict)
    if verdict.get("errors"):
        progress("render", 0.0, f"HyperFrames found {verdict['errors']} problem(s) that can break the picture: {verdict['issues'][0]['message'][:120]}")
    progress("render", 0.0, "rendering frames")
    render_silent(comp_dir, silent, fps=fps or fmt["fps"], quality=quality, gpu=gpu,
                  on_progress=lambda f, c: progress("render", f, c))
    progress("mux", 0.0, "mixing audio")
    voice = project.cut_audio if project.cut_audio.exists() else project.master
    track = None if music is None else (meta.options.music if music == "__project__" else music)
    music_path = resolve_music(track)
    sfx = build_sfx_track(data["cues"], data["duration"], project.dir / "audio.sfx.wav", sfx_level(meta.options), seed=project.id)
    from . import layers as LY

    layer_audio = LY.audio_clips(project)
    final = out_dir / f"{project.id}-{fmt['tag']}-{stamp}.mp4"
    mix_and_mux(silent, voice, final, duration=data["duration"], music=music_path,
                music_volume=meta.options.music_volume, sfx=sfx, short_side=short_side, gpu=gpu, layer_audio=layer_audio, clean_voice=clean_voice,
                duck=meta.options.duck, duck_amount=meta.options.duck_amount, duck_release=meta.options.duck_release,
                target_lufs=meta.options.target_lufs, music_fade_in=meta.options.music_fade_in, music_fade_out=meta.options.music_fade_out)
    acceleration=read_json(silent.with_suffix('.acceleration.json'),None)
    if acceleration:write_json(final.with_suffix('.acceleration.json'),acceleration)
    silent.unlink(missing_ok=True)
    srt = final.with_suffix(".srt")
    srt.write_text(to_srt(data["captions"]), encoding="utf-8")
    from .compose.composer import to_vtt
    final.with_suffix(".vtt").write_text(to_vtt(data["captions"]), encoding="utf-8")      # the same captions for web players (C10)
    from . import credits as CR

    credits = CR.text(project, track or "")               # stock, catalogue, the music's licence and a link's source, written next to the video
    if credits:
        final.with_suffix(".credits.txt").write_text(credits, encoding="utf-8")
    try:                                                      # the retention scorecard of what was just made (vt/retention.py); never stops an export
        from . import retention as RT

        RT.save(final.with_suffix(".retention.json"), RT.scorecard(final, aspect, data, project.cut_audio if project.cut_audio.exists() else None))
    except Exception as e:                                           # noqa: BLE001 — the video is made; only its scorecard is missing
        from .notices import record as record_notice
        record_notice(project, "render", "The retention scorecard could not be made for this export.", e)
    compose_project(project, aspect)  # restore the preview composition (captions on) after a no-captions export
    project.update_meta(status="rendered")
    progress("mux", 1.0, "done")
    return {"video": str(final), "srt": str(srt), "seconds": round(time.time() - t0, 1), "duration": data["duration"]}
