"""Independent stack-machine expression and exact-rational metric checker."""

from fractions import Fraction

from research_loops.domain import IntegrityError, Verdict, validate_candidate


def check(request: dict, verdict: Verdict) -> None:
    tree = request["candidate"]
    validate_candidate(tree)
    program = []
    stack = [(tree, False)]
    while stack:
        node, visited = stack.pop()
        if "op" in node and not visited:
            stack.extend([(node, True), (node["right"], False), (node["left"], False)])
        else:
            program.append(node)
    outputs = []
    for row in request["rows"]:
        values = []
        for instruction in program:
            if "constant" in instruction:
                values.append(Fraction(instruction["constant"]))
            elif "feature" in instruction:
                values.append(Fraction(row["x"][instruction["feature"]]))
            else:
                b, a = values.pop(), values.pop()
                values.append({"add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b}[instruction["op"]]())
        outputs.append(values.pop())
    errors = [(p - row["y"]) ** 2 for p, row in zip(outputs, request["rows"], strict=True)]
    mean = Fraction(str(request["training_mean"]))
    baseline = sum((mean - row["y"]) ** 2 for row in request["rows"]) / len(outputs)
    mse = sum(errors) / len(errors)
    improvement = 1 - mse / baseline
    expected_support = float(mse) <= request["threshold_mse"] and float(improvement) >= request["minimum_improvement"]
    if (list(verdict.predictions) != [float(p) for p in outputs]
        or list(verdict.squared_errors) != [float(e) for e in errors]
        or abs(verdict.mse - float(mse)) > 1e-12
        or abs(verdict.baseline_mse - float(baseline)) > 1e-12
        or abs(verdict.improvement - float(improvement)) > 1e-12
        or verdict.supported != expected_support):
        raise IntegrityError("independent stack/rational verifier disagrees")
