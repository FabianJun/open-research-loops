"""Opt-in reproduction; reads only val members, never opens the real test split."""

import hashlib
import io
import os
from pathlib import Path
import time
import zipfile

import pytest


@pytest.mark.skipif(not os.environ.get("RLOOP_GRAIN_ARCHIVE"), reason="set RLOOP_GRAIN_ARCHIVE for local development reproduction")
def test_real_development_controls():
    import numpy as np
    from PIL import Image
    from research_loops.grain_evaluator import CONTROL_VALUES, TEAM_FINAL, measure, score, segment, truth

    started = time.monotonic()
    archive = Path(os.environ["RLOOP_GRAIN_ARCHIVE"]).read_bytes()
    assert len(archive) == 100439005
    assert hashlib.md5(archive).hexdigest() == "b6c9d5d98b5c0001e12e4ee9a0582b86"
    assert hashlib.sha256(archive).hexdigest() == "30ca8e80392519bb790d6093b5deb86df4d4aedf8cbe9beedbf329106d54d9d0"
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names = sorted(n for n in z.namelist() if n.startswith("Grain/val/images/") and Path(n).suffix in {".png", ".jpg"})
        assert len(names) == 40
        truths, images = {}, {}
        for name in names:
            stem = Path(name).stem
            with Image.open(io.BytesIO(z.read(name))) as im:
                images[stem] = np.array(im)
            mask_name = "Grain/val/masks/" + stem + ".png"
            with Image.open(io.BytesIO(z.read(mask_name))) as im:
                truths[stem] = truth(np.array(im))
    measured = []
    for config in ({}, TEAM_FINAL):
        predictions = {n: measure(segment(im, config)) for n, im in images.items()}
        measured.append(score(truths, predictions, config.get("exclude_edge", False))["max_rel_error"])
    elapsed = time.monotonic() - started
    print(f"development controls={measured}; duration={elapsed:.3f}s")
    assert measured == pytest.approx(CONTROL_VALUES, abs=1e-9, rel=0)
