FROM ghcr.io/astral-sh/uv@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_CACHE_DIR=/tmp/uv-cache PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --extra mcp --no-dev --no-install-project
# Deliberate allowlist: no evaluator, data, storage, SDKs, refs or host credentials.
COPY src/research_loops/__init__.py src/research_loops/domain.py src/research_loops/reports.py src/research_loops/paths.py src/research_loops/candidate_schema.py src/research_loops/tools.py /opt/venv/lib/python3.12/site-packages/research_loops/
COPY src/research_loops/transports/__init__.py src/research_loops/transports/server.py src/research_loops/transports/protocol.py /opt/venv/lib/python3.12/site-packages/research_loops/transports/
USER 1000:1000
WORKDIR /workspace
ENTRYPOINT ["/opt/venv/bin/python", "-I", "-m", "research_loops.transports.server"]
