"""PlusVibe adapter backed by the validated legacy wire client."""
from __future__ import annotations

from typing import Any

from ..core import DecisionError, DecisionRequest, DecisionResult, ModelConfig
from ..legacy.client import DecisionClient as LegacyClient, DecisionClientError as LegacyError


class PlusVibeAdapter:
    name = "plusvibe"

    def __init__(self, *, api_key: str | None = None, endpoint: str | None = None,
                 timeout: float | None = None, transport: Any = None):
        self.api_key, self.endpoint, self.timeout, self.transport = api_key, endpoint, timeout, transport

    def decide(self, request: DecisionRequest, config: ModelConfig) -> DecisionResult:
        if config.provider != self.name:
            raise DecisionError("provider_config_mismatch")
        if config.pricing is not None and config.pricing.currency != "RUB":
            raise DecisionError("pricing_currency_mismatch")
        configured_endpoint = config.provider_settings.get("endpoint")
        configured_timeout = config.provider_settings.get("timeout")
        if self.endpoint is not None and configured_endpoint is not None and self.endpoint != configured_endpoint:
            raise DecisionError("provider_config_mismatch")
        if self.timeout is not None and configured_timeout is not None and self.timeout != configured_timeout:
            raise DecisionError("provider_config_mismatch")
        endpoint = self.endpoint or configured_endpoint
        timeout = self.timeout if self.timeout is not None else (configured_timeout or 60.0)
        price = config.pricing.input_per_million if config.pricing else None
        price_configured = price is not None
        wire_price = price if price_configured else 0.0
        kwargs: dict[str, Any] = {"model": config.model, "timeout": timeout,
                                  "price_rub_per_million": wire_price}
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        if endpoint is not None:
            kwargs["endpoint"] = endpoint
        if self.transport is not None:
            kwargs["transport"] = self.transport
        try:
            client = LegacyClient(**kwargs)
            legacy = client.decide(request.state, {
                key: {"type": "choice", "instructions": q.instructions, "criteria": dict(q.criteria)}
                for key, q in request.questions.items()
            })
        except LegacyError as exc:
            uncertain = exc.error_class in {"timeout", "transport_error"}
            raise DecisionError(exc.error_class, status=exc.status, billed_cost=exc.billed_cost_rub,
                                currency="RUB" if exc.billed_cost_rub is not None else None,
                                uncertain=uncertain,
                                billed_cost_provenance="PlusVibe x-pv-cost-rub response header" if exc.billed_cost_rub is not None else None,
                                billing_header_invalid=exc.billing_header_invalid) from None
        if legacy.billing_header_invalid:
            raise DecisionError("invalid_billing_header", status=200, billing_header_invalid=True)
        answers = {}
        for qid, answer in legacy.answers.items():
            clean = {k: v for k, v in answer.items() if k in {"type", "choice", "probabilities", "confidence"}}
            answers[qid] = clean
        price_info = config.pricing
        provenance = price_info.provenance if price_info else "adapter default; verify before cost planning"
        complete_price = price_info is not None and price_info.input_per_million is not None and price_info.output_per_million is not None
        estimated = ((legacy.usage['input_tokens'] * price_info.input_per_million
                      + legacy.usage['output_tokens'] * price_info.output_per_million) / 1_000_000
                     if complete_price else None)
        return DecisionResult.create(
            answer=legacy.answer, answers=answers, config=config,
            returned_model=legacy.returned_model, usage=legacy.usage,
            billed_cost=legacy.billed_cost_rub, billed_currency="RUB" if legacy.billed_cost_rub is not None else None,
            billed_cost_provenance="PlusVibe x-pv-cost-rub response header" if legacy.billed_cost_rub is not None else None,
            estimated_cost=estimated,
            estimated_currency="RUB" if complete_price else None,
            estimated_cost_provenance=provenance if complete_price else None,
            reused=legacy.cache_hit, elapsed_seconds=legacy.elapsed_seconds,
            model_version=legacy.model_version, billing_header_invalid=legacy.billing_header_invalid)
