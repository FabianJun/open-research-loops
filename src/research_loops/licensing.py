"""Small checks shared by future self-assessment; no legal inference."""

from pathlib import Path


def license_issues(root: Path, source_licenses: list[str]) -> list[str]:
    issues = []
    code = root / "LICENSE"
    docs = root / "LICENSE-CC-BY-4.0"
    if not code.exists() or "Apache License" not in code.read_text(encoding="utf-8") or "Version 2.0" not in code.read_text(encoding="utf-8"):
        issues.append("repository code license missing or differs from Apache-2.0")
    if not docs.exists() or "Attribution 4.0 International" not in docs.read_text(encoding="utf-8"):
        issues.append("documentation license missing or differs from CC-BY-4.0")
    for item in source_licenses:
        if item not in {"CC0-1.0", "CC-BY-4.0", "Apache-2.0", "MIT"}:
            issues.append(f"source license requires review: {item}")
    return issues
