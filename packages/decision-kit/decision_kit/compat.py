"""Namespaced compatibility facade for legacy clients and cohort runners."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import ModelConfig, PricingInfo
from .cli import _validate_cases, read, run as _run, save
from .core import DecisionError
from .legacy.client import MODEL, ENDPOINT, DecisionClient, DecisionClientError, DecisionResult


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")


def prepare(cases: Any, model: str = MODEL, endpoint: str = ENDPOINT) -> list[dict[str, Any]]:
    config = ModelConfig("plusvibe", model, pricing=PricingInfo(
        "RUB", 7.4, 0, "PlusVibe typesafe/jev-1.13; https://gw.plusvibeapi.ru/models; verified 2026-11-07"),
        provider_settings={"endpoint": endpoint})
    prepared = _validate_cases(cases, config, max(1, len(cases) if isinstance(cases, list) else 1))
    return [{"case": item["case"], "payload": {"state": item["request"].state,
             "questions": {k: {"type": q.task, "instructions": q.instructions, "criteria": dict(q.criteria)}
                           for k, q in item["request"].questions.items()}},
             "fingerprint": item["fingerprint"], "estimated_upper_cost_rub": item["estimated_upper_cost"]}
            for item in prepared]


def run(cases: Any, output: str | Path, *, execute: bool = False,
        max_requests: int = 20, max_cost_rub: float = 1.0,
        client_factory: Any = None, model: str = MODEL, endpoint: str = ENDPOINT,
        **_: Any) -> dict[str, Any]:
    config = ModelConfig("plusvibe", model, pricing=PricingInfo(
        "RUB", 7.4, 0, "PlusVibe typesafe/jev-1.13; https://gw.plusvibeapi.ru/models; verified 2026-11-07"),
        provider_settings={"endpoint": endpoint})
    factory = client_factory
    if client_factory is not None:
        class LegacyFactoryAdapter:
            def __init__(self):
                self.client = client_factory()
            def decide(self, state, questions):
                try:
                    return self.client.decide(state=state, questions=questions)
                except DecisionClientError as exc:
                    raise DecisionError(exc.error_class, status=exc.status,
                        billed_cost=exc.billed_cost_rub,
                        currency="RUB" if exc.billed_cost_rub is not None else None,
                        uncertain=exc.error_class in {"timeout", "transport_error"}) from None
        factory = LegacyFactoryAdapter
    try:
        result = _run(cases, output, config=config, execute_calls=execute,
                      max_requests=max_requests, max_cost=max_cost_rub, client_factory=factory)
    finally:
        for receipt in (Path(output) / "receipts").glob("*.json"):
            item = read(receipt)
            item["billed_cost_rub"] = item.get("billed_cost")
            save(receipt, item)
    if "billed_cost_known" in result:
        result["billed_cost_rub_known"] = result["billed_cost_known"]
    return result


__all__ = ["DecisionClient", "DecisionClientError", "DecisionResult", "prepare", "read", "run", "save", "encoded"]
