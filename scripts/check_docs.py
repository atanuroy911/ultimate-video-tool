"""Keep the docs honest. Fails (exit 1) when:

  1. a markdown link in any doc points at a file that does not exist;
  2. a `backticked path` in docs/STATUS.md, docs/HANDOFF.md or docs/README.md does not exist (planned files are written without backticks);
  3. a `tests/test_x.py::test_name` reference names a test that is not in the file;
  4. the facts table between <!-- facts:begin --> and <!-- facts:end --> in docs/STATUS.md differs from what scripts/count_facts.py measures now;
  5. a phase heading in docs/ROADMAP.md is missing its Status line.

    python scripts/check_docs.py            # all checks
    python scripts/check_docs.py --fix-facts  # rewrite the facts table in docs/STATUS.md from the code
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRICT = ["docs/STATUS.md", "docs/HANDOFF.md", "docs/README.md"]
SKIP_LINK_DIRS = ("docs/history", "docs/evidence", "third_party", "node_modules", ".venv")
PATH_ROOTS = ("vt/", "tests/", "studio/", "renderer/", "scripts/", "docs/", "assets/", "design/", "samples/", "third_party/", "desktop/", "build/", "projects/", "models/")
EXT = r"(?:py|ts|tsx|js|mjs|json|md|MD|ps1|css|html|yaml|yml|txt|log|xml|svg|toml|png|mp4|wav|mp3|jsonl)"
PATH_TOKEN = re.compile(rf"^(?:[\w.\-]+/)+[\w.\-]*\.{EXT}$|^(?:{'|'.join(re.escape(r) for r in PATH_ROOTS)})[\w./\-]*$")


def md_files() -> list[Path]:
    out = [ROOT / "README.md", ROOT / "plan.md"]
    out += [p for p in (ROOT / "docs").rglob("*") if p.suffix.lower() == ".md"]
    return [p for p in out if p.exists() and not any(part in str(p.relative_to(ROOT)).replace("\\", "/") for part in SKIP_LINK_DIRS)]


def check_links(problems: list[str]) -> int:
    n = 0
    for p in md_files():
        for m in re.finditer(r"\[[^\]]*\]\(([^)\s]+)\)", p.read_text(encoding="utf-8", errors="replace")):
            link = m.group(1)
            if re.match(r"^(https?:|mailto:|#)", link):
                continue
            n += 1
            target = (p.parent / link.split("#")[0]).resolve()
            if not target.exists():
                problems.append(f"{p.relative_to(ROOT)}: broken link ({link})")
    return n


def check_paths(problems: list[str]) -> int:
    n = 0
    for rel in STRICT:
        p = ROOT / rel
        if not p.exists():
            problems.append(f"{rel}: missing")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"`([^`\n]+)`", text):
            tok = m.group(1).strip()
            test = re.match(r"^(tests/[\w./\-]+\.py)::(\w+)$", tok)
            if test:
                n += 1
                tp = ROOT / test.group(1)
                if not tp.exists() or not re.search(rf"def {re.escape(test.group(2))}\b", tp.read_text(encoding="utf-8", errors="replace")):
                    problems.append(f"{rel}: test not found ({tok})")
                continue
            sym = re.match(r"^([\w./\-]+\.(?:py|ts|tsx|js|mjs))::([\w.]+)$", tok)
            if sym:
                n += 1
                sp = ROOT / sym.group(1)
                name = sym.group(2).split(".")[-1]
                if not sp.exists():
                    problems.append(f"{rel}: path does not exist ({tok})")
                elif not re.search(rf"(?:def|class|function|const|let|var)\s+{re.escape(name)}\b|^\s*{re.escape(name)}\s*[:=]", sp.read_text(encoding="utf-8", errors="replace"), re.M):
                    problems.append(f"{rel}: symbol not found ({tok})")
                continue
            if any(c in tok for c in "*<>{}…$") or tok.startswith(("/", "~", "http")) or " " in tok or not PATH_TOKEN.match(tok):
                continue
            n += 1
            if not (ROOT / tok.rstrip("/")).exists():
                problems.append(f"{rel}: path does not exist ({tok})")
    return n


def facts_block(text: str) -> tuple[int, int] | None:
    a, b = text.find("<!-- facts:begin -->"), text.find("<!-- facts:end -->")
    return (a + len("<!-- facts:begin -->"), b) if a != -1 and b != -1 else None


def check_facts(problems: list[str], fix: bool) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from count_facts import measure, to_markdown

    p = ROOT / "docs" / "STATUS.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    span = facts_block(text)
    if not span:
        problems.append("docs/STATUS.md: facts markers missing")
        return
    fresh = "\n" + to_markdown(measure()) + "\n"
    if text[span[0]:span[1]] != fresh:
        if fix:
            p.write_text(text[:span[0]] + fresh + text[span[1]:], encoding="utf-8")
            print("rewrote the facts table in docs/STATUS.md")
        else:
            problems.append("docs/STATUS.md: the facts table differs from the code (run: python scripts/check_docs.py --fix-facts, then read what changed)")


def check_roadmap(problems: list[str]) -> int:
    p = ROOT / "docs" / "ROADMAP.md"
    if not p.exists():
        return 0
    text = p.read_text(encoding="utf-8")
    heads = list(re.finditer(r"^## (Phase [\w.]+)\b.*$", text, re.M))
    for i, h in enumerate(heads):
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        if not re.search(r"^\*\*Status:\*\* (DONE|NEXT|PLANNED|PARALLEL|PARTLY DONE)", body, re.M):
            problems.append(f"docs/ROADMAP.md: {h.group(1)} has no **Status:** line")
    return len(heads)


def main() -> None:
    problems: list[str] = []
    links = check_links(problems)
    paths = check_paths(problems)
    phases = check_roadmap(problems)
    if '--structural-only' not in sys.argv:
        check_facts(problems, "--fix-facts" in sys.argv)
    print(f"checked {links} links, {paths} paths/tests in the strict docs, {phases} roadmap phases")
    for pr in problems:
        print("PROBLEM:", pr)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
