"""Standalone U-Net experiment; code Apache-2.0. No research_loops dependency.

Metric copied from src/research_loops/grain_evaluator.py, ported from
VanishJr/micrograph-impact-lab (Apache-2.0), commit
91758551f37d54d94130ab69cd00a8ee68ac0d40 (common.py, evaluate.py).
See the repository NOTICE and LICENSE. Dataset pixels are never redistributed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import random
import shutil
import stat
import statistics
import tempfile
import time
import urllib.request
import zipfile


ARCHIVE_URL = "https://zenodo.org/records/22039777/files/Grain.zip?download=1"
ARCHIVE_SIZE = 100439005
ARCHIVE_MD5 = "b6c9d5d98b5c0001e12e4ee9a0582b86"
ARCHIVE_SHA256 = "30ca8e80392519bb790d6093b5deb86df4d4aedf8cbe9beedbf329106d54d9d0"
SEED = 0
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7)
MIN_AREAS = (0, 20, 50, 100, 200)


class IntegrityError(ValueError):
    pass


def allowed_member(name):
    """An exact file allowlist; every other split and unsafe spelling is rejected."""
    path = PurePosixPath(name)
    return ("\\" not in name and ":" not in name and "\x00" not in name
        and path.as_posix() == name and len(path.parts) == 4
        and not any(part in {".", ".."} for part in path.parts)
        and path.parts[0] == "Grain" and path.parts[1] in {"train", "val"}
        and path.parts[2] in {"images", "masks"}
        and path.suffix in ({".png"} if path.parts[2] == "masks" else {".png", ".jpg"}))


def split_training(names):
    names = sorted(names)
    if len(names) != 611 or len(set(names)) != 611:
        raise IntegrityError("expected 611 unique training stems")
    random.Random(SEED).shuffle(names)
    return sorted(names[:551]), sorted(names[551:])


def verified_archive(path):
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1_048_576):
            size += len(chunk)
            md5.update(chunk)
            sha256.update(chunk)
    if (size, md5.hexdigest(), sha256.hexdigest()) != (ARCHIVE_SIZE, ARCHIVE_MD5, ARCHIVE_SHA256):
        raise IntegrityError("archive size/md5/sha256 mismatch; nothing extracted")


def extract_selected(archive, root):
    # Verify the complete archive before opening or extracting any member.
    verified_archive(archive)
    grouped = {(split, kind): {} for split in ("train", "val") for kind in ("images", "masks")}
    with zipfile.ZipFile(archive) as source:
        selected, seen = [], set()
        for info in source.infolist():
            if not allowed_member(info.orig_filename):
                continue
            name = info.orig_filename
            mode = info.external_attr >> 16
            if (info.filename != name or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                    or info.file_size > 20_000_000 or name.casefold() in seen):
                raise IntegrityError("unsafe or duplicate selected member")
            seen.add(name.casefold())
            _, split, kind, filename = PurePosixPath(name).parts
            stem = PurePosixPath(filename).stem
            if stem in grouped[split, kind]:
                raise IntegrityError("duplicate image stem")
            grouped[split, kind][stem] = root / name
            selected.append(info)
        for split, count in (("train", 611), ("val", 40)):
            if (len(grouped[split, "images"]) != count
                    or grouped[split, "images"].keys() != grouped[split, "masks"].keys()):
                raise IntegrityError("expected complete paired train/val splits")
        for info in selected:
            assert allowed_member(info.orig_filename)
            assert PurePosixPath(info.orig_filename).parts[1] in {"train", "val"}
            target = root / info.orig_filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as member, target.open("xb") as output:
                shutil.copyfileobj(member, output)
    return grouped


# Verbatim measure/truth/score from src/research_loops/grain_evaluator.py.
# Apache-2.0 origin is recorded in this module's docstring.
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


def postprocess(probability, threshold, min_area):
    from skimage.measure import label
    from skimage.morphology import remove_small_objects
    from skimage.segmentation import relabel_sequential
    labels = label(probability > threshold, connectivity=1)
    labels = remove_small_objects(labels, min_size=min_area)
    return relabel_sequential(labels)[0]


def load_image(path, mask=False):
    import numpy as np
    from PIL import Image
    with Image.open(path) as image:
        array = np.array(image)
    expected = (300, 400) if mask else (300, 400, 3)
    if array.shape != expected or array.dtype != np.uint8:
        raise IntegrityError("unexpected image shape or dtype")
    if mask and not np.isin(array, (0, 1)).all():
        raise IntegrityError("expected binary interior mask")
    return array


def make_model():
    import torch
    from torch import nn

    def block(inputs, outputs):
        return nn.Sequential(nn.Conv2d(inputs, outputs, 3, padding=1, bias=False),
            nn.BatchNorm2d(outputs), nn.ReLU(inplace=True),
            nn.Conv2d(outputs, outputs, 3, padding=1, bias=False),
            nn.BatchNorm2d(outputs), nn.ReLU(inplace=True))

    class UNet(nn.Module):
        def __init__(self):
            super().__init__()
            channels = (32, 64, 128, 256, 512)
            self.down = nn.ModuleList(block(i, o) for i, o in zip((3, *channels[:-1]), channels))
            self.pool = nn.MaxPool2d(2)
            self.up = nn.ModuleList(nn.ConvTranspose2d(i, o, 2, stride=2)
                for i, o in zip(channels[:0:-1], channels[-2::-1]))
            self.decode = nn.ModuleList(block(2 * c, c) for c in channels[-2::-1])
            self.head = nn.Conv2d(32, 1, 1)

        def forward(self, value):
            skips = []
            for layer in self.down[:-1]:
                value = layer(value)
                skips.append(value)
                value = self.pool(value)
            value = self.down[-1](value)
            for up, decode, skip in zip(self.up, self.decode, reversed(skips)):
                value = decode(torch.cat((up(value), skip), dim=1))
            return self.head(value)

    return UNet()


def make_dataset(images, masks):
    import numpy as np
    import torch
    from torch.utils.data import Dataset

    class Crops(Dataset):
        def __len__(self):
            return len(images)

        def __getitem__(self, index):
            image, mask = images[index], masks[index]
            top = random.randint(0, image.shape[0] - 256)
            left = random.randint(0, image.shape[1] - 256)
            image = image[top:top + 256, left:left + 256].astype(np.float32) / 255
            mask = mask[top:top + 256, left:left + 256].astype(np.float32)
            for axis in (0, 1):
                if random.random() < 0.5:
                    image, mask = np.flip(image, axis), np.flip(mask, axis)
            turns = random.randrange(4)
            image, mask = np.rot90(image, turns), np.rot90(mask, turns)
            brightness, contrast = random.uniform(0.9, 1.1), random.uniform(0.9, 1.1)
            image = np.clip(((image - 0.5) * contrast + 0.5) * brightness, 0, 1)
            return (torch.from_numpy(image.transpose(2, 0, 1).copy()),
                torch.from_numpy(mask[None].copy()))

    return Crops()


def predict(model, images, device):
    import numpy as np
    import torch
    from torch.nn import functional as F
    probabilities = {}
    model.eval()
    with torch.inference_mode():
        for name, image in images.items():
            height, width = image.shape[:2]
            value = torch.from_numpy(image.transpose(2, 0, 1).astype(np.float32) / 255)[None].to(device)
            value = F.pad(value, (0, (-width) % 16, 0, (-height) % 16), mode="reflect")
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(value)
            probabilities[name] = logits.float().sigmoid()[0, 0, :height, :width].cpu().numpy()
    return probabilities


def internal_score(truths, probabilities, threshold, min_area):
    predictions = {name: measure(postprocess(prob, threshold, min_area))
        for name, prob in probabilities.items()}
    return score(truths, predictions, exclude_edge=False)


def train(grouped, output, smoke):
    # Set before importing torch, including before any CUDA initialization.
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    import numpy as np
    import torch
    from torch.nn import functional as F
    from torch.utils.data import DataLoader

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    fit, check = split_training(grouped["train", "images"])
    val = sorted(grouped["val", "images"])
    epochs = 1 if smoke else 60
    if smoke:
        fit, check, val = fit[:8], check[:4], val[:2]
    fit_images = [load_image(grouped["train", "images"][n]) for n in fit]
    fit_masks = [load_image(grouped["train", "masks"][n], mask=True) for n in fit]
    check_images = {n: load_image(grouped["train", "images"][n]) for n in check}
    truths = {n: truth(load_image(grouped["train", "masks"][n], mask=True)) for n in check}
    loader = DataLoader(make_dataset(fit_images, fit_masks), batch_size=16, shuffle=True,
        num_workers=0, generator=torch.Generator().manual_seed(SEED))
    model = make_model().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history, best_score, best_epoch = [], None, None
    for epoch in range(1, epochs + 1):
        model.train()
        loss_total = 0.0
        for images, masks in loader:
            images, masks = images.to(device), masks.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                bce = F.binary_cross_entropy_with_logits(logits, masks)
                probabilities = logits.float().sigmoid()
                intersection = (probabilities * masks).sum((1, 2, 3))
                denominator = probabilities.sum((1, 2, 3)) + masks.sum((1, 2, 3))
                dice_loss = 1 - ((2 * intersection + 1) / (denominator + 1)).mean()
                loss = bce + dice_loss
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            loss_total += loss.item() * len(images)
        scheduler.step()
        result = internal_score(truths, predict(model, check_images, device), 0.5, 0)
        history.append(dict(epoch=epoch, loss=loss_total / len(fit), score=result))
        print(f"epoch {epoch}/{epochs}: internal max_rel_error={result['max_rel_error']:.8f}", flush=True)
        # Strict improvement: ties retain the earliest checkpoint.
        if best_score is None or result["max_rel_error"] < best_score["max_rel_error"]:
            best_score, best_epoch = result, epoch
            torch.save(model.state_dict(), output / "best.pt")
    model.load_state_dict(torch.load(output / "best.pt", map_location=device, weights_only=True))
    probabilities = predict(model, check_images, device)
    grid = []
    for threshold in THRESHOLDS:
        for min_area in MIN_AREAS:
            grid.append(dict(t=threshold, a=min_area,
                score=internal_score(truths, probabilities, threshold, min_area)))
    # Iteration order breaks ties: lower t, then lower a.
    chosen = min(grid, key=lambda row: row["score"]["max_rel_error"])
    # Val images are first decoded only after checkpoint and post-processing selection.
    # No val masks are opened, and no val metric is computed here.
    val_images = {n: load_image(grouped["val", "images"][n]) for n in val}
    val_probabilities = predict(model, val_images, device)
    labels = {}
    for name, probability in val_probabilities.items():
        regions = postprocess(probability, chosen["t"], chosen["a"])
        if regions.max() > np.iinfo(np.uint16).max:
            raise IntegrityError("too many labels for uint16")
        labels[name] = regions.astype(np.uint16)
    np.savez_compressed(output / "val_labels.npz", **labels)
    return dict(config=dict(model="UNet", down_levels=4, base_channels=32,
        normalization="BatchNorm", activation="ReLU", input_scale="RGB uint8 / 255",
        output="one grain-interior logit", loss="BCE + soft Dice (per-image, smoothing=1)",
        crop_size=256, crops_per_image_per_epoch=1, flips=True, rot90=True,
        brightness=[0.9, 1.1], contrast=[0.9, 1.1], optimizer="AdamW", lr=1e-3,
        weight_decay=0.01, schedule="cosine", batch_size=16, epochs=epochs,
        amp=device.type == "cuda", exclude_edge=False, checkpoint_t=0.5, checkpoint_a=0,
        thresholds=THRESHOLDS, min_areas=MIN_AREAS, smoke=smoke,
        inference="full image, reflect-pad right/bottom to multiple of 16, crop back",
        checkpoint_ties="earliest epoch", postprocess_ties="lower t, then lower a"),
        seeds=dict(python=SEED, numpy=SEED, torch=SEED, split=SEED, loader=SEED),
        fit_stems=fit, internal_check_stems=check, val_stems=val,
        archive=dict(url=ARCHIVE_URL, size=ARCHIVE_SIZE, md5=ARCHIVE_MD5, sha256=ARCHIVE_SHA256),
        t=chosen["t"], a=chosen["a"], best_epoch=best_epoch,
        checkpoint_internal_score=best_score, internal_check_score=chosen["score"],
        per_epoch_internal_scores=history, postprocess_grid=grid,
        torch_version=torch.__version__, device=str(device),
        device_name=torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU")


def resolve_output_dir(cli=None):
    if cli is not None:
        return Path(cli).resolve()
    if os.environ.get("RLOOP_OUTPUT_DIR"):
        return Path(os.environ["RLOOP_OUTPUT_DIR"]).resolve()
    if Path("/kaggle/working").is_dir():
        return Path("/kaggle/working")
    return Path("out").resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--archive", type=Path, help="use a local archive, with identical hash checks")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    output = resolve_output_dir(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ("run.json", "val_labels.npz", "best.pt")):
        raise IntegrityError("existing run outputs; use a fresh working directory")
    with tempfile.TemporaryDirectory(prefix="grain-data-", dir=output) as folder:
        archive = args.archive or Path(folder) / "Grain.zip"
        if args.archive is None:
            with urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response, archive.open("xb") as target:
                size = 0
                while chunk := response.read(1_048_576):
                    size += len(chunk)
                    if size > ARCHIVE_SIZE:
                        raise IntegrityError("download exceeds expected archive size")
                    target.write(chunk)
        grouped = extract_selected(archive, Path(folder) / "data")
        run = train(grouped, output, args.smoke)
    run["wall_time_seconds"] = time.monotonic() - started
    (output / "run.json").write_text(json.dumps(run, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"saved val_labels.npz and run.json to {output}", flush=True)


if __name__ == "__main__":
    main()
