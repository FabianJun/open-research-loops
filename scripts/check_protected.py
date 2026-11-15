"""Compare evaluator anchors with a trusted Git base, not a same-commit decision."""

import argparse
import json
import subprocess

from research_loops.protection import authorize_change, verify_anchor
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    current = verify_anchor()
    def read(path):
        result = subprocess.run(["git", "show", f"{args.base}:{path}"], capture_output=True, check=False)
        return json.loads(result.stdout) if result.returncode == 0 else None
    base = read("src/research_loops/evaluator-manifest.json")
    if base is None:
        # First introduction is checked by the tests/owner review, not a fabricated prior anchor.
        print("no evaluator anchor in trusted base; initial anchor requires owner review")
        return
    # Both identity and decisions come from the base, never the changed checkout.
    trusted_config = read("project.json") or {}
    current_config = json.loads(Path("project.json").read_bytes())
    authorize_change(
        {"anchor": base, "owner": trusted_config.get("owner")},
        {"anchor": current, "owner": current_config.get("owner")},
        trusted_config.get("evaluator_authorizations", []),
    )
    print("protected evaluator matches trusted base or prior human authorization")


if __name__ == "__main__":
    main()
