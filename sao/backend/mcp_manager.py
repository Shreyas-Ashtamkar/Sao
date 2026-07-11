import json
import os
import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


_CONNECT_TIMEOUT_SECONDS = 30
_TOOL_TIMEOUT_SECONDS = 60


class MCPManager:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path or "~/.sao/mcp_servers.json").expanduser()
        self._exit_stack = None
        self._tools = {}

    async def connect_servers(self):
        if self._exit_stack is not None:
            return

        servers = self._load_servers()
        self._exit_stack = AsyncExitStack()
        try:
            for server_name, server_config in servers.items():
                await asyncio.wait_for(
                    self._connect_server(server_name, server_config),
                    timeout=_CONNECT_TIMEOUT_SECONDS,
                )
        except (Exception, asyncio.CancelledError):
            await self.close()
            raise

    async def close(self):
        if self._exit_stack is None:
            return

        exit_stack = self._exit_stack
        self._exit_stack = None
        self._tools.clear()
        await exit_stack.aclose()

    def get_tool_schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool_name, tool in self._tools.items()
        ]

    async def execute_tool(self, tool_name, args):
        try:
            tool = self._tools[tool_name]
        except KeyError as exc:
            raise ValueError(f"Unknown MCP tool: {tool_name}") from exc

        result = await asyncio.wait_for(
            tool["session"].call_tool(tool["source_name"], args),
            timeout=_TOOL_TIMEOUT_SECONDS,
        )
        return json.dumps(result.model_dump(mode="json"))

    def _load_servers(self):
        if not self.config_path.exists():
            return {}

        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid MCP configuration: {self.config_path}") from exc

        servers = config.get("servers")
        if not isinstance(servers, dict):
            raise ValueError("MCP configuration must contain a 'servers' object")

        return servers

    async def _connect_server(self, server_name, config):
        if not isinstance(server_name, str) or not server_name:
            raise ValueError("MCP server names must be non-empty strings")
        if not isinstance(config, dict):
            raise ValueError(f"MCP server '{server_name}' must be an object")

        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env")
        cwd = config.get("cwd")
        if not isinstance(command, str) or not command:
            raise ValueError(f"MCP server '{server_name}' requires a command")
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError(f"MCP server '{server_name}' args must be a string list")
        if env is not None and (
            not isinstance(env, dict)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in env.items())
        ):
            raise ValueError(f"MCP server '{server_name}' env must be a string map")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError(f"MCP server '{server_name}' cwd must be a string")

        parameters = StdioServerParameters(
            command=command,
            args=args,
            env={**os.environ, **env} if env is not None else None,
            cwd=cwd,
        )
        read_stream, write_stream = await self._exit_stack.enter_async_context(stdio_client(parameters))
        session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        tools = await session.list_tools()

        for tool in tools.tools:
            tool_name = f"{server_name}__{tool.name}"
            if tool_name in self._tools:
                raise ValueError(f"Duplicate MCP tool name: {tool_name}")
            self._tools[tool_name] = {
                "session": session,
                "source_name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
