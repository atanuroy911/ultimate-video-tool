"""Copy OpenChatCut source files into client/studio/src/occ/, keeping their folder layout (so relative imports keep working) and adding a
header that names the source file and commit. Files that already carry a `// Video Tool:` change are left alone unless --force.

    python scripts/port_openchatcut.py <OpenChatCut checkout> <file list>   # one repo-relative path per line (src/... or shared/...)

The reference checkout lives at E:/OpenChatCut-9242a95 (github.com/0xsline/OpenChatCut, commit 9242a95). Plan: docs/plans/PLAN-OPENCHATCUT.MD.
"""
import pathlib
import sys

COMMIT = "9242a95"
HEADER = "// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) {path} @ {commit}. See src/occ/NOTICE.md.\n"


def main() -> int:
    src_root, listing = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    force = "--force" in sys.argv
    dest_root = pathlib.Path(__file__).resolve().parents[1] / "client" / "studio" / "src" / "occ"
    copied = kept = 0
    for rel in [l.strip() for l in listing.read_text(encoding="utf-8").splitlines() if l.strip()]:
        dest = dest_root / rel
        if dest.exists() and "// Video Tool:" in dest.read_text(encoding="utf-8") and not force:
            kept += 1
            continue
        text = (src_root / rel).read_text(encoding="utf-8")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(HEADER.format(path=rel, commit=COMMIT) + text, encoding="utf-8")
        copied += 1
    print(f"copied {copied}, kept {kept} (they carry Video Tool changes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
