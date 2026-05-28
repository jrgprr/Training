from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .ai_assessment_models import AssessmentRunStatus


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GatewayInvocation:
    profile_key: str
    instruction_version: str
    prompt_text: str
    provider_key: str | None = None
    model_name: str | None = None
    timeout_seconds: int = 60
    context_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256(self.prompt_text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GatewayResult:
    run_status: AssessmentRunStatus
    provider_key: str | None
    model_name: str | None
    instruction_version: str
    prompt_hash: str
    output_text: str | None = None
    failure_code: str | None = None
    failure_detail: str | None = None
    started_at: str = field(default_factory=_utc_now_iso)
    completed_at: str = field(default_factory=_utc_now_iso)


class GatewayProvider(Protocol):
    def invoke(self, invocation: GatewayInvocation) -> str:
        ...


class GatewayConfigurationError(RuntimeError):
    pass


class GatewayInvocationError(RuntimeError):
    pass


class NullGatewayProvider:
    def invoke(self, invocation: GatewayInvocation) -> str:
        raise GatewayConfigurationError(
            "No AI assessment provider is configured. Set AI_ASSESSMENT_PROVIDER and register a provider implementation."
        )


class AssessmentLLMGateway:
    def __init__(self, providers: dict[str, GatewayProvider] | None = None) -> None:
        self._providers = providers or {}

    def register_provider(self, provider_key: str, provider: GatewayProvider) -> None:
        self._providers[provider_key] = provider

    def invoke(self, invocation: GatewayInvocation) -> GatewayResult:
        started_at = _utc_now_iso()
        provider_key = invocation.provider_key or os.getenv("AI_ASSESSMENT_PROVIDER")
        model_name = invocation.model_name or os.getenv("AI_ASSESSMENT_MODEL")
        provider = self._providers.get(provider_key) if provider_key else None

        if provider is None:
            provider = NullGatewayProvider()

        try:
            output_text = provider.invoke(invocation)
        except TimeoutError as exc:
            return GatewayResult(
                run_status=AssessmentRunStatus.FAILED,
                provider_key=provider_key,
                model_name=model_name,
                instruction_version=invocation.instruction_version,
                prompt_hash=invocation.prompt_hash,
                failure_code="timeout",
                failure_detail=str(exc),
                started_at=started_at,
                completed_at=_utc_now_iso(),
            )
        except (GatewayConfigurationError, GatewayInvocationError) as exc:
            return GatewayResult(
                run_status=AssessmentRunStatus.FAILED,
                provider_key=provider_key,
                model_name=model_name,
                instruction_version=invocation.instruction_version,
                prompt_hash=invocation.prompt_hash,
                failure_code="provider_error",
                failure_detail=str(exc),
                started_at=started_at,
                completed_at=_utc_now_iso(),
            )
        except Exception as exc:
            return GatewayResult(
                run_status=AssessmentRunStatus.FAILED,
                provider_key=provider_key,
                model_name=model_name,
                instruction_version=invocation.instruction_version,
                prompt_hash=invocation.prompt_hash,
                failure_code="unexpected_error",
                failure_detail=str(exc),
                started_at=started_at,
                completed_at=_utc_now_iso(),
            )

        return GatewayResult(
            run_status=AssessmentRunStatus.COMPLETED,
            provider_key=provider_key,
            model_name=model_name,
            instruction_version=invocation.instruction_version,
            prompt_hash=invocation.prompt_hash,
            output_text=output_text,
            started_at=started_at,
            completed_at=_utc_now_iso(),
        )