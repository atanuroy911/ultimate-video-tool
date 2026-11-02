"""Runs the stages for a project. Every stage hashes its inputs, so re-running only redoes what changed."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from . import paths
from .compose import FORMATS, compose_project, to_srt
from .planner import plan_rules
from .planner.catalogue import all_icon_names
from .project import Project, load_theme
from .schema import Beats, Cuts, ProjectMeta, ScenesFile, Transcript, validate_scenes
from .stages import audio as A
from .stages.align import snap_words
from .stages.chunks import plan_chunks
from .stages import words as W
from .util import ProgressFn, file_hash, noop_progress, now_iso, read_json, write_json

log = logging.getLogger(__name__)
REEL_HOLD_S = 3.0                     # the three-second rule: something changes on screen at least this often (longer videos breathe: x1.6, see vt/reel/slots.py)
AUTO_LANGUAGES = ["bn", "en"]          # what "auto" chooses between: the two languages the whole app (speech, captions, voices) is built for
LEAD_IN_MAX, LEAD_IN_KEEP = 3.0, 0.6       # seconds of non-speech allowed before the first word, and how much of it is kept
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

    def _say(self, stage: str, frac: float, msg: str = "") -> None:
        self.progress(stage, frac, msg)

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
        self.p.update_meta(status="processing")
        try:
            run_classic(self, stages, force=force)
            self.p.update_meta(status="review" if self.pause_reason == "plan" else "planned")
        except Exception:
            self.p.update_meta(status="error")   # the job keeps the failing stage as its current stage, so the UI can mark it
            raise

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
        denoise = not p.script_path.exists()          # synthetic speech is already clean; noise reduction would only dull it
        h = file_hash(p.input_audio, extra=f"denoise={int(denoise)}")
        if self._fresh("preprocess", h, force, p.master, p.asr_wav):
            return
        if not p.input_audio.exists():
            raise FileNotFoundError(f"no input audio in {p.dir}")
        A.preprocess(p.input_audio, p.master, p.asr_wav, denoise=denoise)
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
            silences, dur, _, _ = A.find_silences(p.asr_wav, 0.2, (read_json(p.dir / "cuts.silence.json") or {}).get("threshold_db"), return_db=True)
            words, dropped = snap_words(raw["words"], silences, dur)
            raw["words"] = words or raw["words"]
            raw["snap_dropped"] = dropped
            write_json(p.raw_transcript_path, raw)
            p.mark_stage("asr", h, words=len(raw["words"]), model="subtitles", dropped=dropped)
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
        except Exception as e:                                     # no detector model and no network: Bangla is the app's first language
            log.warning("language detection failed (%s); using Bangla", e)
            lang = "bn"
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
        except Exception as e:
            write_json(p.dir / "aroll.error.json", {"at": now_iso(), "error": f"{type(e).__name__}: {str(e)[:200]}"})

    def stage_sounds(self, force: bool = False) -> None:
        """Find laughter, applause, music, animals ... in the voice track (output time). Never stops the video: a failure is recorded and the stage is skipped."""
        p = self.p
        from . import sounds as SN

        if p.meta().options.sound_events == "off" or not SN.available() or not p.cut_audio.exists():
            return
        try:
            SN.analyze_project(p, lambda f: self._say("sounds", f, "listening"), force=force)
        except Exception as e:
            write_json(SN.path(p), {"hash": "", "model": SN.MODEL, "duration": 0, "events": [], "error": f"{type(e).__name__}: {str(e)[:160]}"})

    def stage_cuts(self, force: bool = False) -> None:
        p = self.p
        meta = p.meta()
        sil = read_json(p.dir / "cuts.silence.json")
        h = file_hash(p.dir / "cuts.silence.json", p.raw_transcript_path, p.dir / "audio_edits.json", extra=f"fillers={meta.options.remove_fillers}|retakes={meta.options.remove_retakes}|rt-v3|{tighten_signature(p)}")
        if self._fresh("cuts", h, force, p.cuts_path, p.cut_audio):
            return
        from . import audio_edit as AE

        edits = AE.load(p)                                           # the user's own cuts, mutes and volume changes
        if sil and sil.get("cuts"):
            base = Cuts.model_validate(sil["cuts"])
        else:                                                        # no silence stage ran (a hand-built or imported project): keep the whole recording and apply only the edits
            import soundfile as sf

            total = float(sf.info(str(p.master)).duration)
            base = Cuts(source_duration=total, keep=[(0.0, total)])
        removed = A.removed_from_cuts(base) + [(a, b) for a, b in edits["cuts"]]
        raw = read_json(p.raw_transcript_path) or {"words": []}
        first = min((w["start"] for w in raw.get("words", [])), default=0.0)
        if first > LEAD_IN_MAX:                                      # a long stretch of noise or music before anyone speaks would be a still opening with no captions
            removed.append((0.0, first - LEAD_IN_KEEP))
        if meta.options.remove_fillers:
            for i in sorted(W.find_fillers(raw["words"])):
                w = raw["words"][i]
                removed.append((max(0.0, w["start"] - 0.02), w["end"] + 0.04))
        retakes = []
        if meta.options.remove_retakes and not p.script_path.exists():      # a typed script has no retakes
            from .retakes import find_retakes

            retakes = find_retakes(raw.get("words", []))
            for r in retakes:
                removed.append((max(0.0, r["start"] - 0.03), r["end"] + 0.05))
        for d in (read_json(p.dir / "tighten.json") or {}).get("cuts", []):     # sentences the tighten stage dropped (source time)
            removed.extend((a, b) for a, b in d.get("src", []))
        write_json(p.dir / "retakes.json", {"cuts": [{k: v for k, v in r.items() if k != "words"} for r in retakes]})   # shown as "what the editor cut"
        cuts = A.cuts_from_removed(base.source_duration, removed)
        write_json(p.cuts_path, cuts.model_dump())
        dur = A.apply_cuts(p.master, cuts, p.cut_audio)
        AE.apply_to_cut_audio(p.cut_audio, cuts, edits)
        p.ensure_preview_audio()
        p.mark_stage("cuts", h, output_seconds=round(dur, 2), retakes=len(retakes))

    def stage_words(self, force: bool = False) -> None:
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
            except Exception:                                  # a guess must never stop a video from being made
                who = None
            if who:
                names = (read_json(p.dir / "speakers.json", {}) or {}).get("names", {})
                tr = SP.label_words(tr, beats, {b: names.get(n, n) for b, n in who.items()})
                beats = W.build_beats(tr, max_seconds=hold)    # sentences now also break where the speaker changes
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
                except Exception:
                    use_ai = False
            ctx = CX.build(p.transcript(), p.beats(), meta.language, use_ai=use_ai, overrides=ov)
            ctx.hash = CX.current_hash(p)
            CX.save(p, ctx)
            p.mark_stage("context", h, source=ctx.source, entities=len(ctx.entities), sections=len(ctx.sections))
        except Exception as e:
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
                if who.startswith("claude@") and status.get("available"):
                    plan = PD.build(p, use_ai=False)
                    PD.save(p.dir, plan)
                    self._say("plan", 0.1, f"Waiting for {status.get('label', 'Claude on this PC')}")
                    result = directors.broker.request(who.split("@", 1)[1], p.id, directors.client_prompt(p.id),
                                                      directors.settings()["wait_seconds"])
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

                    plan = PD.build(p, provider=ClaudeCLIProvider())
                    directors.record(p, who, requested=requested, fallback_reason=fallback_reason)
                    break
                if who == "local" and status.get("available"):
                    plan = PD.build(p)
                    directors.record(p, who, requested=requested, fallback_reason=fallback_reason)
                    break
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
        audio = p.cut_audio if p.cut_audio.exists() else None
        sf, brief = None, None
        notice = None
        from . import llm
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
        except Exception:                      # no dictionary/model: typography-only pictures
            picks = {}

        def draw(brief_):
            meta2 = self._resolve_auto_theme(meta, tr, None, profile)
            scrim = lambda mid, aspect, layout, t0, t1: K.decide_for_media(p, mid, aspect, layout, t0, t1)   # noqa: E731
            base = D.plan(tr, beats, theme=meta2.theme, language=meta.language, usecase=usecase, picks=picks, media=meta.planner_media(),
                          seed=p.id, brief=brief_, aspect=meta.aspect, scrim_fn=scrim)
            return meta2, base

        from .ai import providers as AIP

        # the per-scene picture planner speaks only to the local model; Claude and other providers plan through the AI script (script_service.direct below)
        if AIP.ai_enabled() and isinstance(AIP.current_provider(), AIP.OllamaProvider):
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
        if sf is None:
            meta, sf = draw(brief)
        try:
            from .script import service as script_service

            sf, how = script_service.direct(p, sf, lambda f, m: self._say("plan", 0.9 + 0.05 * f, m))
            if how.startswith("rules"):
                notice = notice or "The AI script was not available; the rule director wrote it (" + how.split(" + ")[0][7:-1][:120] + ")"
        except Exception as e:                  # the script step never breaks the video
            notice = notice or f"Script step skipped: {type(e).__name__}: {str(e)[:120]}"
        write_json(p.dir / "usecase.json", {"requested": meta.usecase, "used": usecase, "profile": profile.get("label")})
        write_json(p.dir / "ai_notice.json", {"at": now_iso(), "message": notice, "brief": brief}) if (notice or brief) else (p.dir / "ai_notice.json").unlink(missing_ok=True)
        try:
            from . import sounds as SN

            doc = SN.load(p) if meta.options.sound_events != "off" else None
            from . import aroll as AR

            speaker = next((m for m in p.meta().media if m.id == "aroll" and m.role == "a_roll"), None) if meta.options.aroll != "off" else None
            if speaker is not None:
                AR.apply_speaker(sf, p, beats, meta.aspect, speaker)          # the speaker where nothing better illustrates the words
            raw = read_json(p.raw_transcript_path) or {}
            if raw.get("model") == "sounds":                           # nobody speaks: the sounds are the story
                sf, _ = SN.plan_from_sounds(sf, (doc or {}).get("events", []), tr, beats)
            elif doc and doc.get("events"):
                SN.add_stickers(sf, doc["events"], tr, beats)          # a picture where a sound happens
        except Exception:
            pass
        try:
            from . import craft as CR

            CR.fix_hook(sf, tr, p)                                         # the first frame shows what the video is about (vt/craft.py hook.topic)
            CR.fix_numbers(sf, tr, beats, meta.language)                   # never a figure nobody said, whichever director wrote the plan
        except Exception:
            pass
        try:
            from .director import heartbeat as HB

            HB.add_heartbeats(sf, tr, beats, meta.aspect)                 # no scene sits still for long: a related visual at a spoken word where a gap would be too long
            spk = next((m for m in p.meta().media if m.id == "aroll" and m.role == "a_roll"), None) if meta.options.aroll != "off" else None
            if spk is not None:                                           # still too still and no real word to show: the speaker is the better picture
                from . import aroll as AR2

                left = HB.still_scenes(sf, tr, beats, meta.aspect)
                if left:
                    AR2.apply_speaker(sf, p, beats, meta.aspect, spk, force=set(left))
        except Exception:
            pass
        errs = validate_scenes(sf, tr, beats, icons)
        if errs:
            raise RuntimeError("rule planner produced an invalid plan: " + "; ".join(errs[:5]))
        p.save_scenes(sf)
        write_json(p.dir / "plan_basis.json", self._word_basis())
        try:
            from . import craft as CR

            write_json(p.dir / "craft.json", CR.check(p))                  # the craft rules this plan still breaks, for the Review page and the director
        except Exception:
            pass
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


# ---------------------------------------------------------------------- helpers


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
        if ids:                              # a scene whose sentences all vanished is dropped
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
        if not wids:
            return None
        for el in sc["elements"]:
            if el["at_word"] not in wset:
                el["at_word"] = wids[0]
        sc["caption"]["highlight_words"] = [w for w in sc["caption"]["highlight_words"] if w in wset]
    try:
        fixed = ScenesFile.model_validate(data)
    except Exception:
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
                music_volume=meta.options.music_volume, sfx=sfx, short_side=short_side, gpu=gpu, layer_audio=layer_audio, clean_voice=clean_voice)
    silent.unlink(missing_ok=True)
    srt = final.with_suffix(".srt")
    srt.write_text(to_srt(data["captions"]), encoding="utf-8")
    from .director.stock import credits_text

    credits = credits_text(project)                       # stock pictures/clips come with a thank-you list, written next to the video
    from .director.catalog import music_credit

    mc = music_credit(track)
    if mc:
        credits = (credits or "Media credits\n") + f"- {mc}\n"
    origin = project.meta().origin
    if origin:
        lines = [f"Voice and text from: {origin.get('title', '')} by {origin.get('uploader') or 'unknown'}", origin.get("url", "")]
        if origin.get("license"):
            lines.append(f"Licence: {origin['license']}")
        credits = (credits or "") + "\n".join(lines) + "\n"
    if credits:
        final.with_suffix(".credits.txt").write_text(credits, encoding="utf-8")
    try:                                                      # the retention scorecard of what was just made (vt/retention.py); never stops an export
        from . import retention as RT

        RT.save(final.with_suffix(".retention.json"), RT.scorecard(final, aspect, data, project.cut_audio if project.cut_audio.exists() else None))
    except Exception:
        pass
    compose_project(project, aspect)  # restore the preview composition (captions on) after a no-captions export
    project.update_meta(status="rendered")
    progress("mux", 1.0, "done")
    return {"video": str(final), "srt": str(srt), "seconds": round(time.time() - t0, 1), "duration": data["duration"]}
