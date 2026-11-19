"""Host watchdog for credential-free container MCP stdio; never enters the image."""
import json
import signal
import subprocess
import sys
import threading
from pathlib import Path

from research_loops.paths import long_path, plain_io_errors
from research_loops.transports.launch import tool_environment


def main():
    with plain_io_errors():
        config = json.loads(long_path(Path(sys.argv[1])).read_text(encoding="utf-8"))
    command = config["command"]
    runtime, name = command[0], command[command.index("--name") + 1]
    def remove():
        subprocess.run([runtime, "rm", "--force", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20, env=tool_environment())
    def stop(*_):
        raise SystemExit(124)
    signal.signal(signal.SIGTERM, stop)
    timer = threading.Timer(config["seconds"], remove)
    timer.daemon = True
    process = None
    try:
        process = subprocess.Popen(command, env=tool_environment())
        timer.start()
        raise SystemExit(process.wait())
    finally:
        timer.cancel()
        remove()
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
