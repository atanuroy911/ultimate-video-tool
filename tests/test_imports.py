"""Every module and the CLI must import cleanly (a syntax error in a rarely-tested file once went unnoticed)."""
import importlib
import pkgutil

import vt


def test_every_module_imports():
    failed = []
    for m in pkgutil.walk_packages(vt.__path__, "vt."):
        try:
            importlib.import_module(m.name)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{m.name}: {e!r}")
    assert not failed, failed


def test_cli_commands_load():
    from typer.testing import CliRunner

    from vt.cli import app

    r = CliRunner().invoke(app, ["--help"])
    assert r.exit_code == 0 and "doctor" in r.output and "render" in r.output
    r = CliRunner().invoke(app, ["themes"])
    assert r.exit_code == 0 and "paper" in r.output
