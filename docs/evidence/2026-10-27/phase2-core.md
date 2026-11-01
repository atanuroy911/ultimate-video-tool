# Phase 2 core module evidence — 2026-10-27

Phase 2 is **complete** for its adapter/runtime scope. This checkpoint covers 125 modules beyond Phase 1 and records the later-phase boundary explicitly.

## Implemented

- Canonical wrappers for voice, clean, silence, ASR, cuts, sound events, transcript, tighten, context, scene planning and composition. These call the existing `Pipeline.stage_*` bodies.
- Project options; language detection; pause boundaries; sentence ranking; roles; screen-text tidying; music selection; beat detection/snapping and SFX placement.
- Existing export and publish-kit flows. Export records `exports/` but has `version_outputs=False`, preventing a large copy of prior exports before every render.
- Director controls: `meta.catalog`, `meta.describe`, `meta.state`, `meta.dry_run`, `meta.undo`, `meta.wait`, `meta.cancel`, `meta.note`, `meta.health`, `meta.hardware`, and `meta.models`.
- Project media and sound import/removal, named and constructed themes, manual audio cut/mute/gain/split history, subtitle-to-word ingestion and signal-derived word emphasis.
- Rule-derived key terms and use-case detection, sound-event captions, stock-media credits, and confirmed local creator taste/preferences.
- Timeline caption chunking, deterministic motion recipes, media contrast, semantic validation and the three-second visual heartbeat.
- Video Script scoring, rule-based editor critique and grounded action enrichment.
- ComfyUI server status, pinned workflow listing/readiness, shared-GPU memory release, targeted prompt cancellation and the existing image-to-video generation path. Contract tests use fake clients; this checkpoint neither installs server code nor submits a live GPU job.
- Existing IS-Net background removal, cached scene thumbnails, selected-frame snapshots and silent HyperFrames rendering. Model/render execution is mocked in module contracts; the existing dedicated slow tests retain real coverage.
- Editable layer documents with validation and undo/redo; typed scene split/merge/boundary/patch/action/cast operations; consented local voice registration/listing; conservative two-speaker labeling; and rendered retention scorecards.
- AI-plus-measured-fallback Shorts detection and standalone child slicing.
- The planned uniform Slot→Fragment contract, with grounded placeholder, text-card, explicit user-media, still-zoom and speaker-footage fill modules. Fragment items remain ordinary editable timeline data.
- Existing soundtrack selection and theme resolution; AI-first transcript polish, media description and grounded publishing copy; Video Script compilation and AI-first/rule-fallback planning.
- One-sentence speech synthesis with duration and word timing measured from the resulting waveform; conversational direction through the existing validated script chat flow.
- Rendered scene QA with the existing pixel fallback and contextual picture-candidate judging.
- Executor prerequisite correction: when a native producer's own requirements are already ready, it runs that producer directly instead of replaying unrelated earlier classic stages.
- Executor provenance correction: a module that reads and updates the same artifact no longer records the previous version as a self-dependency and immediately marks its output stale.
- Executor cache correction: state-changing modules with no tracked project artifact always execute, so repeated confirmed preferences and similar side effects are not swallowed by a cache hit.

The registry contains 140 modules total: 12 `pipeline.*` adapters, the 3 Phase 1 spike modules, and 125 Phase 2 modules.

## Verification

Focused contracts and behavioral comparisons:

```text
python -m pytest -q -o addopts= -p no:cacheprovider --basetemp qa_phase2/focused3 -p no:warnings \
  tests/test_modules_core.py tests/test_modules_registry.py tests/test_modules_executor.py \
  tests/test_modules_toolspec.py tests/test_modules_workspace.py
28 passed in 18.88s
```

Registry contract:

```text
modules 49
lint []
```

Full fast regression:

```text
python -m pytest -q -m "not slow" -p no:cacheprovider --basetemp qa_phase2/fast -p no:warnings
exit code 0
815/882 tests collected (67 deselected); one existing opt-in case is skipped
```

The focused comparisons include byte equality for `audio.clean`, existing-function equality for language, pauses, ranking, text tidying, music choice and beat snapping, rule-fallback equality for the publish kit, validated pass-through for export, canonical stage execution on the reference project, meta contracts, and the no-export-history-copy assertion.

`python scripts/map_tests.py` regenerated `docs/evidence/code-test-map.md`. `python scripts/check_docs.py --fix-facts` then completed successfully after refreshing the measured facts table.

Continuation module regression:

```text
python -m pytest -q -o addopts= -m "not slow" -p no:cacheprovider tests/test_modules_*.py
41 passed, 2 deselected in 28.82s
registry: 57 modules; lint []
```

Second continuation checkpoint:

```text
45 passed, 2 deselected in 29.18s
registry: 63 modules; lint []
```

Timeline and judging checkpoint:

```text
50 passed, 2 deselected in 28.23s
registry: 71 modules; lint []
```

Generation-control checkpoint:

```text
52 passed, 2 deselected in 27.94s
registry: 76 modules; lint []
```

Cutout and render-helper checkpoint:

```text
55 passed, 2 deselected in 36.11s
registry: 80 modules; lint []
```

Editing, voices and scorecard checkpoint:

```text
60 passed, 2 deselected in 34.74s
registry: 86 modules; lint []
```

Shorts and first fill-contract checkpoint:

```text
63 passed, 2 deselected in 39.06s
registry: 93 modules; lint []
```

Direction, copy, compilation and vision checkpoint:

```text
74 passed in the combined runtime/equivalence/core module suite
registry: 104 modules; lint []
```

Phase 2 completion checkpoint:

```text
combined module runtime/equivalence/core suite: 80 passed
completion contracts: 6 passed
full fast regression: 859 selected, 1 expected opt-in skip, 0 failed
registry: 140 modules; lint []
code-test map: 163 source modules, 28 without a direct static test-file match
```

## Boundary after Phase 2

`gen.image` and `gen.video_from_text` depend on new ComfyUI workflow assets and the experiments assigned to Phase 5. The `plan.*` approval/edit/preview surface belongs to Phase 4. Those are not wrappers over existing Phase 0 code and are therefore not Phase 2 adapter gaps. `publish.dispatch` is registered only in the `full` toolbox and refuses calls without explicit confirmation; no real social account was contacted by this checkpoint.
