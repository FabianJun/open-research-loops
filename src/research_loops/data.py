"""Known-answer synthetic inputs, generated only by the coordinator."""

import itertools
import json
import random

from research_loops.domain import Contract, canonical


def datasets(contract: Contract) -> dict[str, bytes]:
    features = list(itertools.product(range(-2, 3), repeat=4))
    random.Random(610342).shuffle(features)
    rows = [{"x": list(x), "y": 2 * x[0] - 3 * x[2] + x[1] * x[3]} for x in features[:256]]
    train, development, final = rows[:64], rows[64:128], rows[128:256]
    mean = sum(row["y"] for row in train) / len(train)
    return {key: canonical({"rows": split, "training_mean": mean, "threshold_mse": contract.threshold_mse,
        "minimum_improvement": contract.minimum_improvement}).encode()
        for key, split in (("training", train), ("development", development), ("final", final))}
