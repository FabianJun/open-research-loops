import asyncio
import os
import shutil
from pathlib import Path

import pytest

from research_loops import coordinator
from research_loops.domain import IntegrityError
from research_loops.paths import atomic_write, confined, long_path, plain_path


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
    folder = Path(str(folder) + "x" * (length - len(str(folder))))
    assert len(str(folder)) == length
    return folder


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
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(long_path(outside)), str(long_path(link)))
        assert long_path(link).is_junction()
    else:
        link.symlink_to(outside, target_is_directory=True)
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


def windows_long_paths_enabled():
    """Read the host's LongPathsEnabled setting (read-only); a missing value counts as off."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
    except OSError:
        return False
    return value == 1


@pytest.mark.parametrize("value, expected", [(0, False), (1, True), (None, False)])
def test_windows_long_paths_enabled_reads_registry(monkeypatch, value, expected):
    import sys
    import types
    from contextlib import nullcontext

    def query(key, name):
        assert name == "LongPathsEnabled"
        if value is None:
            raise FileNotFoundError(name)
        return value, 4

    fake = types.SimpleNamespace(
        HKEY_LOCAL_MACHINE="HKLM",
        OpenKey=lambda root, path: nullcontext((root, path)),
        QueryValueEx=query,
    )
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert windows_long_paths_enabled() is expected


@pytest.mark.parametrize("length", [199, 230])
def test_grain_data_under_deep_root(tmp_path, length):
    pytest.importorskip("skimage")
    from test_grain import fixture_zip
    from research_loops.contracts import GrainContract
    from research_loops.domain import canonical
    from research_loops.evaluation import SubprocessEvaluator
    from research_loops.grain_data import _fetch_verified_archive

    project = deep_folder(tmp_path, length)
    long_path(project).mkdir(parents=True)
    long_path(project / "contract.json").write_text(canonical(GrainContract()), encoding="utf-8")
    archive = tmp_path / "fixture.zip"
    expected = fixture_zip(archive)
    data_root = project / ".rloop/data/Grain/val"
    if os.name != "nt" or length < 200 or windows_long_paths_enabled():
        _fetch_verified_archive(project, archive, expected, dict(train=3, val=3, test=3))
        manifest = long_path(project / ".rloop/data/val.json").read_bytes()
        assert SubprocessEvaluator().evaluate(b"{}", manifest, 300, data_root=data_root)
        return
    # Windows with long paths off: the protected evaluator keeps plain paths,
    # so deeper grain data stops with an error.
    with pytest.raises(IntegrityError, match="evaluator process failed"):
        _fetch_verified_archive(project, archive, expected, dict(train=3, val=3, test=3))
    manifest = long_path(project / ".rloop/data/val.json").read_bytes()
    with pytest.raises(IntegrityError, match="evaluator process failed"):
        SubprocessEvaluator().evaluate(b"{}", manifest, 300, data_root=data_root)
