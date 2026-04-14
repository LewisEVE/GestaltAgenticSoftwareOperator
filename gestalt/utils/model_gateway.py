"""LiteLLM-backed model gateway with a deterministic mock mode."""

from __future__ import annotations

from typing import Any, TypeVar, cast

from litellm import acompletion
from pydantic import BaseModel

from gestalt.config import ModelsConfig
from gestalt.stats import GestaltStats
from gestalt.utils.logging import get_logger

logger = get_logger(__name__)
ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class ModelGateway:
    """Centralized model selection and structured output execution."""

    def __init__(self, config: ModelsConfig) -> None:
        self._config = config

    @property
    def mock_enabled(self) -> bool:
        """Return whether the gateway should avoid external LLM calls."""

        return self._config.enable_mock_llm

    def select_model(self, stats: GestaltStats, preferred_tier: str | None = None) -> str:
        """Select a model alias using stats-aware routing plus an optional override."""

        route = preferred_tier or stats.derive_model_policy()["preferred_route"]
        if route == "critical":
            return self._config.routes.critical
        if route == "high":
            return self._config.routes.high
        if route == "medium":
            return self._config.routes.medium
        return self._config.routes.low or self._config.default_alias

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModelT],
        stats: GestaltStats,
        preferred_tier: str | None = None,
        mock_payload: dict[str, Any] | None = None,
    ) -> ResponseModelT:
        """Return a validated structured response using LiteLLM or mock mode."""

        model_name = self.select_model(stats, preferred_tier=preferred_tier)
        if self.mock_enabled or model_name.startswith("mock://"):
            if mock_payload is None:
                msg = "Mock payload is required when the model gateway runs in mock mode."
                raise ValueError(msg)
            return response_model.model_validate(mock_payload)

        logger.info("issuing structured model completion", extra={"model": model_name})
        response = await acompletion(
            model=model_name,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_model,
        )
        parsed = cast(Any, response).choices[0].message.parsed
        if parsed is None:
            msg = "LiteLLM did not return a parsed structured response."
            raise ValueError(msg)
        return response_model.model_validate(parsed)
