"""Worker-facing description of the anchored evaluator grammar.

Conformance tests pin this description and diagnostics to domain.validate_candidate.
The anchored validator remains the authority for acceptance.
"""

from research_loops.domain import IntegrityError, validate_candidate


CANDIDATE_GRAMMAR = (
    'Each node is exactly one of: {"op":"add"|"sub"|"mul","left":node,"right":node}, '
    '{"feature":integer 0..3}, or {"constant":integer -10..10}. '
    'No extra keys; booleans are not integers. Maximum depth is 4 (root depth 0); '
    'maximum total nodes is 31. Example: '
    '{"op":"mul","left":{"constant":2},"right":{"feature":0}}.'
)


def validate_submission(candidate) -> None:
    try:
        validate_candidate(candidate)
    except IntegrityError:
        # Fixed messages only: never echo untrusted candidate values in errors.
        count = 0

        def explain(node, depth=0):
            nonlocal count
            count += 1
            if depth > 4:
                return "candidate depth must be at most 4 (root depth 0)"
            if count > 31:
                return "candidate must contain at most 31 nodes"
            if not isinstance(node, dict):
                return "each candidate node must be a JSON object"
            if set(node) == {"feature"}:
                return "feature must be an integer in 0..3 (not a boolean)" if type(node["feature"]) is not int or not 0 <= node["feature"] <= 3 else None
            if set(node) == {"constant"}:
                return "constant must be an integer in -10..10 (not a boolean)" if type(node["constant"]) is not int or not -10 <= node["constant"] <= 10 else None
            if set(node) != {"op", "left", "right"}:
                return "candidate node keys must be exactly feature, constant, or op/left/right; replace args with left and right"
            if node["op"] not in ("add", "sub", "mul"):
                return "candidate op must be add, sub, or mul"
            return explain(node["left"], depth + 1) or explain(node["right"], depth + 1)

        raise IntegrityError(explain(candidate) or "candidate must follow the bounded expression grammar") from None
