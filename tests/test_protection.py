from pathlib import Path

import pytest

from research_loops.domain import IntegrityError, content_hash
from research_loops.protection import authorize_change, verify_anchor
from research_loops.storage import Repository


def test_anchor_and_spec_cannot_change_together_without_prior_decision():
    base = {"files": {"spec.py": "old"}}
    changed = {"files": {"spec.py": "new"}}
    with pytest.raises(IntegrityError, match="trusted base"):
        authorize_change(base, changed, [])
    authorize_change(base, changed, [{"old": content_hash(base), "new": content_hash(changed), "authority": "scaled-thinking", "reason": "approved revised threshold"}])
    assert verify_anchor()["files"]


def test_changed_migration_checksum_and_foreign_keys_are_rejected(tmp_path):
    import sqlite3
    root = tmp_path / "state"
    repo = Repository(root)
    assert repo.db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert repo.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    with pytest.raises(sqlite3.IntegrityError):
        repo.db.execute("INSERT INTO claims VALUES('bad','missing','statement','simulated','mse',NULL)")
    repo.db.rollback()
    with repo.db:
        repo.db.execute("UPDATE schema_migrations SET hash='tampered' WHERE number='001_slice.sql'")
    repo.close()
    with pytest.raises(IntegrityError, match="migration"):
        Repository(root)
