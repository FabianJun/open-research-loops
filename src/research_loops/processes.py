"""Supervise trusted evaluator trees; this is not a candidate-code sandbox."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from research_loops.domain import IntegrityError


def _kernel():
    from ctypes import wintypes as w
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes, api.CreateJobObjectW.restype = [ctypes.c_void_p, w.LPCWSTR], w.HANDLE
    api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    api.CloseHandle.argtypes = [w.HANDLE]
    api.OpenProcess.argtypes, api.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    api.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
    api.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    return api


def process_identity(pid: int) -> str | None:
    """Creation identity, not just PID. Permission errors remain unknown."""
    if os.name == "nt":
        from ctypes import wintypes as w
        api = _kernel()
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() in (87, 1168):
                return None
            raise IntegrityError("process identity unavailable")
        try:
            code = w.DWORD()
            if not api.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise IntegrityError("process liveness unavailable")
            if code.value != 259:
                return None
            times = [w.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
                raise IntegrityError("process creation time unavailable")
            return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            api.CloseHandle(handle)
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return fields[19]
    except (FileNotFoundError, ProcessLookupError):
        return None
    except OSError as exc:
        raise IntegrityError("process identity unavailable") from exc


class WindowsJob:
    def __init__(self, process: subprocess.Popen):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64), ("flags", w.DWORD),
                ("min_working", ctypes.c_size_t), ("max_working", ctypes.c_size_t), ("active", w.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ro", "wo", "oo", "rb", "wb", "ob")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
        self.api = _kernel()
        self.handle = self.api.CreateJobObjectW(None, None)
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)) or not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            process.kill()
            process.wait()
            if self.handle:
                self.api.CloseHandle(self.handle)
            raise IntegrityError("cannot establish evaluator Job Object")

    def close(self) -> None:
        self.api.CloseHandle(self.handle)


def supervised(command: list[str], payload: bytes, seconds: float, *, cwd: Path | None = None,
               started: Callable[[dict], None] | None = None) -> bytes:
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG"}}
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
            cwd=cwd, env=env, start_new_session=os.name != "nt")
        job = WindowsJob(process) if os.name == "nt" else None
        try:
            if started:
                started({"pid": process.pid, "creation": process_identity(process.pid)})
            # Trusted evaluator reads stdin before doing work, after containment is established.
            process.communicate(payload, timeout=seconds)
            if process.returncode:
                raise IntegrityError(f"evaluator process failed (exit {process.returncode})")
            stdout.seek(0)
            output = stdout.read(1_000_001)
            if not output or len(output) > 1_000_000:
                raise IntegrityError("empty/oversized evaluator output")
            return output
        except subprocess.TimeoutExpired as exc:
            raise IntegrityError("evaluator timed out") from exc
        finally:
            if job:
                job.close()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
