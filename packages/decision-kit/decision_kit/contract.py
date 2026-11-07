"""Language-neutral bounded-decisions/1 record mapping; caller owns durable storage."""
from __future__ import annotations
from typing import Any
from .core import DecisionResult, DecisionError, ModelConfig

CONTRACT_VERSION = "bounded-decisions/1"


def to_record(value: DecisionResult | DecisionError, config: ModelConfig, *,
              receipt_id: str | None = None, reused: bool | None = None) -> dict[str, Any]:
    """Map an accepted result or safe error; preserve unknown cost as null."""
    success = isinstance(value, DecisionResult)
    if not success and not isinstance(value, DecisionError):
        raise TypeError("expected normalized result or DecisionError")
    cost = value.billed_cost
    source = value.billed_cost_provenance
    currency = value.billed_currency if success else value.currency
    billing = {"amount": cost, "currency": currency, "source": source} if cost is not None else None
    usage = None
    if success and value.usage:
        usage = {k: value.usage[k] for k in ("input_tokens", "output_tokens") if k in value.usage}
        # Explicit legacy provider aliases used by existing generic adapters.
        for original, canonical in (("input", "input_tokens"), ("output", "output_tokens")):
            if canonical not in usage and original in value.usage: usage[canonical] = value.usage[original]
    answers = {k: {"type": "choice", **{f: d[f] for f in ("choice", "probabilities", "confidence") if f in d}}
               for k, d in value.answers.items()} if success else {}
    code = None
    if not success:
        name = value.error_class
        code = {"http_error": "http", "timeout": "timeout", "transport_error": "transport",
                "request_byte_limit_exceeded": "input_limit", "missing_api_key": "route"}.get(name, "invalid_response")
    return {"contract_version": CONTRACT_VERSION, "provider": config.provider,
            "requested_model": config.model, "returned_model": value.returned_model if success else None,
            "status": "ok" if success else ("pending" if value.uncertain else "error"),
            "answers": answers, "usage": usage, "billing": billing,
            "billing_state": "invalid" if value.billing_header_invalid else ("observed" if billing else "unknown"),
            "estimate": {"amount": value.estimated_cost, "currency": value.estimated_currency,
                         "source": value.estimated_cost_provenance} if success and value.estimated_cost is not None else None,
            "receipt": {"id": receipt_id if receipt_id is not None else (value.receipt if success else None),
                        "reused": reused if reused is not None else (value.reused if success else False)},
            "uncertain": False if success else value.uncertain,
            "error": None if success else {"code": code, "http_status": value.status}}
