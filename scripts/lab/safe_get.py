"""Download a file over SFTP without ever damaging the local copy.

paramiko's `sftp.get(remote, local)` opens `local` for writing before it opens `remote`, so a missing remote file left a zero-byte local
file behind: three finished MP4s were destroyed that way (2026-11-03). Here the remote file is checked first, the bytes go to a separate
`.part` file, the size is verified, and only then the destination is replaced. A missing remote raises FileNotFoundError and leaves the
local file exactly as it was.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path


def safe_get(sftp, remote: str, local) -> Path:
    local = Path(local)
    info = sftp.stat(remote)                               # FileNotFoundError when it is not there: nothing local has been touched
    if stat.S_ISDIR(info.st_mode):
        raise IsADirectoryError(remote)
    local.parent.mkdir(parents=True, exist_ok=True)
    part = local.with_name(local.name + ".part")
    try:
        sftp.get(remote, str(part))
        got = part.stat().st_size
        if got != info.st_size:
            raise IOError(f"{remote}: got {got} bytes, expected {info.st_size}")
        os.replace(part, local)                            # atomic on the same disk: the old copy is replaced only by a complete one
    finally:
        if part.exists():
            part.unlink()
    return local
