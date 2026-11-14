"""MCP client helpers; imports stay outside the research core."""

import json
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from research_loops.transports.launch import Launch


@asynccontextmanager
async def session(launch: Launch):
    params = StdioServerParameters(command=launch.command, args=launch.args, env=launch.env, cwd=launch.cwd)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=20) as client:
            await client.initialize()
            yield client


def value(result) -> dict:
    if result.is_error:
        raise ValueError("MCP protocol/tool error: " + str(result.content))
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)
