"""Host watchdog for credential-free container MCP stdio; never enters the image."""
import json
import signal
import subprocess
import sys
import threading

from research_loops.transports.launch import tool_environment


def main():
    config = json.loads(open(sys.argv[1], encoding="utf-8").read())
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
