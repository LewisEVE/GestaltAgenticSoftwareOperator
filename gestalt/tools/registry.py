"""Centralized tool registration and allowlist enforcement."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from gestalt.tools.base import BaseGestaltTool, ToolContext, ToolExecutionRequest


class ToolPermissionError(PermissionError):
    """Raised when an agent attempts to use a forbidden tool."""


class ToolRegistry:
    """Registry that stores and resolves tools by name."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseGestaltTool[Any, Any]] = {}

    def register(self, tool: BaseGestaltTool[Any, Any]) -> None:
        """Register a tool instance by descriptor name."""

        self._tools[tool.name] = tool

    def bulk_register(self, tools: Iterable[BaseGestaltTool[Any, Any]]) -> None:
        """Register several tool instances."""

        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> BaseGestaltTool[Any, Any]:
        """Return a registered tool or raise KeyError."""

        return self._tools[name]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""

        return sorted(self._tools)

    def list_allowed_tools(self, allowlist: Iterable[str]) -> list[BaseGestaltTool[Any, Any]]:
        """Resolve the subset of tools named in the allowlist."""

        names = set(allowlist)
        return [tool for name, tool in self._tools.items() if name in names]

    async def execute_allowed(
        self,
        *,
        tool_name: str,
        request: ToolExecutionRequest,
        allowlist: Iterable[str],
    ) -> BaseModel:
        """Execute a tool only if it appears in the allowlist."""

        if tool_name not in set(allowlist):
            msg = f"Tool '{tool_name}' is not allowed for agent '{request.agent_name}'."
            raise ToolPermissionError(msg)
        tool = self.get(tool_name)
        return await tool.execute(request)
