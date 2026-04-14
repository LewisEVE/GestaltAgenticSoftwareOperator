"""Allowlisted outbound HTTP tool implementation."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from gestalt.config import SecurityConfig
from gestalt.protocol import ToolExecutionMode
from gestalt.tools.base import BaseTool, ToolContext, ToolDescriptor


class HttpRequestInput(BaseModel):
    """Input payload for outbound HTTP requests."""

    model_config = ConfigDict(extra="forbid")

    method: str = Field(default="GET", min_length=3, max_length=10)
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    timeout_seconds: int = Field(default=15, ge=1, le=60)


class HttpRequestOutput(BaseModel):
    """Normalized HTTP response payload."""

    model_config = ConfigDict(extra="forbid")

    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    text: str = ""


class HttpRequestTool(BaseTool):
    """Execute allowlisted outbound HTTP requests."""

    descriptor = ToolDescriptor(
        name="http_request",
        description="Performs allowlisted outbound HTTP requests for controlled integrations.",
        execution_mode=ToolExecutionMode.MUTATING,
        timeout_seconds=30,
    )
    input_model = HttpRequestInput
    output_model = HttpRequestOutput

    def __init__(self, security_config: SecurityConfig) -> None:
        self._allowlist = tuple(security_config.outbound_http_allowlist)

    async def arun(self, payload: HttpRequestInput, context: ToolContext) -> HttpRequestOutput:
        """Send an HTTP request after validating the allowlist."""

        if self._allowlist and not any(str(payload.url).startswith(prefix) for prefix in self._allowlist):
            msg = f"URL '{payload.url}' is not in the outbound allowlist."
            raise PermissionError(msg)

        async with httpx.AsyncClient(timeout=payload.timeout_seconds) as client:
            response = await client.request(
                payload.method.upper(),
                str(payload.url),
                headers=payload.headers,
                params=payload.params,
                json=payload.json_body,
            )
        return HttpRequestOutput(
            status_code=response.status_code,
            headers=dict(response.headers),
            text=response.text,
        )
