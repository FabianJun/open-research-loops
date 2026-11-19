import asyncio
import os
import shutil
from pathlib import Path

import pytest

from research_loops import coordinator
from research_loops.domain import IntegrityError
from research_loops.paths import atomic_write, confined, long_path, plain_path, sqlite_uri


def test_prepare_and_resume_deep_project(tmp_path):
    example = tmp_path / "research space ü"
    while len(str(example / "planted-signal")) < 200:
        example /= "nested-project-folder"
    example /= "planted-signal"
    long_path(example).mkdir(parents=True)
    shutil.copyfile(Path(__file__).parents[1] / "examples/planted-signal/contract.json",
                    long_path(example / "contract.json"))

    repo, _, key = coordinator.prepare(example)
    try:
        private_dir = example / ".rloop" / "private" / key
        development = private_dir / "development.json"
        assert len(str(development)) > 260
        assert len(str(private_dir / ".pending-XXXXXXXX")) > 260
        assert repo.root == example / ".rloop"
        assert confined(repo.root, f"private/{key}/development.json") == development
        assert coordinator.private(repo, key, "training")
        data = coordinator.private(repo, key, "development")
        assert data
        with pytest.raises(FileExistsError) as exc:
            atomic_write(development, data, exclusive=True)
        assert str(development) == exc.value.filename2
        assert not any(long_path(private_dir).glob(".pending-*"))
    finally:
        repo.close()

    repo, _, resumed_key = coordinator.prepare(example)
    try:
        assert resumed_key == key
    finally:
        repo.close()


def deep_folder(base, length):
    """A plain path of exactly `length` characters below `base`."""
    folder = base / "p"
    while length - len(str(folder)) > 100:
        folder /= "x" * 99  # Keep every component below the 255-character name limit.
    folder = Path(str(folder) + "x" * (length - len(str(folder))))
    assert len(str(folder)) == length
    return folder


def directory_link(target, link):
    if os.name == "nt":
        import _winapi
        # CreateJunction adds its own prefix to the target.
        _winapi.CreateJunction(str(target), str(long_path(link)))
        assert long_path(link).is_junction()
    else:
        link.symlink_to(target, target_is_directory=True)


def test_run_report_and_export_deep_project(tmp_path):
    from research_loops.reporting import export, report
    from research_loops.storage import Repository

    example = deep_folder(tmp_path, 200)
    long_path(example).mkdir(parents=True)
    shutil.copyfile(Path(__file__).parents[1] / "examples/planted-signal/contract.json",
                    long_path(example / "contract.json"))
    asyncio.run(coordinator.run(example))
    repo = Repository(example / ".rloop")
    try:
        assert len(repo.runs()) == 48
        report(repo, check=True)
        export(repo)
    finally:
        repo.close()
    asyncio.run(coordinator.run(example))


def test_confinement_under_deep_root(tmp_path):
    root = tmp_path / "root"
    while len(str(root / "linked")) <= 260:
        root /= "nested-project-folder"
    outside = tmp_path / "outside"
    long_path(root).mkdir(parents=True)
    outside.mkdir()
    link = root / "linked"
    directory_link(outside, link)
    for relative in ("../x", "inner/../../x", "linked/x", "linked/inner/x", "linked/../x"):
        with pytest.raises(IntegrityError):
            confined(root, relative)
    assert confined(root, "inner/x") == root / "inner" / "x"


def test_long_path():
    relative = Path("folder") / ".." / "file"
    extended = long_path(relative)
    assert long_path(extended) is extended
    unc = Path(r"\\server\share\folder\..\file")
    if os.name == "nt":
        assert str(extended) == "\\\\?\\" + os.path.abspath(relative)
        assert str(long_path(unc)) == r"\\?\UNC\server\share\file"
        assert plain_path(long_path(unc)) == Path(r"\\server\share\file")
        assert plain_path(extended) == Path(os.path.abspath(relative))
        assert str(long_path(Path(r"\\.\pipe\x"))) == r"\\.\pipe\x"
        volume = Path(r"\\?\Volume{00000000-0000-0000-0000-000000000000}\x")
        assert plain_path(volume) is volume
    else:
        assert extended is relative
        assert long_path(unc) is unc


@pytest.mark.parametrize("length, linked_host", [(199, False), (230, False), (300, False), (199, True)])
def test_grain_data_under_deep_root(tmp_path, length, linked_host):
    pytest.importorskip("skimage")
    from test_grain import fixture_zip
    from research_loops.contracts import GrainContract
    from research_loops.domain import canonical
    from research_loops.evaluation import SubprocessEvaluator
    from research_loops.grain_data import _fetch_verified_archive

    base = tmp_path
    if linked_host:
        target = tmp_path / "host-target"
        target.mkdir()
        base = tmp_path / "host-folder"
        directory_link(target, base)
    project = deep_folder(base, length)
    long_path(project).mkdir(parents=True)
    long_path(project / "contract.json").write_text(canonical(GrainContract()), encoding="utf-8")
    archive = tmp_path / "fixture.zip"
    expected = fixture_zip(archive)
    data_root = project / ".rloop/data/Grain/val"
    _fetch_verified_archive(project, archive, expected, dict(train=3, val=3, test=3))
    manifest = long_path(project / ".rloop/data/val.json").read_bytes()
    assert SubprocessEvaluator().evaluate(b"{}", manifest, 300, data_root=data_root).n_images == 3


def test_fake_grain_campaign_under_deep_root(tmp_path, monkeypatch):
    pytest.importorskip("skimage")
    import json
    from typer.testing import CliRunner
    from test_grain import fixture_zip
    from research_loops import grain_worker
    from research_loops.assessment import assess
    from research_loops.cli import app
    from research_loops.contracts import GrainContract
    from research_loops.domain import canonical
    from research_loops.grain_data import _fetch_verified_archive
    from research_loops.grain_evaluator import TEAM_FINAL, evaluate
    from research_loops.storage import ReadOnlyRepository

    project = deep_folder(tmp_path, 250)  # The training data root is beyond 260 characters.
    long_path(project).mkdir(parents=True)
    long_path(project / "contract.json").write_text(canonical(GrainContract()), encoding="utf-8")
    archive = tmp_path / "fixture.zip"
    _fetch_verified_archive(project, archive, fixture_zip(archive), dict(train=3, val=3, test=3))
    manifest = json.loads(long_path(project / ".rloop/data/val.json").read_bytes())
    expected = tuple(evaluate(dict(domain="grain-316l", candidate=params, manifest=manifest,
        data_root=str(project / ".rloop/data/Grain/val"))).max_rel_error for params in ({}, TEAM_FINAL))
    monkeypatch.setattr(grain_worker, "control_expectations", lambda: expected)
    runner = CliRunner()
    for args in (["init", str(project), "--owner", "Fixture Owner"], ["plan", str(project)],
            ["run", str(project)], ["report", str(project), "--check"], ["run", str(project), "--final"],
            ["report", str(project), "--check"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.output, result.exception)
    assert "FAIL" not in assess(project)
    snapshot = ReadOnlyRepository(project / ".rloop")
    try:
        assert snapshot.runs()
    finally:
        snapshot.close()
    tools = list(long_path(project / ".rloop").rglob("training-tool.json"))
    assert tools
    for path in tools:
        root = json.loads(path.read_bytes())["data_root"]
        assert len(root) > 260 and root == str(plain_path(Path(root)))
    assert "Final holdout max_rel_error" in long_path(project / ".rloop/report.md").read_text(encoding="utf-8")
    # The assessment re-check refuses a linked data folder.
    moved = tmp_path / "moved-grain"
    os.replace(long_path(project / ".rloop/data/Grain"), long_path(moved))
    directory_link(moved, project / ".rloop/data/Grain")
    assessment = assess(project)
    assert "FAIL" in assessment and "links/reparse points are forbidden: .rloop/data/Grain" in assessment, assessment


@pytest.mark.parametrize("component", ["Grain", "train"])
@pytest.mark.parametrize("consumer", ["evaluation", "training"])
def test_grain_data_root_refuses_links(tmp_path, monkeypatch, component, consumer):
    from types import SimpleNamespace

    from research_loops.evaluation import SubprocessEvaluator
    from research_loops.grain_worker import prepare_training_tool

    root = tmp_path / ".rloop"
    data_root = root / "data/Grain/train"
    link = data_root.parent if component == "Grain" else data_root
    link.parent.mkdir(parents=True)
    target = tmp_path / "data-target"
    (target / "train").mkdir(parents=True)
    directory_link(target, link)
    manifest = b'{"domain":"grain-316l","split":"train","images":[]}'
    run_root = tmp_path / "run"
    if consumer == "training":
        monkeypatch.setattr(coordinator, "private", lambda *_: manifest)
        # Exercise the training check independently of the coordinator's check.
        monkeypatch.setattr(coordinator, "data_root", lambda *_: data_root)
    else:
        monkeypatch.setattr("research_loops.evaluation.supervised",
            lambda *args, **kwargs: pytest.fail("evaluator process started"))
    with pytest.raises(IntegrityError, match=rf"links.*{component}"):
        if consumer == "training":
            prepare_training_tool(SimpleNamespace(root=root), None, None, run_root)
        else:
            SubprocessEvaluator().evaluate(b"{}", manifest, 300, data_root=data_root)
    assert not run_root.exists()


def test_sqlite_uri_escapes_names(tmp_path):
    import sqlite3

    folder = tmp_path / ("a b#%ü" + ("" if os.name == "nt" else "?x"))
    folder.mkdir()
    database = folder / "state.sqlite"
    writer = sqlite3.connect(database)
    writer.execute("CREATE TABLE t (x)")
    writer.commit()
    writer.close()
    reader = sqlite3.connect(sqlite_uri(database) + "?mode=ro", uri=True)
    try:
        assert reader.execute("SELECT count(*) FROM t").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.execute("INSERT INTO t VALUES (1)")
    finally:
        reader.close()
