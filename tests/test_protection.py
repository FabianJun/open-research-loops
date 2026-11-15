from pathlib import Path
import json
import subprocess
import sys

import pytest

from research_loops.domain import IntegrityError, content_hash
from research_loops.protection import authorize_change, verify_anchor
from research_loops.storage import Repository


def test_anchor_and_spec_cannot_change_together_without_prior_decision():
    owner = {"name": "Ada", "source": "argument"}
    base = {"anchor": {"files": {"spec.py": "old"}}, "owner": owner}
    changed = {"anchor": {"files": {"spec.py": "new"}}, "owner": owner}
    with pytest.raises(IntegrityError, match="trusted base"):
        authorize_change(base, changed, [])
    authorize_change(base, changed, [{"old": content_hash(base), "new": content_hash(changed), "authority": " Ada ", "reason": "approved revised threshold"}])
    assert verify_anchor()["files"]


@pytest.mark.parametrize("authority", ["Mallory", "ada"])
def test_owner_substitution_cannot_authorize_same_change(authority):
    base = {"anchor": {"files": {"spec.py": "old"}}, "owner": {"name": "Ada", "source": "argument"}}
    changed = {"anchor": {"files": {"spec.py": "new"}}, "owner": {"name": "Mallory", "source": "argument"}}
    forged = {"old": content_hash(base), "new": content_hash(changed), "authority": authority,
        "reason": "I changed the owner to myself, so approve my anchor"}
    with pytest.raises(IntegrityError, match="trusted base"):
        authorize_change(base, changed, [forged])


@pytest.mark.parametrize("authority,prior_decision,accepted", [("Mallory", True, False), ("Ada", False, False), ("Ada", True, True)])
def test_protected_script_reads_owner_and_decision_only_from_git_base(tmp_path, authority, prior_decision, accepted):
    script = Path(__file__).parents[1] / "scripts/check_protected.py"
    manifest = {"files": {"spec.py": "old"}}
    base_owner = {"name": "Ada", "source": "argument"}
    changed_owner = {"name": "Mallory", "source": "argument"}
    decision = {"old": content_hash({"anchor": manifest, "owner": base_owner}),
        "new": content_hash({"anchor": verify_anchor(), "owner": changed_owner}),
        "authority": authority, "reason": "explicitly approved policy and owner amendment"}
    path = tmp_path / "src/research_loops/evaluator-manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest))
    config = tmp_path / "project.json"
    config.write_text(json.dumps({"owner": base_owner, "evaluator_authorizations": [decision] if prior_decision else []}))
    def git(*args):
        return subprocess.run(["git", "-c", "user.name=Test Owner", "-c", "user.email=owner@example.invalid",
            "-c", "commit.gpgsign=false", "-c", f"core.hooksPath={tmp_path / 'no-hooks'}", *args],
            cwd=tmp_path, capture_output=True, text=True, check=True)
    git("init")
    git("add", ".")
    git("commit", "-m", "Record trusted owner and decisions")
    # Substitute the owner and add an apparently matching decision in this change.
    config.write_text(json.dumps({"owner": changed_owner, "evaluator_authorizations": [decision]}))
    result = subprocess.run([sys.executable, str(script), "--base", "HEAD"], cwd=tmp_path, capture_output=True, text=True)
    assert (result.returncode == 0) is accepted, result.stderr
    if not accepted:
        assert "trusted base" in result.stderr


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
