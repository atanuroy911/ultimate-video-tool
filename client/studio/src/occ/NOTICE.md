# OpenChatCut parts in Video Tool's timeline

`src/occ/src/` and `src/occ/shared/` hold files ported from OpenChatCut (https://github.com/0xsline/OpenChatCut, commit `9242a95`,
2026-11-06), licensed GNU AGPL-3.0-or-later; copyright stays with the OpenChatCut authors. The owner is on the OpenChatCut team and approved
copying its code into Video Tool (2026-11-09). Each ported file starts with a header naming its source path.

- Folder layout mirrors upstream (`src/…`, `shared/…`) so relative imports are unchanged.
- Files marked `// Video Tool:` are changed or replaced (stand-ins for modules Video Tool does not take: other languages, GL effects, uploads,
  scene detection, motion tracking, caption translation, plugin templates). `scripts/port_openchatcut.py` re-copies everything else from a
  checkout and never overwrites a marked file.
- The file list is `scripts/openchatcut-timeline-files.txt`; the reference checkout is `E:\OpenChatCut-9242a95`.
- `src/occ/bridge/` is Video Tool's own code: our project ⇄ OpenChatCut's timeline state, and our preview player in Remotion's PlayerRef shape.
- Plan and phases: `docs/plans/PLAN-OPENCHATCUT.MD`.
