"""Independent grain truth and metric checks, without the ported measurement code."""

import io
import math
import statistics

from research_loops.domain import IntegrityError
from research_loops.grain_evaluator import manifest_rows, validate_params, verified_bytes


def mask_statistics(data):
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    with Image.open(io.BytesIO(data)) as im:
        mask = np.array(im)
    if mask.ndim != 2:
        raise IntegrityError("grain mask must be two dimensional")
    labels, count = ndimage.label(mask == 1, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    areas = np.bincount(labels.ravel())
    h, w = mask.shape
    diameters = []
    for index, box in enumerate(ndimage.find_objects(labels), 1):
        if box and box[0].start != 0 and box[1].start != 0 and box[0].stop != h and box[1].stop != w:
            diameters.append(math.sqrt(4 * int(areas[index]) / math.pi))
    return dict(size_px=[w, h], n_all=int(count), n_interior=len(diameters),
        mean_eq_interior=statistics.mean(diameters) if diameters else None)


def check(request, verdict):
    p = validate_params(request["candidate"])
    rows = manifest_rows(request["manifest"])
    if set(verdict.per_image) != {row["name"] for row in rows}:
        raise IntegrityError("independent grain verifier: incomplete per-image outputs")

    def equal(actual, expected):
        if expected is None:
            same = actual is None
        else:
            same = (type(actual) in (int, float) and math.isfinite(actual)
                and abs(actual - expected) <= 1e-9)
        if not same:
            raise IntegrityError("independent grain verifier disagrees")

    counts, sizes = [], []
    for row in rows:
        # Check both file hashes independently of evaluator reads, before deriving truth.
        verified_bytes(request["data_root"], row["image"], "images")
        t = mask_statistics(verified_bytes(request["data_root"], row["mask"], "masks"))
        r = verdict.per_image[row["name"]]
        n_true = t["n_interior"] if p["exclude_edge"] else t["n_all"]
        if not n_true:
            raise IntegrityError("independent grain verifier: undefined count")
        for key in ("n_pred", "n_pred_interior"):
            if type(r.get(key)) is not int or r[key] < 0:
                raise IntegrityError("independent grain verifier: invalid prediction count")
        if r["n_pred_interior"] > r["n_pred"]:
            raise IntegrityError("independent grain verifier: invalid interior count")
        pred = r["mean_eq_pred"]
        if (pred is None) != (r["n_pred_interior"] == 0) or (pred is not None and (type(pred) not in (int, float) or not math.isfinite(pred) or pred <= 0)):
            raise IntegrityError("independent grain verifier: invalid predicted diameter")
        equal(r["n_true"], n_true)
        equal(r["mean_eq_true"], t["mean_eq_interior"])
        count = (r["n_pred"] - n_true) / n_true
        size = None if t["mean_eq_interior"] is None else (1.0 if pred is None else (pred - t["mean_eq_interior"]) / t["mean_eq_interior"])
        equal(r["count_rel_error"], count)
        equal(r["size_rel_error"], size)
        counts.append(count)
        if size is not None:
            sizes.append(size)
    c = statistics.median(abs(x) for x in counts)
    s = statistics.median(abs(x) for x in sizes) if sizes else None
    equal(verdict.median_count_rel_error, c)
    equal(verdict.median_size_rel_error, s)
    equal(verdict.max_rel_error, max(c, s) if s is not None else c)
    equal(verdict.median_count_bias, statistics.median(counts))
    equal(verdict.median_size_bias, statistics.median(sizes) if sizes else None)
    equal(verdict.n_images, len(counts))
    equal(verdict.n_images_size, len(sizes))
    if verdict.supported != (verdict.max_rel_error <= .10):
        raise IntegrityError("independent grain verifier disagrees on support")
