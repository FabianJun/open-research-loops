import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tomllib

import pytest


@pytest.fixture(scope="session")
def offline_uv_cache(tmp_path_factory):
    """Copy cached base/dev/build inputs; uv may only mutate the temporary copy."""
    source = Path(subprocess.check_output(["uv", "cache", "dir"], text=True).strip())
    target = tmp_path_factory.mktemp("guide-uv-cache")
    shutil.copytree(source / "simple-v21", target / "simple-v21")
    lock = tomllib.loads((Path(__file__).parents[1] / "uv.lock").read_text(encoding="utf-8"))
    packages = {package["name"]: package for package in lock["package"]}
    pending = ["research-loops", "pytest"]
    names = {"hatchling", "editables", "packaging", "pathspec", "tomlkit", "trove-classifiers"}
    while pending:
        name = pending.pop()
        if name in names:
            continue
        names.add(name)
        pending.extend(dependency["name"] for dependency in packages[name].get("dependencies", []))
    for name in names:
        cached = source / "wheels-v6" / "pypi" / name
        if not cached.is_dir():
            continue
        shutil.copytree(cached, target / "wheels-v6" / "pypi" / name)
        for entry in cached.iterdir():
            if entry.is_symlink():
                archive = entry.resolve()
            elif entry.is_file() and not entry.suffix in (".http", ".msgpack", ".lock"):
                pointer = entry.read_text(encoding="utf-8").strip()
                archive = source / pointer
            else:
                continue
            if archive.is_dir() and archive.parent.name == "archive-v0":
                shutil.copytree(archive, target / "archive-v0" / archive.name, dirs_exist_ok=True)
    return target


def test_guide_offline_sequence_in_temporary_checkout(tmp_path, offline_uv_cache):
    source = Path(__file__).parents[1]
    checkout = tmp_path / "checkout space ü"
    checkout.mkdir()
    for name in ("src", "skills", "docs"):
        shutil.copytree(source / name, checkout / name, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("pyproject.toml", "uv.lock", "README.md", "LICENSE", "LICENSE-CC-BY-4.0"):
        shutil.copyfile(source / name, checkout / name)
    record = Path("experiments/grain-cnn/README.md")
    (checkout / record).parent.mkdir(parents=True)
    shutil.copyfile(source / record, checkout / record)
    env = {**os.environ, "UV_OFFLINE": "1", "UV_CACHE_DIR": str(offline_uv_cache), "UV_PYTHON": sys.executable, "PYTHONUTF8": "1",
        "UV_PROJECT_ENVIRONMENT": str(tmp_path / "guide-venv"),
        "HOME": str(tmp_path / "guide-home"), "USERPROFILE": str(tmp_path / "guide-home")}
    text = (source / "docs/GUIDE.md").read_text(encoding="utf-8")
    commands = [line for block in re.findall(r"```sh\n(.*?)```", text, re.S) for line in block.strip().splitlines()]
    assert commands
    for command in commands:
        result = subprocess.run(shlex.split(command), cwd=checkout, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert result.returncode == 0, (command, result.stdout, result.stderr)
    root = checkout / "research-demo/.rloop"
    assert "public-ready: needs human review" in (root / "self-assessment.md").read_text(encoding="utf-8")
    assert not (tmp_path / "guide-home/.claude").exists()
    assert not (tmp_path / "guide-home/.agents").exists()
