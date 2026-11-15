"""Protected 316L pipeline and metric; no pixels leave this process.

Ported from VanishJr/micrograph-impact-lab, Apache-2.0, commit
91758551f37d54d94130ab69cd00a8ee68ac0d40 (watershed.py, common.py, evaluate.py).
Defect detection, file outputs and unrelated measurements are omitted. See NOTICE.
"""

import statistics
import json
from pathlib import Path, PurePosixPath

from pydantic import Field

from research_loops.domain import IntegrityError, Message, digest
from research_loops.paths import confined


class GrainVerdict(Message):
    max_rel_error: float = Field(ge=0)
    median_count_rel_error: float = Field(ge=0)
    median_size_rel_error: float | None = Field(default=None, ge=0)
    median_count_bias: float
    median_size_bias: float | None
    n_images: int = Field(ge=1)
    n_images_size: int = Field(ge=0)
    per_image: dict[str, dict]
    supported: bool

DEFAULTS = dict(denoise="gaussian", sigma=1.0, boundary="tophat", line_width_px=4,
    markers="peaks", h_px=2.0, min_distance=8, footprint=15, min_area_px=40,
    exclude_edge=False, fill_boundaries=True)
CHOICES = dict(denoise=("none", "gaussian", "median"),
    boundary=("threshold", "sobel", "tophat"), markers=("peaks", "hmaxima"))
RANGES = dict(sigma=(.5, 5), line_width_px=(1, 15), h_px=(1, 5),
    min_distance=(2, 60), footprint=(3, 61), min_area_px=(0, 5000))
TEAM_FINAL = dict(denoise="gaussian", sigma=4.0, boundary="tophat", line_width_px=15,
    markers="hmaxima", h_px=5.0, min_area_px=1500, exclude_edge=False, fill_boundaries=False)
CONTROL_VALUES = (12.885281385281385, 0.12586301151517196)


def validate_params(params):
    if not isinstance(params, dict):
        raise IntegrityError("grain candidate must be a JSON object of pipeline parameters")
    if set(params) - set(DEFAULTS):
        raise IntegrityError("unknown grain parameter; allowed: " + ", ".join(DEFAULTS))
    p = {**DEFAULTS, **params}
    for key, choices in CHOICES.items():
        if type(p[key]) is not str or p[key] not in choices:
            raise IntegrityError(key + " must be one of " + ", ".join(choices))
    for key, (low, high) in RANGES.items():
        types = (int, float) if key in {"sigma", "h_px"} else (int,)
        if type(p[key]) not in types or not low <= p[key] <= high:
            raise IntegrityError(f"{key} must be {'a number' if len(types) == 2 else 'an integer'} in {low}..{high}")
    if p["footprint"] % 2 != 1:
        raise IntegrityError("footprint must be odd")
    for key in ("exclude_edge", "fill_boundaries"):
        if type(p[key]) is not bool:
            raise IntegrityError(key + " must be a boolean")
    return p


def segment(raw, params):
    import numpy as np
    from scipy import ndimage as ndi
    from skimage.color import rgb2gray
    from skimage.feature import peak_local_max
    from skimage.filters import gaussian, median, sobel, threshold_otsu
    from skimage.measure import label
    from skimage.morphology import black_tophat, disk, h_maxima, remove_small_objects
    from skimage.segmentation import clear_border, relabel_sequential, watershed

    p = validate_params(params)
    gray = rgb2gray(raw[..., :3]) if raw.ndim == 3 else raw.astype(float) / 255.0
    if p["denoise"] == "gaussian":
        smooth = gaussian(gray, sigma=p["sigma"])
    elif p["denoise"] == "median":
        smooth = median(gray, disk(max(1, round(p["sigma"]))))
    else:
        smooth = gray
    if p["boundary"] == "threshold":
        boundary = smooth < threshold_otsu(smooth)
    elif p["boundary"] == "sobel":
        edges = sobel(smooth)
        boundary = edges > threshold_otsu(edges)
    else:
        response = black_tophat(smooth, disk(int(p["line_width_px"])))
        boundary = response > threshold_otsu(response)
    interior = ~boundary
    distance = ndi.distance_transform_edt(interior)
    if p["markers"] == "hmaxima":
        markers = label(h_maxima(distance, float(p["h_px"])).astype(bool) & interior)
    else:
        size = int(p["footprint"]) | 1
        peaks = peak_local_max(distance, min_distance=int(p["min_distance"]),
            footprint=np.ones((size, size)), labels=label(interior), exclude_border=False)
        markers = np.zeros(distance.shape, dtype=np.int32)
        markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    labels = watershed(-distance, markers, mask=None if p["fill_boundaries"] else interior)
    if p["min_area_px"] > 0:
        labels = remove_small_objects(labels, min_size=int(p["min_area_px"]))
    if p["exclude_edge"]:
        labels = clear_border(labels)
    labels, _, _ = relabel_sequential(labels)
    return labels


def measure(labels):
    import numpy as np
    from skimage.measure import regionprops
    h, w = labels.shape
    regions = regionprops(labels)
    interior = [r.equivalent_diameter_area for r in regions
        if not (r.bbox[0] == 0 or r.bbox[1] == 0 or r.bbox[2] == h or r.bbox[3] == w)]
    return dict(n_all=len(regions), n_interior=len(interior),
        mean_eq_interior=float(np.mean(interior)) if interior else None)


def truth(mask):
    from skimage.measure import label
    return measure(label(mask == 1, connectivity=1))


def score(truths, predictions, exclude_edge):
    rows = {}
    for name, t in truths.items():
        p = predictions[name]
        n_true = t["n_interior"] if exclude_edge else t["n_all"]
        if n_true == 0:
            raise IntegrityError("count metric undefined: no truth regions for selected edge policy")
        true_size = t["mean_eq_interior"]
        pred_size = p["mean_eq_interior"]
        rows[name] = dict(n_true=n_true, n_pred=p["n_all"],
            n_pred_interior=p["n_interior"], mean_eq_true=true_size, mean_eq_pred=pred_size,
            count_rel_error=(p["n_all"] - n_true) / n_true,
            size_rel_error=None if true_size is None else
                ((pred_size - true_size) / true_size if pred_size is not None else 1.0))
    counts = [r["count_rel_error"] for r in rows.values()]
    sizes = [r["size_rel_error"] for r in rows.values() if r["size_rel_error"] is not None]
    c = statistics.median(map(abs, counts))
    s = statistics.median(map(abs, sizes)) if sizes else None
    return dict(max_rel_error=max(c, s) if s is not None else c,
        median_count_rel_error=c, median_size_rel_error=s,
        median_count_bias=statistics.median(counts),
        median_size_bias=statistics.median(sizes) if sizes else None,
        n_images=len(rows), n_images_size=len(sizes), per_image=rows)


def verified_bytes(root, entry, kind):
    """Manifest paths are relative to one split, with no links or aliases."""
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        raise IntegrityError("invalid grain file manifest entry")
    name = entry["path"]
    if not isinstance(name, str) or "\\" in name or ":" in name:
        raise IntegrityError("invalid grain manifest path")
    path = PurePosixPath(name)
    if (path.is_absolute() or len(path.parts) != 2 or path.parts[0] != kind
            or path.parts[1] in {".", ".."} or path.suffix.lower() not in ({".png"} if kind == "masks" else {".png", ".jpg"})):
        raise IntegrityError("grain manifest path outside selected split")
    root = Path(root)
    if any(p.is_symlink() or p.is_junction() for p in (root, *root.parents)):
        raise IntegrityError("grain data links forbidden")
    target = confined(root, name)
    if not target.is_file():
        raise IntegrityError("grain manifest file missing")
    data = target.read_bytes()
    if digest(data) != entry["sha256"]:
        raise IntegrityError("grain manifest sha256 mismatch")
    return data


def manifest_rows(manifest):
    if (not isinstance(manifest, dict) or set(manifest) != {"domain", "split", "images"}
            or manifest["domain"] != "grain-316l" or manifest["split"] not in {"train", "val", "test"}
            or not isinstance(manifest["images"], list) or not manifest["images"]):
        raise IntegrityError("invalid grain split manifest")
    rows = manifest["images"]
    names = []
    paths = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "image", "mask"}:
            raise IntegrityError("invalid grain image manifest row")
        if not isinstance(row["name"], str) or not row["name"]:
            raise IntegrityError("invalid grain image name")
        for kind in ("image", "mask"):
            entry = row[kind]
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                raise IntegrityError("invalid grain file manifest entry")
            if PurePosixPath(entry["path"]).stem != row["name"]:
                raise IntegrityError("grain manifest image/mask name mismatch")
            paths.append(entry["path"].casefold())
        names.append(row["name"])
    if names != sorted(names) or len(set(names)) != len(names) or len(set(paths)) != len(paths):
        raise IntegrityError("grain manifest must be sorted and unique")
    return rows


def evaluate(request):
    import io
    import numpy as np
    from PIL import Image

    params = validate_params(request["candidate"])
    root = request["data_root"]
    truths, predictions = {}, {}
    for row in manifest_rows(request["manifest"]):
        image = verified_bytes(root, row["image"], "images")
        mask = verified_bytes(root, row["mask"], "masks")
        with Image.open(io.BytesIO(image)) as im:
            raw = np.array(im)
        with Image.open(io.BytesIO(mask)) as im:
            mask_array = np.array(im)
        if raw.shape[:2] != mask_array.shape or mask_array.ndim != 2:
            raise IntegrityError("grain image and mask dimensions differ")
        truths[row["name"]] = truth(mask_array)
        predictions[row["name"]] = measure(segment(raw, params))
    result = score(truths, predictions, params["exclude_edge"])
    return GrainVerdict(**result, supported=result["max_rel_error"] <= .10)


def parse_verdict(value):
    from research_loops.domain import Verdict
    if isinstance(value, (bytes, str)):
        value = json.loads(value)
    return GrainVerdict.model_validate(value) if "max_rel_error" in value else Verdict.model_validate(value)
