"""Host-only archive ingestion and deterministic statistics-only public input."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import urllib.request
import zipfile

from research_loops.contracts import ARCHIVE_SHA256, is_grain, parse_contract
from research_loops.domain import IntegrityError, canonical, digest
from research_loops.paths import atomic_write, confined, long_path, plain_io_errors, plain_path
from research_loops.processes import supervised

ARCHIVE_SIZE = 100439005
ARCHIVE_MD5 = "b6c9d5d98b5c0001e12e4ee9a0582b86"
ARCHIVE_URL = "https://zenodo.org/records/22039777/files/Grain.zip?download=1"
COUNTS = {"train": 611, "val": 40, "test": 165}
LICENSE_CAVEAT = "Metadata license CC BY 4.0; the deposit README says a final package license has not been selected. Images and masks are never redistributed."
TEAM_SOURCE = "VanishJr/micrograph-impact-lab@91758551f37d54d94130ab69cd00a8ee68ac0d40 (Apache-2.0)"


@plain_io_errors()
def unchanged_write(path, data):
    if long_path(path).exists():
        if long_path(path).read_bytes() != data:
            raise IntegrityError("existing grain data or manifest differs; refusing overwrite")
    else:
        atomic_write(path, data, exclusive=True)


@plain_io_errors()
def fetch(project: Path, archive: Path | None = None):
    if not is_grain(parse_contract(long_path(project / "contract.json").read_bytes())):
        raise IntegrityError("data fetch requires a grain-316l contract")
    if archive is not None:
        return _fetch_verified_archive(project, archive, (ARCHIVE_SIZE, ARCHIVE_MD5, ARCHIVE_SHA256), COUNTS)
    # No CLI/environment override of source URL, hashes, layout, or control values.
    with tempfile.TemporaryDirectory(prefix="rloop-grain-download-") as folder:
        path = Path(folder) / "Grain.zip"
        with urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response, path.open("wb") as target:
            total = 0
            while chunk := response.read(1_048_576):
                total += len(chunk)
                if total > ARCHIVE_SIZE:
                    raise IntegrityError("grain archive exceeds expected size")
                target.write(chunk)
        return _fetch_verified_archive(project, path, (ARCHIVE_SIZE, ARCHIVE_MD5, ARCHIVE_SHA256), COUNTS)


@plain_io_errors()
def _fetch_verified_archive(project, archive, expected, counts):
    """Tests inject fixture facts directly here; no contract/CLI test seam."""
    size, md5, sha256 = expected
    raw = long_path(Path(archive)).read_bytes()
    if len(raw) != size or hashlib.md5(raw).hexdigest() != md5 or digest(raw) != sha256:
        raise IntegrityError("grain archive size/md5/sha256 verification failed; nothing extracted")
    root = project / ".rloop" / "data" / "Grain"
    manifests = {s: {"domain": "grain-316l", "split": s, "images": []} for s in counts}
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        seen, selected = set(), []
        for info in z.infolist():
            name = info.orig_filename
            path = PurePosixPath(name)
            if (info.filename != name or "\x00" in name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                    or not path.parts or any(part in {"", "."} for part in path.parts)
                    or path.as_posix() != name.rstrip("/")):
                raise IntegrityError("unsafe archive path")
            if name.rstrip("/").casefold() in seen:
                raise IntegrityError("duplicate archive path")
            seen.add(name.rstrip("/").casefold())
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise IntegrityError("archive links or special files forbidden")
            # Reject suspicious metadata before opening even one member. Only the
            # explicit data allowlist is extracted; package READMEs are ignored.
            if info.is_dir():
                continue
            if re.fullmatch(r"Grain/(train|val|test)/(images|masks)/[^/]+\.png", name):
                selected.append(info)
            elif re.fullmatch(r"Grain/(train|val|test)/images/[^/]+\.jpg", name):
                selected.append(info)
        grouped = {(s, kind): {} for s in counts for kind in ("images", "masks")}
        for info in selected:
            _, split, kind, filename = PurePosixPath(info.filename).parts
            stem = PurePosixPath(filename).stem
            if stem in grouped[split, kind]:
                raise IntegrityError("duplicate image stem")
            if info.file_size > 20_000_000:
                raise IntegrityError("oversized archive member")
            grouped[split, kind][stem] = info
        for split, count in counts.items():
            images, masks = grouped[split, "images"], grouped[split, "masks"]
            if set(images) != set(masks) or len(images) != count:
                raise IntegrityError("grain split must contain all paired images and masks")
        # All paths and pairing are validated before extraction. No decoding or
        # statistics on test; raw member hashing only anchors its future use.
        for split in counts:
            for name in sorted(grouped[split, "images"]):
                row = {"name": name}
                for kind, key in (("images", "image"), ("masks", "mask")):
                    info = grouped[split, kind][name]
                    data = z.read(info)
                    relative = kind + "/" + PurePosixPath(info.filename).name
                    target = confined(root, split + "/" + relative)
                    if any(long_path(p).is_symlink() or long_path(p).is_junction() for p in (target, *target.parents)):
                        raise IntegrityError("grain extraction links forbidden")
                    unchanged_write(target, data)
                    row[key] = {"path": relative, "sha256": digest(data)}
                manifests[split]["images"].append(row)
    for split, manifest in manifests.items():
        unchanged_write(project / ".rloop" / "data" / f"{split}.json", canonical(manifest).encode())
    request = {"manifest": manifests["train"], "data_root": str(plain_path(long_path(root / "train").resolve()))}
    public = supervised([sys.executable, "-I", "-m", "research_loops.grain_data"], canonical(request).encode(), 300)
    unchanged_write(project / ".rloop" / "inputs" / "training.json", public)
    return {split: digest(canonical(m).encode()) for split, m in manifests.items()}


def public_input(request):
    from research_loops.grain_evaluator import CHOICES, DEFAULTS, RANGES, TEAM_FINAL, manifest_rows, verified_bytes
    from research_loops.grain_verification import mask_statistics
    if request["manifest"]["split"] != "train":
        raise IntegrityError("public statistics require training data only")
    images = []
    for row in manifest_rows(request["manifest"]):
        verified_bytes(request["data_root"], row["image"], "images")
        images.append({"name": row["name"], **mask_statistics(verified_bytes(request["data_root"], row["mask"], "masks"))})
    docs = dict(denoise="Smoothing method before boundary extraction.",
        sigma="Gaussian sigma or rounded median disk radius in pixels.",
        boundary="Dark-pixel threshold, Sobel gradient, or black top-hat dark lines, using Otsu.",
        line_width_px="Disk radius for black top-hat, in pixels; wider boundaries may be missed.",
        markers="Peaks by spacing/window, or maxima rising at least h_px.",
        h_px="Minimum height of an hmaxima maximum; larger values merge regions.",
        min_distance="Minimum spacing between peaks, in pixels; ignored by hmaxima.",
        footprint="Odd square window for peaks, in pixels; ignored by hmaxima.",
        min_area_px="Drop predicted regions with area strictly below this many pixels.",
        exclude_edge="Drop predicted edge regions and count against true interior regions only.",
        fill_boundaries="Assign boundary pixels to nearest grain; false leaves boundaries unassigned.")
    return dict(domain="grain-316l", images=images,
        pipeline="Grayscale -> denoise -> boundary map -> distance transform -> markers -> watershed -> remove small regions -> optional edge exclusion. No defect detection. Counts use all truth grains unless exclude_edge=true; sizes use interior grains. Main metric is max of median absolute relative count and size errors.",
        parameters={key: {"default": value, "description": docs[key], **({"choices": CHOICES[key]} if key in CHOICES else
            {"range": RANGES[key], "type": "number" if key in {"sigma", "h_px"} else "integer", "odd": key == "footprint"} if key in RANGES else {"type": "boolean"})} for key, value in DEFAULTS.items()},
        controls={"defaults": {}, "team_final": TEAM_FINAL},
        team_benchmark={"tag": "cited", "source": TEAM_SOURCE, "development_max_rel_error": .12586301151517196,
            "holdout_max_rel_error": .17391304347826086}, license_caveat=LICENSE_CAVEAT)


if __name__ == "__main__":
    request = json.loads(sys.stdin.buffer.read(2_000_001))
    sys.stdout.write(canonical(public_input(request)))
