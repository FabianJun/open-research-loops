"""Compute adapters for explicitly submitted, trusted jobs; no vendor SDKs."""

from research_loops.domain import IntegrityError


def load_backend(name, **options):
    # Match execution.load_backend: explicit names and lazy adapter imports.
    if name == "local":
        from research_loops.compute.local import LocalBackend
        return LocalBackend(**options)
    if name == "kaggle":
        from research_loops.compute.kaggle import KaggleBackend
        return KaggleBackend(**options)
    if name == "manual":
        from research_loops.compute.manual import ManualBackend
        return ManualBackend(**options)
    if name == "command":
        from research_loops.compute.command import CommandBackend
        return CommandBackend(**options)
    raise IntegrityError("unknown compute backend: " + name)
