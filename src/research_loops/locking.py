"""A kernel-backed single-coordinator lock; stale lock files are harmless."""

import os
from pathlib import Path

from research_loops.domain import IntegrityError
from research_loops.paths import long_path, plain_io_errors


class ProjectLock:
    def __init__(self, root: Path):
        self.path = root / "coordinator.lock"
        self.stream = None

    @plain_io_errors()
    def __enter__(self):
        path = long_path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)

        def opener(_, flags):
            return os.open(path, flags, 0o666)

        # Keep the stream's name plain while its opener uses the I/O path.
        self.stream = open(self.path, "a+b", opener=opener)
        if os.fstat(self.stream.fileno()).st_size == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise IntegrityError("another coordinator owns this project") from exc
        return self

    def __exit__(self, *_):
        if self.stream:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
