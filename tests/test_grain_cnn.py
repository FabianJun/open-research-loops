"""Offline experiment checks using synthetic val pixels only; no torch needed."""

import ast
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("PIL") is None:
    pytest.skip("install research-loops[grain] for grain CNN tests", allow_module_level=True)

import numpy as np
from PIL import Image

from research_loops.domain import IntegrityError
from research_loops import grain_evaluator


EXPERIMENT = Path(__file__).parents[1] / "experiments/grain-cnn"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def trainer(monkeypatch):
    original = builtins.__import__

    def without_torch(name, *args, **kwargs):
        if name.split(".")[0] == "torch":
            raise AssertionError("helpers must import without torch")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_torch)
    return load_script("train_unet")


@pytest.mark.parametrize("name", [
    "Grain/train/images/a.png", "Grain/train/images/b.jpg",
    "Grain/train/masks/b.png", "Grain/val/images/a.png",
    "Grain/val/images/b.jpg", "Grain/val/masks/b.png",
])
def test_cnn_member_allowlist(trainer, name):
    assert trainer.allowed_member(name)


@pytest.mark.parametrize("name", [
    "Grain/test/images/a.png", "Grain/test/masks/a.png", "Grain/test/",
    "Grain/train/../test/images/a.png", "Grain/train/images/../../test/a.png",
    "/Grain/val/images/a.png", "Grain\\val\\images\\a.png",
    "Grain/val/images//a.png", "Grain/val/images/./a.png",
    "Grain/val/masks/a.jpg", "Grain/val/images/a.png/",
    "Grain/val/images/C:a.png", "Grain/val/images/a\x00.png",
])
def test_cnn_member_rejection(trainer, name):
    # Strings only: no files from a forbidden split are created, listed or opened.
    assert not trainer.allowed_member(name)


def test_cnn_training_split(trainer):
    names = [f"image-{i:03}" for i in range(611)]
    before = random.getstate()
    fit, check = trainer.split_training(reversed(names))
    assert random.getstate() == before
    assert len(fit) == 551 and len(check) == 60
    assert not set(fit) & set(check)
    assert set(fit) | set(check) == set(names)
    assert (fit, check) == trainer.split_training(names)
    shuffled = names.copy()
    random.Random(0).shuffle(shuffled)
    assert fit == sorted(shuffled[:551])
    assert check == sorted(shuffled[551:])
    with pytest.raises(ValueError, match="611 unique"):
        trainer.split_training(names[:-1])
    with pytest.raises(ValueError, match="611 unique"):
        trainer.split_training([names[0]] * 611)


def test_cnn_output_directory_precedence(trainer, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RLOOP_OUTPUT_DIR", raising=False)
    original = Path.is_dir
    kaggle_available = False

    def directory(path):
        if path == Path("/kaggle/working"):
            return kaggle_available
        return original(path)

    monkeypatch.setattr(Path, "is_dir", directory)
    assert trainer.resolve_output_dir() == tmp_path / "out"
    kaggle_available = True
    assert trainer.resolve_output_dir() == Path("/kaggle/working")
    monkeypatch.setenv("RLOOP_OUTPUT_DIR", str(tmp_path / "environment"))
    assert trainer.resolve_output_dir() == tmp_path / "environment"
    assert trainer.resolve_output_dir(tmp_path / "explicit") == tmp_path / "explicit"


def test_cnn_job_data_provenance():
    from research_loops.grain_data import ARCHIVE_SIZE, ARCHIVE_URL
    from research_loops.compute.core import package
    job = package(EXPERIMENT)
    contract = json.loads((EXPERIMENT.parents[1] / "examples/grain-316l/contract.json").read_bytes())
    assert job.spec.entry == "train_unet.py" and job.spec.smoke_args == ["--smoke"]
    assert job.spec.outputs == ["val_labels.npz", "run.json"]
    assert job.spec.data[0].model_dump() == dict(url=ARCHIVE_URL, size=ARCHIVE_SIZE,
        sha256=contract["archive_sha256"])


def test_cnn_metric_is_verbatim(trainer):
    original = ast.parse(Path(grain_evaluator.__file__).read_text(encoding="utf-8"))
    copied = ast.parse((EXPERIMENT / "train_unet.py").read_text(encoding="utf-8"))
    for name in ("measure", "truth", "score"):
        left = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == name)
        right = next(node for node in copied.body if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(left) == ast.dump(right)


@pytest.mark.parametrize("field", ["ARCHIVE_SIZE", "ARCHIVE_MD5", "ARCHIVE_SHA256"])
def test_cnn_hash_failure_precedes_zip_open(trainer, tmp_path, monkeypatch, field):
    archive = tmp_path / "fixture.zip"
    raw = b"not even a zip"
    archive.write_bytes(raw)
    monkeypatch.setattr(trainer, "ARCHIVE_SIZE", len(raw))
    monkeypatch.setattr(trainer, "ARCHIVE_MD5", hashlib.md5(raw).hexdigest())
    monkeypatch.setattr(trainer, "ARCHIVE_SHA256", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(trainer, field, 0 if field.endswith("SIZE") else "incorrect")

    def forbidden(*args, **kwargs):
        pytest.fail("opened zip before verifying all archive facts")

    monkeypatch.setattr(trainer.zipfile, "ZipFile", forbidden)
    with pytest.raises(ValueError, match="size/md5/sha256"):
        trainer.extract_selected(archive, tmp_path / "data")
    assert not (tmp_path / "data").exists()


@pytest.fixture
def synthetic_val(tmp_path):
    project = tmp_path / "project"
    root = project / ".rloop/data/Grain/val"
    manifest = dict(domain="grain-316l", split="val", images=[])
    predictions = {}
    for index in range(2):
        name = f"sample-{index}"
        mask = np.zeros((16, 20), dtype=np.uint8)
        mask[2:6, 3:7] = 1
        mask[9:13, 11:15] = 1
        mask[0:2, 17:20] = 1  # Include an edge grain: count all, size interior only.
        row = dict(name=name)
        for kind, pixels, key in (("images", np.repeat(mask[..., None] * 200, 3, axis=2), "image"),
                ("masks", mask, "mask")):
            path = root / kind / f"{name}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(pixels).save(path)
            row[key] = dict(path=f"{kind}/{name}.png", sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest["images"].append(row)
        from skimage.measure import label
        predictions[name] = label(mask == 1, connectivity=1).astype(np.uint16)
    manifest_path = project / ".rloop/data/val.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    archive = tmp_path / "val_labels.npz"
    np.savez(archive, **predictions)
    return project, archive, manifest, predictions


def test_cnn_score_local_cli(synthetic_val):
    project, archive, _, _ = synthetic_val
    result = subprocess.run([sys.executable, str(EXPERIMENT / "score_local.py"), str(project), str(archive)],
        capture_output=True, text=True, check=True)
    printed = json.loads(result.stdout)
    assert printed == json.loads(archive.with_suffix(".score.json").read_text(encoding="utf-8"))
    assert printed["max_rel_error"] == 0
    assert printed["median_count_rel_error"] == printed["median_size_rel_error"] == 0
    assert printed["median_count_bias"] == printed["median_size_bias"] == 0
    assert printed["difference_to_team"] == -0.12586301151517196
    assert printed["beats_team_pipeline"] and printed["meets_phase_4b_target"]
    assert printed["per_image"]["sample-0"]["n_true"] == 3
    assert printed["per_image"]["sample-0"]["n_pred_interior"] == 2
    again = subprocess.run([sys.executable, str(EXPERIMENT / "score_local.py"), str(project), str(archive)],
        capture_output=True, text=True)
    assert again.returncode != 0 and "FileExistsError" in again.stderr


def test_cnn_score_local_nonzero(synthetic_val):
    project, archive, _, predictions = synthetic_val
    for labels in predictions.values():
        labels[labels == 2] = 0  # One interior region missing.
    np.savez(archive, **predictions)
    result = load_script("score_local").score_local(project, archive)
    assert result["max_rel_error"] == pytest.approx(1 / 3)
    assert result["median_count_bias"] == pytest.approx(-1 / 3)
    assert result["median_size_bias"] == 0


@pytest.mark.parametrize("split", ["train", "test", None])
def test_cnn_scorer_refuses_other_splits(synthetic_val, split, monkeypatch):
    project, archive, manifest, _ = synthetic_val
    manifest["split"] = split
    (project / ".rloop/data/val.json").write_text(json.dumps(manifest), encoding="utf-8")
    scorer = load_script("score_local")

    def forbidden(*args, **kwargs):
        pytest.fail("opened data for a non-val manifest")

    monkeypatch.setattr(scorer, "manifest_rows", forbidden)
    monkeypatch.setattr(scorer, "verified_bytes", forbidden)
    with pytest.raises(IntegrityError, match="val manifest"):
        scorer.score_local(project, archive)


@pytest.mark.parametrize("problem", ["missing", "extra", "shape", "dtype", "hash", "path"])
def test_cnn_scorer_validates_inputs(synthetic_val, problem):
    project, archive, manifest, predictions = synthetic_val
    if problem == "missing":
        predictions.pop("sample-0")
    elif problem == "extra":
        predictions["extra"] = predictions["sample-0"]
    elif problem == "shape":
        predictions["sample-0"] = np.zeros((2, 3), dtype=np.uint16)
    elif problem == "dtype":
        predictions["sample-0"] = predictions["sample-0"].astype(np.float32)
    elif problem == "hash":
        manifest["images"][0]["mask"]["sha256"] = "0" * 64
    else:
        manifest["images"][0]["mask"]["path"] = "../masks/sample-0.png"
    (project / ".rloop/data/val.json").write_text(json.dumps(manifest), encoding="utf-8")
    np.savez(archive, **predictions)
    with pytest.raises(IntegrityError):
        load_script("score_local").score_local(project, archive)
