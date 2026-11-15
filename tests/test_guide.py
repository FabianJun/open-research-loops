import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


def test_guide_offline_sequence_in_temporary_checkout(tmp_path):
    source = Path(__file__).parents[1]
    checkout = tmp_path / "checkout space ü"
    checkout.mkdir()
    for name in ("src", "skills", "docs"):
        shutil.copytree(source / name, checkout / name, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("pyproject.toml", "uv.lock", "README.md", "LICENSE", "LICENSE-CC-BY-4.0"):
        shutil.copyfile(source / name, checkout / name)
    cache = subprocess.check_output(["uv", "cache", "dir"], text=True).strip()
    env = {**os.environ, "UV_OFFLINE": "1", "UV_CACHE_DIR": cache, "UV_PYTHON": sys.executable, "PYTHONUTF8": "1",
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
