import hashlib
import os
from pathlib import Path
import re
import shlex

import pytest
from typer.core import TyperGroup, TyperOption
from typer.main import get_command
from typer.testing import CliRunner

from research_loops.cli import app
from research_loops import skills
from research_loops.domain import IntegrityError


@pytest.fixture(autouse=True)
def temporary_home(tmp_path, monkeypatch):
    home = tmp_path / "home space ü"
    monkeypatch.setattr(skills, "home_directory", lambda: home)
    return home


def test_skills_frontmatter_links_and_exposed_commands():
    root = skills.resources() / "skills"
    assert set(p.name for p in root.iterdir() if p.is_dir()) == set(skills.NAMES)
    for name in skills.NAMES:
        path = skills.skill_path(name) / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        fields = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
        assert fields["name"] == path.parent.name == name
        assert name.startswith("rloop-") and fields["description"].strip()
        assert len(text.splitlines()) < 80
        for link in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            assert not link.startswith(("http:", "https:"))
            assert (path.parent / link.split("#")[0]).is_file(), (name, link)
        for snippet in re.findall(r"`(rloop [^`]+)`", text):
            args = shlex.split(snippet)[1:]
            command = get_command(app)
            while isinstance(command, TyperGroup):
                assert args, snippet
                child = args.pop(0)
                assert child in command.commands, snippet
                command = command.commands[child]
            flags = {option for parameter in command.params if isinstance(parameter, TyperOption)
                for option in parameter.opts + parameter.secondary_opts}
            for arg in args:
                if arg.startswith("--"):
                    assert arg.split("=")[0] in flags, snippet


def test_show_hash_is_exact_and_stable():
    runner = CliRunner()
    listing = runner.invoke(app, ["skills", "list"])
    assert listing.exit_code == 0
    for name in skills.NAMES:
        data = (skills.skill_path(name) / "SKILL.md").read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        result = runner.invoke(app, ["skills", "show", name])
        assert result.exit_code == 0
        assert result.output == data.decode() + f"\nsha256:{sha}\n"
        assert runner.invoke(app, ["skills", "show", name]).output == result.output
        assert f"{name}  sha256:{sha}" in listing.output
    assert runner.invoke(app, ["skills", "show", "../../private"]).exit_code != 0


@pytest.mark.parametrize("target", ["claude", "agents", "both"])
def test_install_create_idempotent_and_platform_link(target, temporary_home):
    messages = skills.install(target)
    locations = ("claude", "agents") if target == "both" else (target,)
    assert len(messages) == len(skills.NAMES) * len(locations)
    before = []
    for location in locations:
        for name in skills.NAMES:
            path = temporary_home / f".{location}" / "skills" / name
            assert path.resolve() == skills.skill_path(name).resolve()
            assert path.is_junction() if os.name == "nt" else path.is_symlink()
            before.append(path.lstat().st_mtime_ns)
    assert all(message.startswith("unchanged ") for message in skills.install(target))
    after = [(temporary_home / f".{location}" / "skills" / name).lstat().st_mtime_ns
        for location in locations for name in skills.NAMES]
    assert before == after


@pytest.mark.parametrize("kind", ["file", "folder", "different_link", "dangling_link"])
def test_install_refuses_conflicts_without_partial_changes(kind, temporary_home, tmp_path):
    paths = [temporary_home / ".agents" / "skills" / skills.NAMES[-1],
        temporary_home / ".claude" / "skills" / skills.NAMES[-2]]
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "file":
            path.write_text("keep me", encoding="utf-8")
        elif kind == "folder":
            path.mkdir()
            (path / "sentinel").write_text("keep me", encoding="utf-8")
        else:
            other = tmp_path / f"other {index}"
            other.mkdir()
            skills.create_link(other, path)
            if kind == "dangling_link":
                other.rmdir()
    before = sorted(str(p.relative_to(temporary_home)) for p in temporary_home.rglob("*"))
    for dry_run in (False, True):
        with pytest.raises(IntegrityError) as caught:
            skills.install(dry_run=dry_run)
        assert all(str(path) in str(caught.value) for path in paths)
        assert before == sorted(str(p.relative_to(temporary_home)) for p in temporary_home.rglob("*"))
        result = CliRunner().invoke(app, ["skills", "install", *(["--dry-run"] if dry_run else [])])
        assert result.exit_code != 0 and "nothing changed" in result.output


def test_dry_run_never_creates_home(temporary_home):
    result = CliRunner().invoke(app, ["skills", "install", "--target", "both", "--dry-run"])
    assert result.exit_code == 0 and result.output.count("would link") == 2 * len(skills.NAMES)
    assert not temporary_home.exists()


def test_parent_file_conflict_is_preflighted(temporary_home):
    temporary_home.mkdir()
    (temporary_home / ".agents").write_text("keep", encoding="utf-8")
    with pytest.raises(IntegrityError, match="nothing changed"):
        skills.install()
    assert not (temporary_home / ".claude").exists()


def test_link_failure_rolls_back_created_links_and_directories(monkeypatch, temporary_home):
    actual = skills.create_link
    count = 0
    def fail_second(source, target):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("test failure")
        actual(source, target)
    monkeypatch.setattr(skills, "create_link", fail_second)
    with pytest.raises(OSError, match="test failure"):
        skills.install()
    assert not temporary_home.exists()
