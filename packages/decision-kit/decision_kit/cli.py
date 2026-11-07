"""Plan and execute bounded, resumable decision cohorts."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable

from . import __version__
from .core import (DecisionError, DecisionRequest, DecisionResult, ModelConfig, PricingInfo,
                   ProviderRegistry, execute, validate_result)
from .providers import PlusVibeAdapter
from .contract import to_record


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def read(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = encoded(value)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def config_from_mapping(data: dict[str, Any]) -> ModelConfig:
    allowed = {"provider", "model", "task_capabilities", "limits", "pricing", "provider_settings", "endpoint", "timeout"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("invalid config fields")
    pricing_data = data.get("pricing")
    pricing = None
    if pricing_data is not None:
        if not isinstance(pricing_data, dict) or set(pricing_data) != {
                "currency", "input_per_million", "output_per_million", "provenance"}:
            raise ValueError("pricing requires currency, input_per_million, output_per_million, provenance")
        pricing = PricingInfo(**pricing_data)
    capabilities = data.get("task_capabilities", ["choice"])
    if not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities):
        raise ValueError("task_capabilities must be a list of strings")
    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        raise ValueError("limits must be an object")
    raw_settings = data.get("provider_settings", {})
    if not isinstance(raw_settings, dict):
        raise ValueError("provider_settings must be an object")
    settings = dict(raw_settings)
    for key in ("endpoint", "timeout"):
        if key in data:
            settings[key] = data[key]
    return ModelConfig(data.get("provider"), data.get("model"), frozenset(capabilities), limits, pricing, settings)


def _validate_cases(cases: Any, config: ModelConfig, max_requests: int) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty array")
    if len(cases) > max_requests:
        raise ValueError("request limit is below cohort size")
    seen: set[str] = set()
    prepared = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each case must be an object")
        allowed = {"case_id", "state", "question", "expected", "dependencies", "cache_context", "decision_evidence", "source_ids", "rules_version", "cohort", "task_kind", "case_origin", "decision_relation"}
        if set(case) - allowed or not isinstance(case.get("case_id"), str) or not case["case_id"]:
            raise ValueError("invalid case fields or case_id")
        if case["case_id"] in seen:
            raise ValueError("case_id must be unique")
        seen.add(case["case_id"])
        question = case.get("question")
        if not isinstance(question, dict) or set(question) != {"type", "instructions", "criteria"} or question["type"] != "choice":
            raise ValueError("question must use the explicit choice schema")
        request = DecisionRequest.from_mapping(case.get("state"), {"decision": question},
                    dependencies=case.get("dependencies", {}), rules_version=case.get("rules_version", "1"))
        criteria = request.questions["decision"].criteria
        if "insufficient" not in criteria:
            raise ValueError("an explicit insufficient option is required")
        if "expected" in case and case["expected"] not in criteria:
            raise ValueError("expected answer must be one of the declared choices")
        if not isinstance(request.dependencies, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                            for k, v in request.dependencies.items()):
            raise ValueError("dependencies must map names to version strings")
        payload = {"provider": config.provider, "model": config.model, "state": request.state,
                   "questions": {k: {"type": v.task, "instructions": v.instructions,
                                     "criteria": dict(v.criteria)} for k, v in request.questions.items()},
                   "dependencies": dict(request.dependencies), "rules_version": request.rules_version}
        if len(encoded(payload)) > int(config.limits.get("request_bytes", 100_000)):
            raise ValueError("case exceeds configured request byte limit")
        if "expected" in case:
            if not isinstance(case["expected"], str):
                raise ValueError("expected must be a choice ID")
        price_in = config.pricing.input_per_million if config.pricing else None
        price_out = config.pricing.output_per_million if config.pricing else None
        upper = ((len(encoded(payload)) * price_in + 4096 * price_out) / 1_000_000
                 if price_in is not None and price_out is not None else None)
        fingerprint_payload = {**payload, "expected": case.get("expected")}
        fingerprint_payload["cache_context"] = {"cache_context": case.get("cache_context"),
                                                  "decision_evidence": case.get("decision_evidence")}
        fingerprint_payload["provider_settings"] = dict(config.provider_settings)
        prepared.append({"case": case, "request": request,
                         "fingerprint": hashlib.sha256(encoded(fingerprint_payload)).hexdigest(),
                         "estimated_upper_cost": upper})
    return prepared


def _cohort(case: dict[str, Any]) -> str:
    return str(case.get("cohort", case.get("task_kind", case.get("decision_relation",
                case.get("case_origin", "unspecified")))))


def run(cases: Any, output: str | Path, *, config: ModelConfig,
        registry: ProviderRegistry | None = None, execute_calls: bool = False,
        max_requests: int = 20, max_cost: float = 1.0,
        client_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    if isinstance(max_requests, bool) or not isinstance(max_requests, int) or max_requests <= 0:
        raise ValueError("max_requests must be a positive integer")
    if isinstance(max_cost, bool) or not isinstance(max_cost, (int, float)) or not math.isfinite(max_cost) or max_cost < 0:
        raise ValueError("max_cost must be a non-negative number")
    prepared = _validate_cases(cases, config, max_requests)
    estimates = [x["estimated_upper_cost"] for x in prepared]
    estimate_total = sum(estimates) if all(x is not None for x in estimates) else None
    if execute_calls:
        if config.pricing is None or config.pricing.input_per_million is None or config.pricing.output_per_million is None:
            raise ValueError("execution requires explicit input/output pricing and provenance")
        if estimate_total is None:
            raise ValueError("execution requires a usable cost estimate")
        if estimate_total > max_cost:
            raise ValueError("cost limit is below planned estimate")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plan = {"decision_kit_version": __version__, "provider": config.provider, "model": config.model,
            "cases": len(prepared), "estimated_upper_cost": estimate_total,
            "currency": config.pricing.currency if config.pricing else None,
            "pricing_provenance": config.pricing.provenance if config.pricing else None,
            "max_requests": max_requests, "max_cost": max_cost,
            "execute": execute_calls, "automatic_retries": 0}
    save(output / "plan.json", plan)
    if not execute_calls:
        return {**plan, "status": "planned", "new_requests_this_run": 0, "reused_receipts": 0}
    lock = output / "execution.lock"
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("evaluation is already owned (an owner already has the lock); inspect before recovery") from None
    records = []
    new_calls = 0
    started = time.perf_counter()
    provider_registry = registry
    if provider_registry is None:
        provider_registry = ProviderRegistry()
        provider_registry.register("plusvibe", PlusVibeAdapter())
    try:
        with os.fdopen(lock_fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}))
            stream.flush()
            os.fsync(stream.fileno())
        config_identity = {"provider": config.provider, "model": config.model,
            "task_capabilities": sorted(config.task_capabilities), "limits": dict(config.limits),
            "pricing": asdict(config.pricing) if config.pricing else None,
            "provider_settings": dict(config.provider_settings)}
        manifest = {"config": config_identity,
                    "cases": [{"case_id": item["case"]["case_id"], "fingerprint": item["fingerprint"]}
                              for item in prepared]}
        manifest["manifest_sha256"] = hashlib.sha256(encoded(manifest)).hexdigest()
        manifest_path = output / "cohort.json"
        if manifest_path.exists() and read(manifest_path) != manifest:
            raise ValueError("output directory belongs to a changed case or changed inputs, cohort, or provider configuration")
        old_records = []
        missing_receipt = False
        has_unknown_spend = False
        for item in prepared:
            case = item["case"]
            receipt = output / "receipts" / (hashlib.sha256(case["case_id"].encode()).hexdigest()[:24] + ".json")
            if not receipt.exists():
                missing_receipt = True
                continue
            old = read(receipt)
            if old.get("fingerprint") != item["fingerprint"]:
                raise ValueError("saved receipt belongs to changed inputs or local dependency versions")
            if old.get("status") == "pending":
                raise ValueError("pending request has uncertain prior outcome; reconcile its receipt before resuming")
            if old.get("status") not in {"ok", "error", "unknown_spend"}:
                raise ValueError("saved receipt has an unsupported status")
            billed = old.get("billed_cost")
            if billed is not None and (isinstance(billed, bool) or not isinstance(billed, (int, float))
                                       or not math.isfinite(billed) or billed < 0):
                raise ValueError("saved receipt has invalid billed cost")
            if billed is not None and old.get("currency") != config.pricing.currency:
                raise ValueError("saved receipt currency differs from configured budget currency")
            if old.get("status") == "ok":
                try:
                    saved_result = DecisionResult(**old["result"])
                    validate_result(saved_result, item["request"], config)
                except (KeyError, TypeError, ValueError, DecisionError):
                    raise ValueError("saved successful receipt has an invalid normalized result") from None
            if billed is None:
                has_unknown_spend = True
            old_records.append(old)
        if has_unknown_spend and missing_receipt:
            raise ValueError("unknown prior spend stops the next paid request")
        if not manifest_path.exists():
            save(manifest_path, manifest)
        charged = sum(x["billed_cost"] for x in old_records if x.get("billed_cost") is not None)
        unknown_spend = False
        new_records = []
        for item in prepared:
            case = item["case"]
            receipt_path = output / "receipts" / (hashlib.sha256(case["case_id"].encode()).hexdigest()[:24] + ".json")
            if receipt_path.exists():
                old = read(receipt_path)
                records.append(old)
                continue
            if unknown_spend:
                raise ValueError("unknown prior spend stops the next paid request")
            if new_calls >= max_requests:
                raise ValueError("request limit reached")
            upper = item["estimated_upper_cost"]
            if upper is not None and charged + upper > max_cost:
                raise ValueError("remaining cost budget exhausted")
            if client_factory is not None:
                # Legacy/testing hook; normal CLI execution always uses the registered provider.
                provider = client_factory()
                def call_provider(request: DecisionRequest, model_config: ModelConfig) -> Any:
                    raw = provider.decide(request.state, {k: {"type": q.task, "instructions": q.instructions,
                        "criteria": dict(q.criteria)} for k, q in request.questions.items()})
                    if isinstance(raw, DecisionResult):
                        return raw
                    if hasattr(raw, "answer") and hasattr(raw, "answers"):
                        return DecisionResult.create(answer=raw.answer, answers=raw.answers,
                            config=model_config, returned_model=raw.returned_model,
                            usage=raw.usage, billed_cost=raw.billed_cost_rub,
                            billed_currency="RUB" if raw.billed_cost_rub is not None else None,
                            billed_cost_provenance="PlusVibe response header" if raw.billed_cost_rub is not None else None,
                            estimated_cost=raw.estimated_cost_rub, estimated_currency="RUB",
                            estimated_cost_provenance="legacy adapter estimate",
                            elapsed_seconds=raw.elapsed_seconds, model_version=raw.model_version)
                    raise DecisionError("invalid_provider_result")
                adapter = call_provider
            else:
                adapter = lambda request, model_config: execute(request, model_config, provider_registry)
            record = {"case_id": case["case_id"], "fingerprint": item["fingerprint"],
                      "status": "pending", "provider": config.provider, "model": config.model,
                      "cohort": _cohort(case), "expected": case.get("expected"),
                      "dependencies": dict(case.get("dependencies", {})), "rules_version": case.get("rules_version", "1"),
                      "source_ids": case.get("source_ids", []),
                      "started_at": datetime.now(timezone.utc).isoformat(),
                      "estimated_upper_cost": upper, "currency": config.pricing.currency if config.pricing else None}
            save(receipt_path, record)
            new_calls += 1
            try:
                result = adapter(item["request"], config)
                validate_result(result, item["request"], config)
            except DecisionError as exc:
                safe_cost = exc.billed_cost
                if safe_cost is not None and (isinstance(safe_cost, bool) or not isinstance(safe_cost, (int, float))
                        or not math.isfinite(safe_cost) or safe_cost < 0):
                    safe_cost = None
                record.update(status="pending" if exc.uncertain else "error", error_class=exc.error_class,
                              http_status=exc.status, billed_cost=safe_cost,
                              currency=exc.currency or record["currency"], uncertain=exc.uncertain,
                              billed_cost_provenance=exc.billed_cost_provenance,
                              billing_header_invalid=exc.billing_header_invalid,
                              contract_result=to_record(exc, config, receipt_id=receipt_path.name))
                save(receipt_path, record)
                records.append(record)
                new_records.append(record)
                if exc.uncertain:
                    raise ValueError('uncertain provider outcome; reconcile its pending receipt before continuing') from None
                if safe_cost is not None and record['currency'] != config.pricing.currency:
                    raise ValueError('provider cost currency differs from configured budget currency') from None
                if safe_cost is None:
                    unknown_spend = True
                    record["status"] = "unknown_spend" if not exc.uncertain else "pending"
                    save(receipt_path, record)
                    raise ValueError("provider outcome has unknown spend; further requests stopped") from None
                charged += safe_cost
                continue
            detail = asdict(result) if hasattr(result, "__dataclass_fields__") else result
            if isinstance(detail, dict) and "billed_cost_rub" in detail:
                detail = {**detail, "billed_cost": detail.get("billed_cost_rub"),
                          "estimated_cost": detail.get("estimated_cost_rub"),
                          "provider": config.provider,
                          "returned_model": detail.get("returned_model", config.model),
                          "reused": detail.get("cache_hit", False)}
            if isinstance(detail, dict) and "answer" in detail:
                actual = detail["answer"].get("decision")
                record.update(status="ok", result=detail, actual=actual,
                              match=(actual == case["expected"] if "expected" in case else None),
                              billed_cost=detail.get("billed_cost"), estimated_cost=detail.get("estimated_cost"),
                              reused=bool(detail.get("reused", False)),
                              result_provider=detail.get("provider", config.provider),
                              result_model=detail.get("returned_model", config.model),
                              contract_result=to_record(result, config, receipt_id=receipt_path.name))
            else:
                raise DecisionError("invalid_provider_result")
            save(receipt_path, record)
            records.append(record)
            new_records.append(record)
            if record["billed_cost"] is None:
                unknown_spend = True
                record["status"] = "unknown_spend"
                save(receipt_path, record)
            else:
                charged += record["billed_cost"]
            if unknown_spend and item is not prepared[-1]:
                raise ValueError("result has unknown billed cost; further requests stopped")
        summary = summarize(records)
        new_known = sum(x.get("billed_cost", 0.0) or 0.0 for x in new_records if not x.get("reused", False))
        new_unknown = sum(1 for x in new_records if x.get("billed_cost") is None and not x.get("reused", False))
        summary.update(status="complete", new_requests_this_run=new_calls,
                       reused_receipts=len(records) - new_calls,
                       new_billed_cost_known=new_known,
                       new_unknown_billed_cost_requests=new_unknown,
                       currency=config.pricing.currency,
                       runner_seconds=time.perf_counter() - started)
        save(output / "summary.json", summary)
        return summary
    finally:
        lock.unlink(missing_ok=True)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    cohorts: dict[str, dict[str, int]] = {}
    costs = []
    for item in records:
        bucket = cohorts.setdefault(item.get("cohort", "unspecified"),
                                    {"questions": 0, "matched": 0, "wrong": 0, "insufficient": 0,
                                     "errors": 0, "unscored": 0})
        bucket["questions"] += 1
        if item.get("status") != "ok":
            bucket["errors"] += 1
        else:
            if item.get('actual') == 'insufficient':
                bucket['insufficient'] += 1
            if item.get('match') is None:
                bucket['unscored'] += 1
            elif item['match']:
                bucket['matched'] += 1
            elif item.get('actual') != 'insufficient':
                bucket['wrong'] += 1
        if item.get("billed_cost") is not None:
            costs.append(item["billed_cost"])
    return {"cohorts": cohorts, "recorded_requests": len(records),
            "billed_cost_known": sum(costs), "unknown_billed_cost_requests": sum(
                1 for x in records if x.get("status") in {"pending", "unknown_spend"} or
                (x.get("status") in {"ok", "error"} and x.get("billed_cost") is None))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-requests", type=int, default=20)
    parser.add_argument("--max-cost", type=float, default=1.0)
    args = parser.parse_args(argv)
    try:
        mapping = read(args.config)
        config = config_from_mapping(mapping)
        registry = ProviderRegistry()
        if config.provider == "plusvibe":
            registry.register("plusvibe", PlusVibeAdapter(
                endpoint=config.provider_settings.get("endpoint"),
                timeout=config.provider_settings.get("timeout")))
        result = run(read(args.cases), args.output, config=config, registry=registry,
                     execute_calls=args.execute, max_requests=args.max_requests, max_cost=args.max_cost)
    except (OSError, ValueError, KeyError, TypeError, DecisionError):
        parser.exit(2, "decision-kit stopped; inspect local config, cases, and receipts. Provider details are withheld.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
