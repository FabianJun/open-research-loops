import json
import os
import subprocess
import sys
import time

import pytest
from pydantic import ValidationError

from research_loops.data import datasets
from research_loops.domain import Contract, IntegrityError, Verdict, canonical
from research_loops.evaluation import SubprocessEvaluator
from research_loops.fake import oracle
from research_loops.processes import process_identity, supervised


def test_wrong_and_known_correct_candidates():
    data = datasets(Contract(goal="recover", falsifier="mismatch", prediction="oracle works"))["development"]
    evaluator = SubprocessEvaluator()
    assert not evaluator.evaluate(b'{"constant":0}', data, 10).supported
    assert evaluator.evaluate(canonical(oracle()).encode(), data, 10).supported
    with pytest.raises(IntegrityError):
        evaluator.evaluate(b'{"code":"print(1)"}', data, 10)


@pytest.mark.parametrize("script", ["pass", "print('x' * 1000001)", "raise RuntimeError('failed')"])
def test_bad_process_output_is_rejected(script):
    with pytest.raises(IntegrityError):
        supervised([sys.executable, "-I", "-c", script], b"", 10)


def test_nonfinite_metric_is_rejected():
    with pytest.raises(ValidationError):
        Verdict(mse=float("nan"), baseline_mse=1, improvement=0, supported=True, predictions=(), squared_errors=())


def test_timeout_cleans_grandchild(tmp_path):
    receipt = tmp_path / "child.pid"
    script = "import sys,subprocess,time,pathlib; sys.stdin.read(); p=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
    with pytest.raises(IntegrityError, match="timed out"):
        supervised([sys.executable, "-I", "-c", script, str(receipt)], b"go", 1.5)
    assert receipt.exists(), "probe must actually start a grandchild"
    pid = int(receipt.read_text())
    deadline = time.monotonic() + 5
    while process_identity(pid) is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert process_identity(pid) is None


def test_evaluator_environment_does_not_include_keys():
    output = supervised([sys.executable, "-I", "-c", "import os; print('OPENAI_API_KEY' in os.environ or 'ANTHROPIC_API_KEY' in os.environ)"], b"", 10)
    assert output.strip() == b"False"
