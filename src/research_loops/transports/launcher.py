"""Host launcher: exec the actual tool server with an allowlisted environment.

Claude's CLI can inherit host agent credentials; this launcher replaces that
environment before starting any tool implementation. It is not a worker tool.
"""

import os
import sys
import subprocess

from research_loops.transports.launch import tool_environment

if __name__ == "__main__":
    env = tool_environment()
    command = [sys.executable, "-I", "-m", "research_loops.transports.server", *sys.argv[1:]]
    if os.name == "nt":
        # Windows execve is spawn-and-exit: the MCP client would see a dead
        # launcher and close the channel while the actual server is still alive.
        from research_loops.processes import WindowsJob
        child = subprocess.Popen(command, env=env)
        job = WindowsJob(child)
        try:
            sys.exit(child.wait())
        finally:
            job.close()
    else:
        os.execve(sys.executable, command, env)
