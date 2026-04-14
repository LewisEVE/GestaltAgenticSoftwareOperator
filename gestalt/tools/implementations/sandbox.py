"""Sandboxed command execution tool."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gestalt.protocol import ToolExecutionMode
from gestalt.tools.base import BaseGestaltTool, ToolContext, ToolDescriptor


class SandboxCommandInput(BaseModel):
    """Input payload for sandbox command execution."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1)
    working_directory: str = "."
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class SandboxCommandOutput(BaseModel):
    """Result payload for sandbox command execution."""

    model_config = ConfigDict(extra="forbid")

    stdout: str = ""
    stderr: str = ""
    return_code: int


class SandboxCommandTool(BaseGestaltTool[SandboxCommandInput, SandboxCommandOutput]):
    """Execute an allowlisted shell command in a constrained subprocess."""

    descriptor = ToolDescriptor(
        name="sandbox_command",
        description="Execute a constrained shell command for planner-executor workflows.",
        execution_mode=ToolExecutionMode.SANDBOXED,
        timeout_seconds=30,
    )
    input_model = SandboxCommandInput
    output_model = SandboxCommandOutput

    def __init__(self, *, workspace_root: str = "/workspace") -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._blocked_terms = {"rm -rf /", "shutdown", "reboot", "mkfs", ":(){:|:&};:"}

    async def arun(self, payload: SandboxCommandInput, context: ToolContext) -> SandboxCommandOutput:
        """Execute a constrained command and return captured output."""

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
