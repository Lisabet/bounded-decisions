"""Provider-neutral contracts for bounded choice decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import json
from typing import Any, Mapping, Protocol


class DecisionError(Exception):
    """Safe structured failure. Provider payloads and secrets are never attached."""

    def __init__(self, error_class: str, *, status: int | None = None,
                 billed_cost: float | None = None, currency: str | None = None,
                 uncertain: bool = False, billed_cost_provenance: str | None = None,
                 billing_header_invalid: bool = False):
        self.error_class = error_class
        self.status = status
        self.billed_cost = billed_cost
        self.currency = currency
        self.uncertain = uncertain
        self.billed_cost_provenance = billed_cost_provenance
        self.billing_header_invalid = billing_header_invalid
        label = error_class + (f" (HTTP {status})" if status is not None else "")
        super().__init__(label)


@dataclass(frozen=True)
class PricingInfo:
    currency: str
    input_per_million: float | None = None
    output_per_million: float | None = None
    provenance: str = "unspecified"

    def __post_init__(self) -> None:
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError("pricing currency is required")
        for value in (self.input_per_million, self.output_per_million):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value) or value < 0):
                raise ValueError("pricing rates must be finite non-negative numbers")
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError("pricing provenance is required")


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    task_capabilities: frozenset[str] = frozenset({"choice"})
    limits: Mapping[str, int | float] = field(default_factory=dict)
    pricing: PricingInfo | None = None
    provider_settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("provider is required")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model is required")
        if not self.task_capabilities or any(not isinstance(x, str) or not x for x in self.task_capabilities):
            raise ValueError("task capabilities must be explicit")
        for key, value in self.limits.items():
            if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("limits must be named positive numbers")


@dataclass(frozen=True)
class ChoiceQuestion:
    instructions: str
    criteria: Mapping[str, str]
    task: str = "choice"

    def __post_init__(self) -> None:
        if self.task != "choice":
            raise ValueError("only choice questions are supported")
        if not isinstance(self.instructions, str) or not self.instructions.strip():
            raise ValueError("question instructions are required")
        if not isinstance(self.criteria, Mapping) or len(self.criteria) < 2:
            raise ValueError("at least two choices are required")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
               for k, v in self.criteria.items()):
            raise ValueError("criteria must map choice IDs to descriptions")


@dataclass(frozen=True)
class DecisionRequest:
    state: Any
    questions: Mapping[str, ChoiceQuestion]
    dependencies: Mapping[str, str] = field(default_factory=dict)
    rules_version: str = "1"

    def __post_init__(self) -> None:
        if not ((isinstance(self.state, str) and self.state.strip()) or
                (isinstance(self.state, (Mapping, list)) and len(self.state) > 0)):
            raise ValueError("non-empty decision state is required")
        if not isinstance(self.questions, Mapping) or not self.questions:
            raise ValueError("at least one question is required")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, ChoiceQuestion)
               for k, v in self.questions.items()):
            raise ValueError("questions must be named ChoiceQuestion values")
        if not isinstance(self.rules_version, str) or not self.rules_version:
            raise ValueError("rules_version is required")

    @classmethod
    def from_mapping(cls, state: Any, questions: Mapping[str, Mapping[str, Any]], **kwargs: Any) -> "DecisionRequest":
        built = {}
        for key, value in questions.items():
            if not isinstance(value, Mapping) or set(value) - {"type", "instructions", "criteria"}:
                raise ValueError("invalid question schema")
            if value.get("type", "choice") != "choice":
                raise ValueError("only choice questions are supported")
            built[key] = ChoiceQuestion(value.get("instructions"), value.get("criteria"))
        return cls(state, built, **kwargs)


@dataclass(frozen=True)
class DecisionResult:
    answer: Mapping[str, str]
    answers: Mapping[str, Mapping[str, Any]]
    status: str
    provider: str
    requested_model: str
    returned_model: str
    timestamp: str
    usage: Mapping[str, int]
    billed_cost: float | None
    billed_currency: str | None
    billed_cost_provenance: str | None
    estimated_cost: float | None
    estimated_currency: str | None
    estimated_cost_provenance: str | None
    receipt: str | None = None
    reused: bool = False
    elapsed_seconds: float | None = None
    model_version: str | None = None
    billing_header_invalid: bool = False

    @classmethod
    def create(cls, *, answer: Mapping[str, str], answers: Mapping[str, Mapping[str, Any]],
               config: ModelConfig, returned_model: str, usage: Mapping[str, int],
               billed_cost: float | None, billed_currency: str | None,
               billed_cost_provenance: str | None, estimated_cost: float | None,
               estimated_currency: str | None, estimated_cost_provenance: str | None,
               receipt: str | None = None, reused: bool = False,
               elapsed_seconds: float | None = None, model_version: str | None = None,
               billing_header_invalid: bool = False) -> "DecisionResult":
        return cls(answer, answers, "ok", config.provider, config.model, returned_model,
                   datetime.now(timezone.utc).isoformat(), usage, billed_cost, billed_currency,
                   billed_cost_provenance, estimated_cost, estimated_currency,
                   estimated_cost_provenance, receipt, reused, elapsed_seconds, model_version, billing_header_invalid)


class DecisionProvider(Protocol):
    def decide(self, request: DecisionRequest, config: ModelConfig) -> DecisionResult: ...


class ProviderRegistry:
    """Explicit registry with no implicit fallback provider."""
    def __init__(self) -> None:
        self._providers: dict[str, DecisionProvider] = {}

    def register(self, name: str, provider: DecisionProvider) -> None:
        if not isinstance(name, str) or not name.strip() or name in self._providers:
            raise ValueError("provider name must be unique and non-empty")
        self._providers[name] = provider

    def get(self, name: str) -> DecisionProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise DecisionError("unsupported_provider") from None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


def execute(request: DecisionRequest, config: ModelConfig, registry: ProviderRegistry) -> DecisionResult:
    if "choice" not in config.task_capabilities:
        raise DecisionError("unsupported_task")
    question_limit = config.limits.get("questions")
    if question_limit is not None and len(request.questions) > question_limit:
        raise DecisionError("question_limit_exceeded")
    byte_limit = config.limits.get("request_bytes")
    if byte_limit is not None:
        try:
            wire_size = len(json.dumps({"state": request.state, "questions": {
                k: {"type": q.task, "instructions": q.instructions, "criteria": dict(q.criteria)}
                for k, q in request.questions.items()}}, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError, UnicodeError):
            raise DecisionError("invalid_request_json") from None
        if wire_size > byte_limit:
            raise DecisionError("request_byte_limit_exceeded")
    result = registry.get(config.provider).decide(request, config)
    try:
        validate_result(result, request, config)
    except DecisionError as exc:
        if (isinstance(result, DecisionResult) and isinstance(result.billed_cost, (int, float))
                and not isinstance(result.billed_cost, bool) and math.isfinite(result.billed_cost)
                and result.billed_cost >= 0 and isinstance(result.billed_currency, str)
                and result.billed_currency):
            raise DecisionError(exc.error_class, billed_cost=result.billed_cost,
                                currency=result.billed_currency,
                                billed_cost_provenance=result.billed_cost_provenance,
                                billing_header_invalid=result.billing_header_invalid) from None
        raise
    return result


def validate_result(result: Any, request: DecisionRequest, config: ModelConfig) -> None:
    """Validate provider output centrally, regardless of adapter implementation."""
    if not isinstance(result, DecisionResult):
        raise DecisionError("invalid_provider_result")
    if result.status != "ok" or result.provider != config.provider or result.requested_model != config.model:
        raise DecisionError("provider_model_mismatch")
    if result.returned_model != config.model:
        raise DecisionError("returned_model_mismatch")
    expected = set(request.questions)
    if not isinstance(result.answer, Mapping) or set(result.answer) != expected or not isinstance(result.answers, Mapping) or set(result.answers) != expected:
        raise DecisionError("answer_keys_mismatch")
    for qid, question in request.questions.items():
        choice = result.answer[qid]
        detail = result.answers[qid]
        if not isinstance(choice, str) or choice not in question.criteria or not isinstance(detail, Mapping) or detail.get("choice") != choice:
            raise DecisionError("invalid_choice")
        probabilities = detail.get("probabilities")
        if "probabilities" in detail:
            if not isinstance(probabilities, Mapping) or set(probabilities) != set(question.criteria):
                raise DecisionError("invalid_probabilities")
            values = list(probabilities.values())
            if (any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 or x > 1 for x in values)
                    or abs(sum(values) - 1.0) > 0.02):
                raise DecisionError("invalid_probabilities")
        confidence = detail.get("confidence")
        if "confidence" in detail and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise DecisionError("invalid_confidence")
    if not isinstance(result.usage, Mapping) or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > 9007199254740991 for v in result.usage.values()):
        raise DecisionError("invalid_usage")
    for value in (result.billed_cost, result.estimated_cost, result.elapsed_seconds):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
            raise DecisionError("invalid_cost_or_elapsed")
    if result.billed_cost is not None and (not isinstance(result.billed_currency, str) or not result.billed_currency):
        raise DecisionError("missing_billed_currency")
    if result.estimated_cost is not None and (not isinstance(result.estimated_currency, str) or not result.estimated_currency):
        raise DecisionError("missing_estimated_currency")
    if config.pricing is not None:
        if result.billed_currency is not None and result.billed_currency != config.pricing.currency:
            raise DecisionError("billed_currency_mismatch")
        if result.estimated_currency is not None and result.estimated_currency != config.pricing.currency:
            raise DecisionError("estimated_currency_mismatch")
