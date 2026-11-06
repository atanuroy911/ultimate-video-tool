"""The install scripts and Docker ask which graphics cards Video Tool may use (PLAN-PERFECT K5): the flag reaches `vt gpu setup`, the scripts are valid, and the words are in the README.
The scripts cannot run for real here (they download Python and models: step H5 does that on a server); what can be checked is that they parse, that the line that carries the answer
builds the right command, and that the question itself works (`tests/test_gpu_setup.py`, with a fake nvidia-smi)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1] / "server" / "packaging" / "engine"
BASH = shutil.which("bash")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def line_with(path: Path, needle: str) -> str:
    return next(l.split("#")[0].strip() if "#" in l and needle in l.split("#")[0] else l.strip() for l in path.read_text(encoding="utf-8").splitlines() if needle in l and not l.lstrip().startswith("#"))


@pytest.mark.skipif(not BASH, reason="no bash")
def test_the_shell_scripts_are_valid_and_the_help_names_the_flag():
    for name in ("install-engine.sh", "docker-entrypoint.sh"):
        done = subprocess.run([BASH, "-n", str(ENGINE / name)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
    helped = subprocess.run([BASH, str(ENGINE / "install-engine.sh"), "--help"], capture_output=True, text=True)
    assert helped.returncode == 0 and "--gpus 1,2|all|none" in helped.stdout


@pytest.mark.skipif(not BASH, reason="no bash")
def test_the_linux_installer_passes_the_answer_to_the_setup_question():
    call = line_with(ENGINE / "install-engine.sh", "vt gpu setup")
    for given, expect in (("", "gpu setup"), ("1,2", "gpu setup --gpus 1,2"), ("all", "gpu setup --gpus all"), ("none", "gpu setup --gpus none")):
        script = f'vt() {{ printf "%s " "$@"; echo; }}\nGPUS="{given}"\n{call}\n'
        out = subprocess.run([BASH, "-c", script], capture_output=True, text=True).stdout.strip()
        assert out == expect, (given, out)


@pytest.mark.skipif(not BASH, reason="no bash")
def test_the_installer_reads_the_flag_and_asks_before_anything_is_downloaded():
    text = (ENGINE / "install-engine.sh").read_text(encoding="utf-8")
    assert '--gpus) GPUS="$2"; shift 2 ;;' in text
    assert text.index("vt gpu setup") < text.index("vt engine plan") < text.index("vt engine setup")           # the cards are settled before an engine is installed or started


@pytest.mark.skipif(not BASH, reason="no bash")
def test_docker_applies_vt_gpus_and_goes_on_when_it_cannot():
    entry = (ENGINE / "docker-entrypoint.sh").read_text(encoding="utf-8")
    call = next(l.strip() for l in entry.splitlines() if "vt gpu setup" in l and not l.lstrip().startswith("#"))
    for given, expect in (("", "gpu setup"), ("1", "gpu setup --gpus 1"), ("0,1", "gpu setup --gpus 0,1")):
        script = f'vt() {{ printf "%s " "$@"; echo; }}\nVT_GPUS="{given}"\n{call}\n'
        assert subprocess.run([BASH, "-c", script], capture_output=True, text=True).stdout.strip() == expect, given
    failing = subprocess.run([BASH, "-c", f'vt() {{ return 2; }}\nVT_GPUS="9"\n{call}\necho went-on'], capture_output=True, text=True)
    assert failing.stdout.strip().endswith("went-on") and "starts with one card only" in failing.stdout          # a wrong VT_GPUS does not stop the container
    assert entry.index("vt gpu setup") < entry.index("exec vt engine run")
    assert "VT_GPUS" in (ENGINE / "docker-compose.yml").read_text(encoding="utf-8")


@pytest.mark.skipif(not POWERSHELL, reason="no PowerShell")
def test_the_windows_installer_parses_and_passes_the_answer_to_the_setup_question():
    path = str(ENGINE / "install-engine.ps1")
    parsed = subprocess.run([POWERSHELL, "-NoProfile", "-Command", f"$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$null, [ref]$e); if ($e) {{ $e | ForEach-Object {{ $_.Message }}; exit 1 }}"],
                            capture_output=True, text=True)
    assert parsed.returncode == 0, parsed.stdout + parsed.stderr
    text = Path(path).read_text(encoding="utf-8")
    assert "[string]$Gpus" in text and text.index("Vt gpu setup") < text.index("Vt engine plan") < text.index("Vt engine setup")
    snippet = "\n".join(l for l in text.splitlines() if l.startswith("$gpuArgs") or l.startswith("Vt gpu setup")).split("#")[0]
    snippet = "\n".join(re.sub(r"\s+#.*$", "", l) for l in snippet.splitlines())
    for given, expect in (("", "gpu setup"), ("1,2", "gpu setup --gpus 1,2"), ("none", "gpu setup --gpus none")):
        script = f'function Vt {{ ($args -join " ") }}\n$Gpus = "{given}"\n{snippet}\n'
        out = subprocess.run([POWERSHELL, "-NoProfile", "-Command", script], capture_output=True, text=True).stdout.strip()
        assert out == expect, (given, out)


def test_the_readme_tells_how_to_say_it_in_each_place():
    text = (ENGINE / "README-ENGINE.txt").read_text(encoding="utf-8")
    for word in ("--gpus", "-Gpus", "VT_GPUS", "vt gpu allow", "ONE card only"):
        assert word in text, word
    assert "WHICH GRAPHICS CARDS MAY VIDEO TOOL USE" in text
