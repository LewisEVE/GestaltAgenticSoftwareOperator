"""Sandboxed command execution tool."""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from gestalt.protocol import ToolExecutionMode
from gestalt.tools.base import BaseGestaltTool, ToolDescriptor, ToolExecutionRequest


class SandboxCommandInput(BaseModel):
    """Input payload for sandbox command execution."""

    command: str = Field(min_length=1)
    working_directory: str = "."
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class SandboxCommandOutput(BaseModel):
    """Result payload for sandbox command execution."""

    stdout: str = ""
    stderr: str = ""
    return_code: int


class SandboxCommandTool(BaseGestaltTool[SandboxCommandInput, SandboxCommandOutput]):
    """Execute an allowlisted shell command in a constrained subprocess."""

    name = "sandbox_command"
    descriptor = ToolDescriptor(
        name=name,
        description="Execute a constrained shell command for planner-executor workflows.",
        execution_mode=ToolExecutionMode.SANDBOXED,
        timeout_seconds=30,
    )
    input_model = SandboxCommandInput
    output_model = SandboxCommandOutput

    def __init__(self, *, workspace_root: str = "/workspace") -> None:
        super().__init__()
        self._workspace_root = Path(workspace_root).resolve()
        self._blocked_terms = {"rm -rf /", "shutdown", "reboot", "mkfs", ":(){:|:&};:"}

    async def _arun_impl(
        self,
        payload: SandboxCommandInput,
        request: ToolExecutionRequest,
    ) -> SandboxCommandOutput:
        lowered = payload.command.lower()
        for blocked in self._blocked_terms:
            if blocked in lowered:
                raise PermissionError(f"Blocked sandbox command pattern detected: {blocked}")

        working_directory = (self._workspace_root / payload.working_directory).resolve()
        if not str(working_directory).startswith(str(self._workspace_root)):
            raise PermissionError("Sandbox working directory escapes workspace root.")

        process = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            payload.command,
            cwd=str(working_directory),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=payload.timeout_seconds)
        return SandboxCommandOutput(
            stdout=stdout.decode("utf-8"),
            stderr=stderr.decode("utf-8"),
            return_code=process.returncode or 0,
        )
