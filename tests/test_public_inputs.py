import asyncio
import base64

import pytest

pytest.importorskip("mcp", reason="install research-loops[mcp] for transport input tests")

from research_loops.domain import IntegrityError, digest
from research_loops.tools import ToolService
from research_loops.transports.client import session, value
from research_loops.transports.launch import local_launch
from test_mcp import task
from test_sandbox import sandbox_image, container


@pytest.mark.parametrize("transport", ["direct", "stdio", "container"])
def test_public_training_read_only_and_hash_checked(transport, tmp_path, request):
    data = b'{"rows":[{"x":[1,2,3,4],"y":5}]}'
    assigned = task().model_copy(update={"input_hash": digest(data)})
    root = tmp_path / "run" / "outbox"
    public = root.parent / "public"
    public.mkdir(parents=True)
    training = public / "training.json"
    training.write_bytes(data)
    training.chmod(0o644)
    if transport == "direct":
        service = ToolService(assigned, root)
        assert service.read_artifact("inputs/training.json") == data
        service.register_variant(assigned.prediction)
        with pytest.raises(IntegrityError):
            service.write_artifact("inputs/training.json", b"bad")
        with pytest.raises(IntegrityError):
            service.read_artifact("inputs/final.json")
        training.write_bytes(b"tampered")
        with pytest.raises(IntegrityError, match="hash mismatch"):
            service.read_artifact("inputs/training.json")
        return
    sandbox = request.getfixturevalue("container") if transport == "container" else None
    launch = sandbox.tool_launch(assigned, root) if sandbox else local_launch(assigned, root)
    async def check():
        async with session(launch) as client:
            async def call(name, arguments):
                return value(await client.call_tool(name, arguments))
            result = await call("read_artifact", {"relative": "inputs/training.json"})
            assert result["ok"] and base64.b64decode(result["value"]["base64"]) == data
            assert not (await call("read_artifact", {"relative": "inputs/final.json"}))["ok"]
            assert not (await call("read_artifact", {"relative": "inputs/../worker-context.json"}))["ok"]
            assert (await call("register_variant", {"prediction": assigned.prediction}))["ok"]
            assert not (await call("write_artifact", {"relative": "inputs/training.json", "content": "YQ=="}))["ok"]
            training.write_bytes(b"tampered")
            assert not (await call("read_artifact", {"relative": "inputs/training.json"}))["ok"]
    try:
        asyncio.run(check())
    finally:
        if sandbox:
            sandbox.cleanup(root)
