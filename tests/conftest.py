import shutil
import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original_connect = socket.socket.connect
    def denied(*args, **kwargs):
        raise AssertionError("offline test attempted network access")
    def local_only(sock, address):
        # Windows asyncio implements its internal wakeup pipe with loopback sockets.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        return denied()
    monkeypatch.setattr(socket.socket, "connect", local_only)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setenv("OPENAI_API_KEY", "test-present-must-never-trigger-provider")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-present-must-never-trigger-provider")


@pytest.fixture
def example(tmp_path):
    folder = tmp_path / "research space ü" / "planted-signal"
    folder.mkdir(parents=True)
    shutil.copyfile(Path(__file__).parents[1] / "examples/planted-signal/contract.json", folder / "contract.json")
    return folder
