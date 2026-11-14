"""Bounded atomic file operations for tool capabilities."""

import os
import re
import stat
import tempfile
from pathlib import Path

from research_loops.domain import IntegrityError


def confined(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative or relative.startswith("/"):
        raise IntegrityError("only relative POSIX paths are permitted")
    parts = relative.split("/")
    if any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts):
        raise IntegrityError("invalid artifact path")
    if any(re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p) for p in parts):
        raise IntegrityError("reserved Windows path")
    target = root
    for part in parts:
        target = target / part
        if target.is_symlink() or target.is_junction():
            raise IntegrityError("links/reparse points are forbidden")
        if target.exists() and getattr(target.stat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise IntegrityError("reparse points are forbidden")
    if not target.resolve().is_relative_to(root.resolve()):
        raise IntegrityError("path escapes workspace")
    return target


def atomic_write(path: Path, data: bytes, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            # Hard-link publication is atomic and refuses overwrites on both target OSes.
            os.link(tmp, path)
        else:
            os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)
