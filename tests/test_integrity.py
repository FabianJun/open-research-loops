import asyncio
import json
import os
import sqlite3
import sys

import pytest
from pydantic import ValidationError

from research_loops.coordinator import prepare
from research_loops.domain import IntegrityError, Limits, WorkerContract, Workspace, canonical, digest
from research_loops.fake import FakeBackend
from research_loops.grounding import Statement, number, public_context, quote
from research_loops.locking import ProjectLock
from research_loops.paths import confined
from research_loops.reporting import export
from research_loops.storage import Repository


def assignment(repo, key, run_id="case"):
    return WorkerContract(run_id=run_id, registration_hash=key, goal="Recover signal", prediction="wrong candidate fails", seed=7, variant=0, input_hash="a" * 64)


def test_registration_is_immutable_and_required(example):
    repo, contract, key = prepare(example)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            repo.db.execute("UPDATE registrations SET payload='{}'")
        with pytest.raises(sqlite3.IntegrityError):
            repo.db.execute("DELETE FROM registrations")
        repo.db.rollback()
        with pytest.raises(IntegrityError, match="registration"):
            repo.dispatch(assignment(repo, "unregistered"))
        assert repo.db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
    finally:
        repo.close()


def test_import_is_true_noop_and_seals_evidence(example):
    repo, contract, key = prepare(example)
    work = Workspace(root=repo.root / "runs" / "case" / "outbox")
    try:
        task = assignment(repo, key)
        repo.dispatch(task)
        result = asyncio.run(FakeBackend().run(task, work, Limits()))
        repo.import_report(result, work)
        before = list(repo.db.iterdump())
        os.utime(work.root / "candidate.json", (1, 1))
        assert not repo.import_report(result, work)
        assert list(repo.db.iterdump()) == before
        (work.root / "candidate.json").write_text("{}")
        assert repo.artifact("case", "candidate") != b"{}"
        with pytest.raises(IntegrityError, match="conflicting"):
            repo.import_report(result.model_copy(update={"seed": 99}), work)
    finally:
        repo.close()


def test_tampered_artifact_never_imports(example):
    repo, _, key = prepare(example)
    work = Workspace(root=repo.root / "runs" / "case" / "outbox")
    try:
        task = assignment(repo, key)
        repo.dispatch(task)
        result = asyncio.run(FakeBackend().run(task, work, Limits()))
        (work.root / "candidate.json").write_bytes(b"{}")
        with pytest.raises(IntegrityError, match="hash"):
            repo.import_report(result, work)
        assert not repo.db.execute("SELECT report_hash FROM runs").fetchone()[0]
    finally:
        repo.close()


@pytest.mark.parametrize("path", ["../other", "/private", "C:/secret", "C:secret", "\\\\server\\share", "a/../../x", "a//x", "a/./x", "NUL", "file:stream", "x."])
def test_path_traversal_refused(tmp_path, path):
    with pytest.raises(IntegrityError):
        confined(tmp_path, path)


def test_links_refused(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    link = tmp_path / "root" / "linked"
    link.parent.mkdir()
    if os.name == "nt":
        import subprocess
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    with pytest.raises(IntegrityError):
        confined(link.parent, "linked/x")


def test_lock_excludes_second_coordinator(tmp_path):
    with ProjectLock(tmp_path):
        with pytest.raises(IntegrityError, match="coordinator"):
            with ProjectLock(tmp_path):
                pass
    with ProjectLock(tmp_path):
        pass


def test_grounding_and_tags():
    quote(b"An exact source passage.", "exact source")
    with pytest.raises(IntegrityError):
        quote(b"An exact source passage.", "Exact source")
    number(1.25, "1.25")
    with pytest.raises(IntegrityError):
        number(1.25, "1.24")
    with pytest.raises(ValidationError):
        Statement(text="result", tag="proven")


def test_public_projection_has_no_private_fields(example):
    repo, _, key = prepare(example)
    try:
        payload = assignment(repo, key).model_dump(mode="json")
        public_context(payload)
        with pytest.raises(IntegrityError):
            public_context({**payload, "holdout": "PRIVATE-CANARY"})
        work = Workspace(root=repo.root / "runs" / "case" / "outbox")
        result = asyncio.run(FakeBackend().run(assignment(repo, key), work, Limits()))
        transcript = (work.root / "transcript.json").read_bytes()
        assert b"PRIVATE-CANARY" not in transcript
        assert not any(name in sys.modules for name in ("agents", "claude_agent_sdk", "openai"))
    finally:
        repo.close()


def test_export_is_prefix_checked(example):
    repo, _, key = prepare(example)
    try:
        path = export(repo)
        original = path.read_bytes()
        repo.dispatch(assignment(repo, key))
        export(repo)
        assert path.read_bytes().startswith(original)
        path.write_bytes(path.read_bytes()[:-1])
        with pytest.raises(IntegrityError, match="torn"):
            export(repo)
    finally:
        repo.close()
