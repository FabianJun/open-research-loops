"""Public SDK Transport with an explicit child environment (no global mutation)."""

import asyncio
import json
import os
import signal
import subprocess

from claude_agent_sdk import Transport
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

from research_loops.domain import IntegrityError
from research_loops.processes import WindowsJob


def child_environment(source, mode):
    # Credential precedence: code.claude.com/docs/en/authentication. Disable cloud
    # provider routing, tokens, profiles and federation as well as direct keys.
    result = {key: value for key, value in source.items()
        if not key.upper().startswith(("ANTHROPIC_", "CLAUDE_CODE_", "AWS_", "AZURE_", "GOOGLE_", "CLOUD_ML_"))
        and key.upper() not in {"CLAUDECODE", "CLAUDE_CONFIG_DIR", "CLAUDE_AGENT_SDK_CLIENT_APP"}}
    if mode == "api_key":
        key = source.get("ANTHROPIC_API_KEY")
        if not key:
            raise IntegrityError("explicit API-key mode requires ANTHROPIC_API_KEY")
        result["ANTHROPIC_API_KEY"] = key
    elif mode != "claude_code":
        raise IntegrityError("unknown Claude auth mode")
    result.update(CLAUDE_CODE_ENTRYPOINT="sdk-py", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
        CLAUDE_CODE_MAX_RETRIES="0", CLAUDE_CODE_RETRY_WATCHDOG="0", CLAUDE_CODE_DISABLE_BACKGROUND_TASKS="1",
        CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST="1")
    return result


class LoginTransport(Transport):
    def __init__(self, options, mode):
        self.options, self.mode = options, mode
        self.process = self.job = None
        self.lock = asyncio.Lock()

    async def connect(self):
        builder = SubprocessCLITransport(prompt="", options=self.options)
        builder._cli_path = builder._find_cli()
        command = builder._build_command()
        # --bare disables subscription credentials, so it is deliberately absent.
        # Explicit settings restrict auth and hooks while settings discovery is off.
        command += ["--no-session-persistence"]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, cwd=self.options.cwd,
            env=child_environment(os.environ, self.mode), start_new_session=os.name != "nt")
        if os.name == "nt":
            self.job = WindowsJob(self.process)

    async def write(self, data):
        async with self.lock:
            def send():
                self.process.stdin.write(data.encode())
                self.process.stdin.flush()
            await asyncio.to_thread(send)

    async def read_messages(self):
        while self.is_ready():
            raw = await asyncio.to_thread(self.process.stdout.readline, 1_000_001)
            if not raw:
                return
            if len(raw) > 1_000_000 or not raw.endswith(b"\n"):
                raise IntegrityError("oversized Claude protocol frame")
            try:
                value = json.loads(raw)
            except ValueError as exc:
                raise IntegrityError("invalid Claude protocol frame") from exc
            yield value

    async def end_input(self):
        if self.process:
            self.process.stdin.close()

    def is_ready(self):
        return self.process is not None and self.process.poll() is None

    async def close(self):
        if not self.process:
            return
        if self.job:
            self.job.close()
        elif os.name != "nt":
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await asyncio.to_thread(self.process.wait)
        self.process.stdin.close()
        self.process.stdout.close()
