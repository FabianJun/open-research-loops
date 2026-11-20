"""Offline grain boundary tests. Only generated pixels are used here."""

import asyncio
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest
from typer.testing import CliRunner

from research_loops.cli import app
from research_loops.contracts import GrainContract, GrainWorkerContract, parse_contract
from research_loops.domain import IntegrityError, canonical, content_hash, digest
from research_loops.evaluation import SubprocessEvaluator
from research_loops.grain_data import _fetch_verified_archive
from research_loops.grain_evaluator import TEAM_FINAL, evaluate, validate_params
from research_loops.tools import ToolService
from research_loops.transports.protocol import Dispatcher, TOOL_NAMES, tool_names
from research_loops.verification import check


def fixture_zip(path):
    import numpy as np
    from PIL import Image
    yy, xx = np.mgrid[:96, :96]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for split in ("train", "val", "test"):
            for index in range(3):
                rng = np.random.default_rng(19 + index)
                centers = np.array([(y + rng.integers(-4, 5), x + rng.integers(-4, 5))
                    for y in (0, 32, 64, 95) for x in (0, 32, 64, 95)])
                labels = np.argmin((yy[..., None]-centers[:, 0])**2 + (xx[..., None]-centers[:, 1])**2, axis=2)
                mask = np.ones(labels.shape, np.uint8)
                mask[1:, :] &= labels[1:, :] == labels[:-1, :]
                mask[:, 1:] &= labels[:, 1:] == labels[:, :-1]
                image = np.where(mask, 180 + labels * 3, 15).astype(np.uint8)
                for kind, pixels in (("images", image), ("masks", mask)):
                    output = io.BytesIO()
                    Image.fromarray(pixels).save(output, format="PNG")
                    z.writestr(f"Grain/{split}/{kind}/image-{index:02d}.png", output.getvalue())
    data = path.read_bytes()
    return (len(data), hashlib.md5(data).hexdigest(), digest(data))


@pytest.fixture
def grain(tmp_path):
    pytest.importorskip("skimage")
    project = tmp_path / "grain space ü"
    project.mkdir()
    (project / "contract.json").write_text(canonical(GrainContract()), encoding="utf-8")
    archive = tmp_path / "fixture.zip"
    expected = fixture_zip(archive)
    _fetch_verified_archive(project, archive, expected, dict(train=3, val=3, test=3))
    return project, archive, expected


def grain_request(project, params=None, split="val"):
    return dict(domain="grain-316l", candidate=params or {},
        manifest=json.loads((project / ".rloop/data" / f"{split}.json").read_bytes()),
        data_root=str(project / ".rloop/data/Grain" / split))


def synthetic_controls(monkeypatch, project):
    from research_loops import grain_worker
    expected = tuple(evaluate(grain_request(project, p)).max_rel_error for p in ({}, TEAM_FINAL))
    monkeypatch.setattr(grain_worker, "control_expectations", lambda: expected)
    return expected


@pytest.mark.parametrize("params,match", [
    ({"code": "pass"}, "unknown"), ({"detect_pores": False}, "unknown"),
    ({"sigma": True}, "sigma"), ({"sigma": float("nan")}, "sigma"),
    ({"sigma": 5.1}, "sigma"), ({"line_width_px": 1.0}, "integer"),
    ({"footprint": 4}, "odd"), ({"min_area_px": -1}, "min_area_px"),
    ({"denoise": "bad"}, "denoise"), ({"markers": []}, "markers"),
    ({"exclude_edge": 0}, "boolean"), ({"h_px": 0}, "h_px"),
    ({"min_distance": 61}, "min_distance"), ([], "object"),
])
def test_candidate_validation(params, match):
    with pytest.raises(IntegrityError, match=match):
        validate_params(params)


def test_contract_and_defaults():
    from pydantic import ValidationError
    from research_loops.grain_evaluator import DEFAULTS
    assert validate_params({}) == DEFAULTS
    assert parse_contract(canonical(GrainContract())).license == "CC-BY-4.0"
    for change in ({"archive_sha256": "a" * 64}, {"dataset_doi": "wrong"},
            {"license": "CC0-1.0"}, {"threshold_max_rel_error": .11},
            {"seeds": []}, {"seeds": [7, 7]}, {"limits": {"project_seconds": 3601}}):
        with pytest.raises(ValidationError):
            GrainContract.model_validate({**GrainContract().model_dump(), **change})


def test_fetch_idempotency_and_public_statistics(grain):
    project, archive, expected = grain
    before = {p.relative_to(project): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in project.rglob("*") if p.is_file()}
    _fetch_verified_archive(project, archive, expected, dict(train=3, val=3, test=3))
    after = {p.relative_to(project): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in project.rglob("*") if p.is_file()}
    assert before == after
    data = (project / ".rloop/inputs/training.json").read_bytes()
    public = json.loads(data)
    assert len(data) < 1_000_000 and len(public["images"]) == 3
    assert public["images"][0]["size_px"] == [96, 96]
    assert public["images"][0]["n_all"] > public["images"][0]["n_interior"] > 0
    assert public["team_benchmark"]["tag"] == "cited"
    assert not any(k in canonical(public) for k in ('"data_root":', '"base64":', '"pixels":'))


def test_original_jpeg_images_remain_byte_identical(tmp_path):
    import importlib.util
    if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("PIL") is None:
        pytest.skip("install research-loops[grain] for grain fixture tests")
    import numpy as np
    from PIL import Image
    archive = tmp_path / "fixture.zip"
    fixture_zip(archive)
    members = {}
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            data = z.read(name)
            if name == "Grain/val/images/image-00.png":
                with Image.open(io.BytesIO(data)) as im:
                    target = io.BytesIO()
                    im.save(target, format="JPEG")
                data = target.getvalue()
                name = "Grain/val/images/image-00.jpg"
                jpeg = data
            members[name] = data
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    raw = archive.read_bytes()
    project = tmp_path / "jpeg-project"
    _fetch_verified_archive(project, archive, (len(raw), hashlib.md5(raw).hexdigest(), digest(raw)), dict(train=3, val=3, test=3))
    assert (project / ".rloop/data/Grain/val/images/image-00.jpg").read_bytes() == jpeg
    manifest = json.loads((project / ".rloop/data/val.json").read_bytes())
    assert manifest["images"][0]["image"] == {"path": "images/image-00.jpg", "sha256": digest(jpeg)}


def test_fetch_cli_hash_refusal(grain):
    project, archive, expected = grain
    result = CliRunner().invoke(app, ["data", "fetch", str(project), "--archive", str(archive)])
    assert result.exit_code != 0 and "size/md5/sha256" in result.output
    assert not (project / ".rloop/state.sqlite").exists()


@pytest.mark.parametrize("index", [0, 1, 2])
def test_fetch_each_hash_checked_before_extraction(tmp_path, index):
    import importlib.util
    if importlib.util.find_spec("numpy") is None or importlib.util.find_spec("PIL") is None:
        pytest.skip("install research-loops[grain] for grain fixture tests")
    archive = tmp_path / "fixture.zip"
    expected = list(fixture_zip(archive))
    expected[index] = 1 if index == 0 else "0" * (32 if index == 1 else 64)
    with pytest.raises(IntegrityError, match="size/md5/sha256"):
        _fetch_verified_archive(tmp_path / "refused", archive, expected, dict(train=3, val=3, test=3))
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("name,link", [("../escape.png", False), ("/absolute.png", False),
    ("C:/escape.png", False), ("Grain/val/images/a.png", True),
    ("Grain/train/../escape.png", False), ("Grain\\val\\escape.png", False)])
def test_fetch_unsafe_zip_refused(tmp_path, name, link):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as z:
        info = zipfile.ZipInfo(name)
        info.filename = name  # Preserve backslashes; ZipInfo normalizes them on Windows.
        if link:
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, b"not a pixel")
    raw = archive.read_bytes()
    with pytest.raises(IntegrityError, match="unsafe|links"):
        _fetch_verified_archive(tmp_path / "project", archive,
            (len(raw), hashlib.md5(raw).hexdigest(), digest(raw)), dict(train=3, val=3, test=3))
    assert not (tmp_path / "project/.rloop/data").exists()


def test_fetch_duplicate_refusal(tmp_path):
    archive = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("Grain/val/images/a.png", b"a")
        z.writestr("Grain/val/images/A.png", b"b")
    raw = archive.read_bytes()
    with pytest.raises(IntegrityError, match="duplicate"):
        _fetch_verified_archive(tmp_path / "project", archive,
            (len(raw), hashlib.md5(raw).hexdigest(), digest(raw)), dict(train=3, val=3, test=3))


def test_protected_evaluator_and_independent_verification(grain):
    project, _, _ = grain
    request = grain_request(project)
    verdict = evaluate(request)
    check(request, verdict)
    altered = copy.deepcopy(verdict.per_image)
    altered[next(iter(altered))]["count_rel_error"] += 1e-6
    with pytest.raises(IntegrityError, match="verifier"):
        check(request, verdict.model_copy(update={"per_image": altered}))
    for key in ("max_rel_error", "median_size_rel_error", "median_count_bias", "n_images_size"):
        v = getattr(verdict, key)
        with pytest.raises(IntegrityError, match="verifier"):
            check(request, verdict.model_copy(update={key: v + .01}))
    for key in ("image", "mask"):
        changed = copy.deepcopy(request)
        changed["manifest"]["images"][0][key]["sha256"] = "0" * 64
        with pytest.raises(IntegrityError, match="sha256"):
            evaluate(changed)
    missing = copy.deepcopy(request)
    missing["manifest"]["images"][0]["image"]["path"] = "images/absent.png"
    missing["manifest"]["images"][0]["mask"]["path"] = "masks/absent.png"
    missing["manifest"]["images"][0]["name"] = "absent"
    with pytest.raises(IntegrityError, match="missing"):
        evaluate(missing)
    invalid = {**request, "candidate": {"code": "print(1)"}}
    with pytest.raises(IntegrityError, match="unknown"):
        evaluate(invalid)
    # The actual isolated module, not an in-process substitute.
    isolated = SubprocessEvaluator().evaluate(b"{}", canonical(request["manifest"]).encode(), 300,
        data_root=Path(request["data_root"]))
    assert isolated == verdict


def test_controls_fail_before_dispatch(grain, monkeypatch):
    from research_loops.coordinator import run
    from research_loops.storage import Repository
    project, _, _ = grain
    from research_loops.grain_evaluator import CONTROL_VALUES
    with pytest.raises(IntegrityError, match=f"{CONTROL_VALUES[0]}.*{CONTROL_VALUES[1]}"):
        asyncio.run(run(project))
    repo = Repository(project / ".rloop")
    try:
        assert not repo.runs()
        assert repo.db.execute("SELECT control_attempts,pilot FROM project").fetchone()[:] == (2, None)
    finally:
        repo.close()


def training_service(project, name="training-tool"):
    from research_loops.coordinator import prepare
    from research_loops.grain_worker import prepare_training_tool
    repo, contract, key = prepare(project)
    root = repo.root / "runs" / name
    try:
        prepare_training_tool(repo, contract, key, root)
        public = (project / ".rloop/inputs/training.json").read_bytes()
        (root / "public").mkdir(exist_ok=True)
        (root / "public/training.json").write_bytes(public)
        assignment = GrainWorkerContract(run_id=name, registration_hash=key, goal=contract.goal,
            prediction=contract.prediction, seed=7, variant=0, input_hash=digest(public))
    finally:
        repo.close()
    return ToolService(assignment, root / "outbox")


def test_training_cap_journal_and_validation(grain, monkeypatch):
    project, _, _ = grain
    service = training_service(project)
    calls = []
    def evaluate_training(self, candidate, dataset, seconds, **kwargs):
        calls.append((json.loads(candidate), json.loads(dataset), kwargs))
        return evaluate(dict(domain="grain-316l", candidate=json.loads(candidate), manifest=json.loads(dataset), data_root=str(kwargs["data_root"])))
    monkeypatch.setattr(SubprocessEvaluator, "evaluate", evaluate_training)
    for _ in range(6):
        result = service.try_on_training({})
        assert result["per_image"] and result["n_images"] == 3
    with pytest.raises(IntegrityError, match="6 calls"):
        service.try_on_training({})
    assert len(calls) == 6
    journal = [json.loads(line) for line in (service.root / "journal.jsonl").read_bytes().splitlines()]
    assert len([e for e in journal if e["kind"] == "training_result"]) == 6
    assert all(e["payload"]["params_hash"] == content_hash({}) for e in journal if e["kind"] == "training_start")
    restarted = ToolService(service.contract, service.root)
    with pytest.raises(IntegrityError, match="6 calls"):
        restarted.try_on_training({})
    other = training_service(project, "invalid")
    with pytest.raises(IntegrityError, match="unknown"):
        other.try_on_training({"detect_scratches": True})
    assert other.training_calls == 1


def test_training_data_isolation(grain):
    project, _, _ = grain
    service = training_service(project)
    capability = service.training
    assert set(capability) == {"manifest", "data_root"}
    assert Path(capability["data_root"]).name == "train"
    assert capability["manifest"]["split"] == "train"
    assert len(capability["manifest"]["images"]) <= 32
    serialized = canonical(capability)
    assert Path(capability["data_root"]).relative_to(project).parts == (".rloop", "data", "Grain", "train")
    assert not any(path in serialized for path in ("/val/", "/test/", "state.sqlite", "project.json"))
    dispatch = Dispatcher(service)
    for path in ("../training-tool.json", "../private/development.json", "inputs/development.json", "inputs/final.json", str(project / ".rloop/data/Grain/val/masks/image-00.png")):
        assert not dispatch.call("read_artifact", {"relative": path})["ok"]
    assert not dispatch.call("try_on_training", {"params": {}, "data_root": "../val"})["ok"]
    # Path-bearing candidate keys cannot redirect the evaluator.
    assert not dispatch.call("try_on_training", {"params": {"mask": "../../val/masks/image-00.png"}})["ok"]
    manifest = copy.deepcopy(capability["manifest"])
    manifest["images"][0]["mask"]["path"] = "../../val/masks/image-00.png"
    with pytest.raises(IntegrityError, match="manifest"):
        evaluate(dict(domain="grain-316l", manifest=manifest, candidate={}, data_root=capability["data_root"]))
    # Remove the other splits entirely; protected training evaluation still works.
    import shutil
    shutil.rmtree(project / ".rloop/data/Grain/val")
    shutil.rmtree(project / ".rloop/data/Grain/test")
    assert service.try_on_training({})["n_images"] == 3


def test_fake_grain_campaign_report_and_final(grain, monkeypatch):
    from research_loops.coordinator import run
    from research_loops.assessment import assess
    from research_loops.storage import Repository
    project, _, _ = grain
    synthetic_controls(monkeypatch, project)
    runner = CliRunner()
    for args in (["init", str(project), "--owner", "Fixture Owner"], ["plan", str(project)],
            ["run", str(project)], ["report", str(project), "--check"], ["export", str(project)]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.output, result.exception)
    repo = Repository(project / ".rloop")
    try:
        rows = repo.runs()
        assert len(rows) == 4 and all(r["verification_status"] == "checked" for r in rows)
        for row in rows:
            candidate = json.loads(repo.artifact(row["id"], "candidate"))
            assert candidate == validate_params(candidate)
        text = (repo.root / "report.md").read_text(encoding="utf-8")
        assert "Real benchmark with a published baseline" in text
        assert "simulated" in text and "reproduction passed" in text
        assert "final package license" in text and "unspent" in text
    finally:
        repo.close()
    assessment = assess(project)
    assert "real benchmark with a published baseline" in assessment
    assert "known-answer" not in assessment
    assert "FAIL" not in assessment, assessment
    assert "Open questions requiring human judgment" in assessment
    # Only synthetic test pixels: exercise final consumption and sealed reports.
    asyncio.run(run(project, final=True))
    assert runner.invoke(app, ["report", str(project), "--check"]).exit_code == 0
    assert "Final holdout max_rel_error" in (project / ".rloop/report.md").read_text(encoding="utf-8")
    with pytest.raises(IntegrityError, match="consumed"):
        asyncio.run(run(project, final=True))


def test_planted_byte_identity():
    from research_loops.domain import Contract
    from research_loops.evaluation import evaluator_hash
    root = Path(__file__).parents[1]
    contract = Contract.model_validate_json((root / "examples/planted-signal/contract.json").read_bytes())
    from research_loops.data import datasets
    inputs = {k: digest(v) for k, v in datasets(contract).items()}
    inputs["proposal_method"] = digest((root / "src/research_loops/fake.py").read_bytes())
    assert content_hash(contract) == "f14bc5d20551e6afe192576cecb46f18f304e97f5badf6793e744e0f9b500ee9"
    assert content_hash(dict(contract=contract.model_dump(mode="json"), evaluator_hash=evaluator_hash(), inputs=inputs)) == "993f79cab2f4a6986a331c035e6d6223b1d39e4c201eee788166a2b97b61230c"
    assert tool_names(contract) == TOOL_NAMES and len(TOOL_NAMES) == 6


def test_compatibility_identity_is_bound_to_all_protected_bytes(monkeypatch):
    import research_loops.evaluation as module
    from research_loops.protection import verify_anchor
    current = copy.deepcopy(verify_anchor())
    assert module.evaluator_hash() == "47810f280d9d73b86fbbc46f7821dc8202d53d961785b165fbc0f9bcf772d57f"
    current["files"]["domain.py"] = "0" * 64
    monkeypatch.setattr(module, "verify_anchor", lambda: current)
    assert module.evaluator_hash() != "47810f280d9d73b86fbbc46f7821dc8202d53d961785b165fbc0f9bcf772d57f"


def grain_script():
    response = yield "read_contract", {}
    assert response["value"]["worker_protocol"] == 3
    training = yield "read_artifact", {"relative": "inputs/training.json"}
    assert training["ok"] and json.loads(training["value"]["text"])["images"]
    for path in ("../training-tool.json", "inputs/development.json", "inputs/final.json", "../../project.json"):
        assert not (yield "read_artifact", {"relative": path})["ok"]
    assert (yield "register_variant", {"prediction": "reproduce the cited team configuration"})["ok"]
    rejected = yield "try_on_training", {"params": {"sigma": True}}
    assert not rejected["ok"] and "sigma" in rejected["error"]
    result = yield "try_on_training", {"params": TEAM_FINAL}
    assert result["ok"] and result["value"]["per_image"]
    assert not (yield "submit_result", {"candidate": {"code": "pass"}})["ok"]
    assert (yield "submit_result", {"candidate": TEAM_FINAL})["ok"]
    candidate = yield "read_artifact", {"relative": "candidate.json"}
    assert json.loads(candidate["value"]["text"]) == validate_params(TEAM_FINAL)
    assert not (yield "try_on_training", {"params": {}})["ok"]
    assert not (yield "submit_result", {"candidate": {}})["ok"]


@pytest.mark.parametrize("name", ["fake", "mcp_fake", "openai_agents", "claude_agent", "chatgpt_stream"])
def test_shared_grain_backend_tools(grain, name):
    from research_loops.domain import Limits, Workspace
    from sdk_seams import openai_model, claude_transport
    project, _, _ = grain
    service = training_service(project)
    assignment = service.contract
    expected = TOOL_NAMES + ("try_on_training",)
    assert service.tool_names == tool_names(assignment) == expected
    if name == "fake":
        from research_loops.grain_worker import GrainFakeBackend
        backend = GrainFakeBackend()
    elif name == "mcp_fake":
        pytest.importorskip("mcp")
        from research_loops.adapters.mcp_fake import MCPFakeBackend
        backend = MCPFakeBackend()
    elif name == "openai_agents":
        pytest.importorskip("agents")
        from research_loops.adapters.openai_agents import OpenAIBackend
        backend = OpenAIBackend("offline-stub", offline_model=openai_model(plan_factory=grain_script, expected_tools=expected))
    elif name == "chatgpt_stream":
        pytest.importorskip("agents")
        from test_chatgpt_responses import stream_client, StubAuth
        from research_loops.adapters.openai_agents import OpenAIBackend
        client, requests = stream_client(plan_factory=grain_script, tool_count=7)
        backend = OpenAIBackend("gpt-6-astra", offline_client=client, offline_auth=StubAuth())
    else:
        pytest.importorskip("claude_agent_sdk")
        from research_loops.adapters.claude_agent import ClaudeBackend
        backend = ClaudeBackend("offline-stub", offline_transport_factory=lambda options:
            claude_transport(options, plan_factory=grain_script, expected_tools=expected))
    result = asyncio.run(backend.run(assignment, Workspace(root=service.root), Limits(worker_seconds=300)))
    assert result.candidate.sha256 == digest((service.root / "candidate.json").read_bytes())
    if name in {"openai_agents", "claude_agent", "chatgpt_stream"}:
        trace = json.loads((service.root / "adapter-trace.json").read_bytes())
        names = [n.removeprefix("mcp__rloop__") for n in trace["effective_tools"]]
        assert set(names) == set(expected)
        assert trace["offline_seam"]


def test_guide_grain_commands_offline(grain, monkeypatch, tmp_path):
    import re
    import shlex
    import shutil
    import subprocess
    import sys
    from research_loops import grain_data, grain_worker
    project, archive, expected = grain
    source = Path(__file__).parents[1]
    checkout = tmp_path / "guide checkout"
    (checkout / "examples").mkdir(parents=True)
    shutil.copytree(source / "examples/grain-316l", checkout / "examples/grain-316l")
    shutil.copyfile(archive, checkout / "Grain.zip")
    synthetic_controls(monkeypatch, project)
    # In-process test injection only; the CLI has no fixture switch or hash option.
    monkeypatch.setattr(grain_data, "fetch", lambda project, archive=None:
        _fetch_verified_archive(project, archive, expected, dict(train=3, val=3, test=3)))
    monkeypatch.chdir(checkout)
    text = (source / "docs/GUIDE.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```powershell\n(.*?)```", text, re.S)
    assert len(blocks) == 1
    for line in blocks[0].strip().splitlines():
        command = shlex.split(line)
        assert command[:2] == ["uv", "run"]
        if command[2] == "python":
            result = subprocess.run([sys.executable, "-I", *command[3:]], cwd=checkout, capture_output=True)
            assert result.returncode == 0, result.stderr
        else:
            assert command[2] == "rloop"
            result = CliRunner().invoke(app, command[3:])
            assert result.exit_code == 0, (line, result.output, result.exception)
    assert "public-ready: needs human review" in (checkout / "grain-demo/.rloop/self-assessment.md").read_text(encoding="utf-8")
