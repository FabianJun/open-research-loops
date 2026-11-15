# Disposable Linux test driver, including actual sibling worker containers.
# The Docker socket belongs to the trusted test driver only, never a worker.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$suffix = [guid]::NewGuid().ToString('N')
$volumeName = "rloop-verification-$suffix"
$driverName = "rloop-verification-$suffix"
$baseImage = 'ghcr.io/astral-sh/uv@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58'
try {
    docker build --file (Join-Path $repoRoot 'Containerfile') --iidfile (Join-Path $repoRoot '.sandbox-image') $repoRoot
    if ($LASTEXITCODE -ne 0) { throw 'Worker image build failed' }
    $workerImage = (Get-Content (Join-Path $repoRoot '.sandbox-image') -Raw).Trim()
    docker volume create $volumeName
    if ($LASTEXITCODE -ne 0) { throw 'Temporary volume creation failed' }
    $daemonRoot = docker volume inspect $volumeName --format '{{.Mountpoint}}'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve temporary volume' }
    $linuxCommand = 'apt-get update -qq && apt-get install -y -qq --no-install-recommends docker.io git && git config --global --add safe.directory /workspace && uv sync --locked --all-extras && uv run --locked pytest -q -o cache_dir=/tmp/pytest-cache && uv run --locked python scripts/measure_init.py && uv run --locked python scripts/check_protected.py --base HEAD && uv build --out-dir /tmp/rloop-dist'
    docker run --rm --name $driverName `
        --mount "type=bind,source=$repoRoot,target=/workspace,readonly" `
        --mount "type=volume,source=$volumeName,target=/test-temp" `
        --mount 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock' `
        --workdir /workspace --env UV_PROJECT_ENVIRONMENT=/tmp/rloop-venv --env UV_CACHE_DIR=/tmp/uv-cache `
        --env TMPDIR=/test-temp --env RLOOP_DRIVER_ROOT=/test-temp --env "RLOOP_DAEMON_ROOT=$daemonRoot" `
        --env "RLOOP_SANDBOX_IMAGE=$workerImage" $baseImage /bin/sh -c $linuxCommand
    if ($LASTEXITCODE -ne 0) { throw 'Linux verification failed' }
} finally {
    docker rm --force $driverName 2>$null | Out-Null
    docker volume rm $volumeName
    if ($LASTEXITCODE -ne 0) { throw 'Temporary Linux volume cleanup failed' }
}
exit 0
