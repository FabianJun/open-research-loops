"""Score one val prediction archive using the protected evaluator's metric."""

import argparse
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from research_loops.domain import IntegrityError
from research_loops.grain_evaluator import manifest_rows, measure, score, truth, verified_bytes


TEAM_MAX_REL_ERROR = 0.12586301151517196


def score_local(project, predictions_path):
    project, predictions_path = Path(project), Path(predictions_path)
    manifest_path = project / ".rloop/data/val.json"
    if any(p.is_symlink() or p.is_junction() for p in (manifest_path, *manifest_path.parents)):
        raise IntegrityError("val manifest links forbidden")
    manifest = json.loads(manifest_path.read_bytes())
    if not isinstance(manifest, dict) or manifest.get("split") != "val":
        raise IntegrityError("scoring requires a val manifest")
    rows = manifest_rows(manifest)
    root = project / ".rloop/data/Grain/val"
    truths, predictions = {}, {}
    with np.load(predictions_path, allow_pickle=False) as arrays:
        names = [row["name"] for row in rows]
        if len(arrays.files) != len(names) or set(arrays.files) != set(names):
            raise IntegrityError("prediction keys must exactly match val stems")
        for row in rows:
            image_bytes = verified_bytes(root, row["image"], "images")
            mask_bytes = verified_bytes(root, row["mask"], "masks")
            with Image.open(io.BytesIO(image_bytes)) as image:
                shape = (image.height, image.width)
            with Image.open(io.BytesIO(mask_bytes)) as mask:
                mask_array = np.array(mask)
            labels = arrays[row["name"]]
            if mask_array.shape != shape or labels.shape != shape:
                raise IntegrityError("val image, mask and prediction shapes must match")
            if labels.dtype != np.uint16:
                raise IntegrityError("predicted labels must be uint16")
            truths[row["name"]] = truth(mask_array)
            predictions[row["name"]] = measure(labels)
    result = score(truths, predictions, exclude_edge=False)
    return {**result, "team_max_rel_error": TEAM_MAX_REL_ERROR,
        "difference_to_team": result["max_rel_error"] - TEAM_MAX_REL_ERROR,
        "beats_team_pipeline": result["max_rel_error"] < TEAM_MAX_REL_ERROR,
        "meets_phase_4b_target": result["max_rel_error"] <= 0.10}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("val_labels", type=Path)
    args = parser.parse_args()
    destination = args.val_labels.with_suffix(".score.json")
    # Keep the one-score rule visible and avoid silently replacing its evidence.
    if destination.exists():
        raise FileExistsError(destination)
    result = score_local(args.project_dir, args.val_labels)
    rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
    with destination.open("x", encoding="utf-8", newline="\n") as output:
        output.write(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
