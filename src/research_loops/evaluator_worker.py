"""Trusted plain-code evaluator subprocess. Interprets data, never candidate code."""

import json
import sys

from research_loops.domain import Verdict, canonical, validate_candidate


def calculate(node: dict, x: list[int]) -> int:
    if "constant" in node:
        return node["constant"]
    if "feature" in node:
        return x[node["feature"]]
    a, b = calculate(node["left"], x), calculate(node["right"], x)
    if node["op"] == "add":
        return a + b
    if node["op"] == "sub":
        return a - b
    return a * b


def evaluate(request: dict) -> Verdict:
    if request.get("domain") == "grain-316l":
        from research_loops.grain_evaluator import evaluate as grain_evaluate
        return grain_evaluate(request)
    tree, rows, mean = request["candidate"], request["rows"], request["training_mean"]
    validate_candidate(tree)
    predictions = [calculate(tree, row["x"]) for row in rows]
    errors = [(prediction - row["y"]) ** 2 for prediction, row in zip(predictions, rows, strict=True)]
    mse = sum(errors) / len(errors)
    baseline = sum((mean - row["y"]) ** 2 for row in rows) / len(rows)
    improvement = 1 - mse / baseline if baseline > 0 else 0
    return Verdict(mse=mse, baseline_mse=baseline, improvement=improvement,
        supported=mse <= request["threshold_mse"] and improvement >= request["minimum_improvement"],
        predictions=tuple(predictions), squared_errors=tuple(errors))


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.buffer.read(2_000_001))
        sys.stdout.write(canonical(evaluate(request)))
    except Exception as exc:
        sys.stderr.write(f"evaluation rejected: {type(exc).__name__}: {exc}\n")
        sys.exit(2)
