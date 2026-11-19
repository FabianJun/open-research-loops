"""Bounded atomic file operations for tool capabilities.

Windows long paths: wrap a path with long_path() only inside the file-system call itself
(long_path(p).read_bytes()). Never store, return, show or pass on the wrapped value: subprocess
arguments, working folders, container mounts and URIs get the plain path. Turn a resolve() result
back with plain_path(), and run the I/O scope under plain_io_errors() so error file names stay plain.
"""

import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from research_loops.domain import IntegrityError


_EXTENDED = "\\\\?\\"
_EXTENDED_UNC = _EXTENDED + "UNC\\"


def long_path(path: Path) -> Path:
    if os.name != "nt" or str(path).startswith(_EXTENDED):
        return path
    absolute = os.path.abspath(path)
    if absolute.startswith("\\\\.\\"):
        return Path(absolute)  # Device paths keep their own form.
    if absolute.startswith("\\\\"):
        return Path(_EXTENDED_UNC + absolute[2:])
    return Path(_EXTENDED + absolute)


def plain_path(path: Path) -> Path:
    if os.name == "nt":
        value = str(path)
        if value.upper().startswith(_EXTENDED_UNC):
            return Path("\\\\" + value[len(_EXTENDED_UNC):])
        if value.startswith(_EXTENDED) and value[len(_EXTENDED) + 1:len(_EXTENDED) + 2] == ":":
            return Path(value[len(_EXTENDED):])
    return path


@contextmanager
def plain_io_errors():
    # Preserve native error types and codes while keeping I/O-only paths private.
    try:
        yield
    except OSError as exc:
        for field in ("filename", "filename2"):
            name = getattr(exc, field)
            if isinstance(name, str) and name.startswith(_EXTENDED):
                setattr(exc, field, str(plain_path(Path(name))))
        raise


def refuse_link(path: Path) -> None:
    probe = long_path(path)
    if probe.is_symlink() or probe.is_junction():
        raise IntegrityError("links/reparse points are forbidden")
    if probe.exists() and getattr(probe.stat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise IntegrityError("reparse points are forbidden")


@plain_io_errors()
def confined(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative or relative.startswith("/"):
        raise IntegrityError("only relative POSIX paths are permitted")
    parts = relative.split("/")
    if any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts):
        raise IntegrityError("invalid artifact path")
    if any(re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p) for p in parts):
        raise IntegrityError("reserved Windows path")
    target = plain_path(root)
    for part in parts:
        target = target / part
        refuse_link(target)
    if not long_path(target).resolve().is_relative_to(long_path(root).resolve()):
        raise IntegrityError("path escapes workspace")
    return target


@plain_io_errors()
def atomic_write(path: Path, data: bytes, *, exclusive: bool = False) -> None:
    destination = long_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destination.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            # Hard-link publication is atomic and refuses overwrites on both target OSes.
            os.link(tmp, destination)
        else:
            os.replace(tmp, destination)
    finally:
        Path(tmp).unlink(missing_ok=True)
