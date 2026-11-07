"""Provider-neutral validation and execution for bounded choice tasks."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

TASK_VERSION = "bounded-task/1"
RECORD_VERSION = "bounded-decisions/1"
_RECORD_KEYS = {"contract_version", "provider", "requested_model", "returned_model", "status", "answers", "usage", "billing", "billing_state", "estimate", "receipt", "uncertain", "error"}
_ERROR_CODES = {"route", "input_limit", "body_limit", "http", "invalid_response", "timeout", "transport"}
_POLICY_KEYS = {"require_confidence", "require_probabilities", "require_usage", "minimum_confidence", "bypass_confidence_choices", "expected_choices"}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _json_safe(value: Any, active: set[int] | None = None) -> bool:
    active = set() if active is None else active
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, int):
        return abs(value) <= 9007199254740991
    if isinstance(value, float):
        return math.isfinite(value) and (not value.is_integer() or abs(value) <= 9007199254740991)
    if isinstance(value, list):
        if id(value) in active: return False
        active.add(id(value))
        ok = all(_json_safe(item, active) for item in value)
        active.remove(id(value))
        return ok
    if isinstance(value, Mapping):
        if id(value) in active: return False
        active.add(id(value))
        ok = all(isinstance(key, str) and _json_safe(item, active) for key, item in value.items())
        active.remove(id(value))
        return ok
    return False


def validate_task(task: Any) -> dict[str, Any]:
    """Validate and return a detached JSON-safe bounded-task/1 object."""
    if not isinstance(task, Mapping) or set(task) != {"task_version", "task_id", "rules_version", "state", "questions"}:
        raise ValueError("invalid task shape")
    if task.get("task_version") != TASK_VERSION or not _nonempty(task.get("task_id")) or not _nonempty(task.get("rules_version")):
        raise ValueError("invalid task identity")
    state = task.get("state")
    if not _json_safe(state) or not ((isinstance(state, str) and state.strip()) or (isinstance(state, Mapping) and len(state)) or (isinstance(state, list) and len(state))):
        raise ValueError("invalid task state")
    questions = task.get("questions")
    if not isinstance(questions, Mapping) or not 1 <= len(questions) <= 20:
        raise ValueError("task requires 1 to 20 questions")
    for qid, q in questions.items():
        if not _nonempty(qid) or not isinstance(q, Mapping) or set(q) - {"type", "instructions", "criteria", "abstain_choice"}:
            raise ValueError("invalid question")
        if q.get("type") != "choice" or not _nonempty(q.get("instructions")):
            raise ValueError("invalid choice question")
        criteria = q.get("criteria")
        if not isinstance(criteria, Mapping) or len(criteria) < 2 or any(not _nonempty(k) or not _nonempty(v) for k, v in criteria.items()):
            raise ValueError("invalid choice criteria")
        abstain = q.get("abstain_choice")
        if "abstain_choice" in q and (not _nonempty(abstain) or abstain not in criteria):
            raise ValueError("invalid abstention choice")
    if not _json_safe(task):
        raise ValueError("task must contain JSON-safe values")
    return json.loads(json.dumps(task, ensure_ascii=False, allow_nan=False))


def _validate_selection(selection: Any) -> tuple[str, str]:
    if not isinstance(selection, Mapping) or set(selection) - {"provider", "model", "returned_model_policy"} or not {"provider", "model"} <= set(selection):
        raise ValueError("invalid selection")
    provider, model = selection.get("provider"), selection.get("model")
    if not _nonempty(provider) or not _nonempty(model):
        raise ValueError("provider and model are required")
    if selection.get("returned_model_policy", "exact") not in {"exact", "any_nonempty"}:
        raise ValueError("invalid returned_model_policy")
    return provider, model


def _validate_context(context: Any) -> dict[str, Any]:
    if not isinstance(context, Mapping) or set(context) - {"receiptId", "reused"}:
        raise ValueError("invalid context")
    if "receiptId" in context and not _nonempty(context["receiptId"]):
        raise ValueError("invalid receiptId")
    if "reused" in context and not isinstance(context["reused"], bool):
        raise ValueError("invalid reused flag")
    if context.get("reused", False) and not _nonempty(context.get("receiptId")):
        raise ValueError("reused records require receiptId")
    return dict(context)


def _policy(task: Mapping[str, Any], policy: Any) -> dict[str, Any]:
    if not isinstance(policy, Mapping) or set(policy) - _POLICY_KEYS:
        raise ValueError("invalid policy")
    p = dict(policy)
    for key in ("require_confidence", "require_probabilities", "require_usage"):
        if key in p and not isinstance(p[key], bool):
            raise ValueError("invalid policy flag")
    if p.get("returned_model_policy", "exact") not in {"exact", "any_nonempty"}:
        raise ValueError("invalid returned_model_policy")
    if "minimum_confidence" in p and (not _finite_number(p["minimum_confidence"]) or not 0 <= p["minimum_confidence"] <= 1):
        raise ValueError("invalid minimum_confidence")
    qmap = task["questions"]
    for key in ("bypass_confidence_choices", "expected_choices"):
        value = p.get(key, {})
        if not isinstance(value, Mapping):
            raise ValueError("invalid policy choices")
        for qid, choices in value.items():
            if qid not in qmap:
                raise ValueError("unknown policy question")
            if key == "expected_choices":
                if not _nonempty(choices) or choices not in qmap[qid]["criteria"]:
                    raise ValueError("invalid expected choice")
            elif not isinstance(choices, list) or len(set(choices)) != len(choices) or any(not _nonempty(c) or c not in qmap[qid]["criteria"] for c in choices):
                raise ValueError("invalid confidence bypass choices")
    return p


def _validate_money(value: Any) -> bool:
    return (isinstance(value, Mapping) and set(value) == {"amount", "currency", "source"}
            and _finite_number(value.get("amount")) and value["amount"] >= 0
            and _nonempty(value.get("currency"))
            and (value.get("source") is None or _nonempty(value.get("source"))))


def _valid_record(record: Any, task: Mapping[str, Any], provider: str, model: str, model_policy: str) -> bool:
    if not isinstance(record, Mapping) or set(record) != _RECORD_KEYS or record.get("contract_version") != RECORD_VERSION:
        return False
    if record.get("provider") != provider or record.get("requested_model") != model:
        return False
    status = record.get("status")
    billing_state = record.get("billing_state")
    if not isinstance(status, str) or status not in {"ok", "error", "pending"} or not isinstance(billing_state, str) or billing_state not in {"observed", "unknown", "invalid"}:
        return False
    answers = record.get("answers")
    if not isinstance(answers, Mapping):
        return False
    if status == "ok":
        if not _nonempty(record.get("returned_model")) or (model_policy == "exact" and record["returned_model"] != model):
            return False
        if record.get("error") is not None or record.get("uncertain") is not False or set(answers) != set(task["questions"]):
            return False
        for qid, answer in answers.items():
            if not isinstance(answer, Mapping) or set(answer) - {"type", "choice", "confidence", "probabilities"} or answer.get("type") != "choice":
                return False
            if not isinstance(answer.get("choice"), str) or answer["choice"] not in task["questions"][qid]["criteria"]:
                return False
            if "confidence" in answer and (not _finite_number(answer["confidence"]) or not 0 <= answer["confidence"] <= 1):
                return False
            if "probabilities" in answer:
                probs = answer["probabilities"]
                if not isinstance(probs, Mapping) or set(probs) != set(task["questions"][qid]["criteria"]):
                    return False
                vals = list(probs.values())
                if any(not _finite_number(x) or not 0 <= x <= 1 for x in vals) or abs(sum(vals) - 1) > .02:
                    return False
    else:
        err = record.get("error")
        if record.get("returned_model") is not None or answers or record.get("usage") is not None or not isinstance(err, Mapping) or set(err) != {"code", "http_status"} or not isinstance(err.get("code"), str) or err["code"] not in _ERROR_CODES:
            return False
        hs = err.get("http_status")
        if hs is not None and (not isinstance(hs, int) or isinstance(hs, bool) or not 100 <= hs <= 599):
            return False
        if record.get("uncertain") is not (status == "pending"):
            return False
    usage = record.get("usage")
    if usage is not None and (not isinstance(usage, Mapping) or set(usage) - {"input_tokens", "output_tokens"} or any(not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9007199254740991 for v in usage.values())):
        return False
    billing = record.get("billing")
    if record["billing_state"] == "observed":
        if not _validate_money(billing): return False
    elif billing is not None:
        return False
    estimate = record.get("estimate")
    if estimate is not None and not _validate_money(estimate): return False
    receipt = record.get("receipt")
    if not isinstance(receipt, Mapping) or set(receipt) != {"id", "reused"} or not isinstance(receipt.get("reused"), bool): return False
    if receipt.get("id") is not None and not _nonempty(receipt["id"]): return False
    if receipt["reused"] and not _nonempty(receipt.get("id")): return False
    return True


def evaluate_record(task: Any, selection: Any, record: Any, policy: Any = None) -> dict[str, Any]:
    task = validate_task(task)
    provider, model = _validate_selection(selection)
    p = _policy(task, {} if policy is None else policy)
    model_policy = selection.get("returned_model_policy", "exact")
    try:
        valid_record = _valid_record(record, task, provider, model, model_policy)
    except (TypeError, ValueError, OverflowError):
        valid_record = False
    if not valid_record:
        raise ValueError("invalid operation record")
    issues: list[str] = []
    quality = None
    if record["status"] == "error":
        issues.append("operation_error")
        status = "rejected"
    elif record["status"] == "pending":
        issues.append("operation_pending")
        status = "review"
    else:
        status = "accepted"
    if record["billing_state"] == "unknown": issues.append("billing_unknown")
    elif record["billing_state"] == "invalid": issues.append("billing_invalid")
    if record["status"] == "ok":
        expected = p.get("expected_choices", {})
        qquality = {qid: record["answers"][qid]["choice"] == choice for qid, choice in expected.items()}
        quality = {"matched": all(qquality.values()), "questions": qquality} if expected else None
        for qid, q in task["questions"].items():
            answer = record["answers"][qid]
            choice = answer["choice"]
            if (p.get("require_confidence") or "minimum_confidence" in p) and "confidence" not in answer: issues.append(f"confidence_required:{qid}")
            if p.get("require_probabilities") and "probabilities" not in answer: issues.append(f"probabilities_required:{qid}")
            if ("minimum_confidence" in p and "confidence" in answer and answer["confidence"] < p["minimum_confidence"]
                    and choice not in p.get("bypass_confidence_choices", {}).get(qid, [])):
                issues.append(f"confidence_below_minimum:{qid}")
            if choice == q.get("abstain_choice"): issues.append(f"abstained:{qid}")
    if record["status"] == "ok" and p.get("require_usage") and (record["usage"] is None or not {"input_tokens", "output_tokens"} <= set(record["usage"])):
        issues.append("usage_required")
    if status != "rejected" and issues: status = "review"
    return {"task_version": task["task_version"], "task_id": task["task_id"], "rules_version": task["rules_version"],
            "record": dict(record), "evaluation": {"status": status, "issues": issues, "quality": quality}}


def _clean_observation(record: Any, provider: str, model: str, context: Mapping[str, Any]) -> dict[str, Any]:
    """Build safe invalid_response record while retaining independently valid billing evidence."""
    r = record if isinstance(record, Mapping) else {}
    billing = r.get("billing")
    billing_valid = _validate_money(billing)
    state = "observed" if billing_valid else ("invalid" if ("billing" in r and billing is not None) or r.get("billing_state") == "invalid" else "unknown")
    estimate = r.get("estimate")
    if not _validate_money(estimate): estimate = None
    receipt_in = r.get("receipt") if isinstance(r.get("receipt"), Mapping) else {}
    rid = context.get("receiptId", receipt_in.get("id"))
    reused = context.get("reused", False) is True
    if not _nonempty(rid): rid = None
    if reused and rid is None: reused = False
    error = r.get("error") if isinstance(r.get("error"), Mapping) else {}
    http = error.get("http_status")
    if not isinstance(http, int) or isinstance(http, bool) or not 100 <= http <= 599: http = None
    uncertain = bool(isinstance(r, Mapping) and (r.get("status") == "pending" or r.get("uncertain") is True))
    return {"contract_version": RECORD_VERSION, "provider": provider, "requested_model": model, "returned_model": None,
            "status": "pending" if uncertain else "error", "answers": {}, "usage": None, "billing": dict(billing) if billing_valid else None,
            "billing_state": state, "estimate": dict(estimate) if estimate else None, "receipt": {"id": rid, "reused": reused},
            "uncertain": uncertain, "error": {"code": "invalid_response", "http_status": http}}


def execute_task(task: Any, selection: Any, registry: Mapping[str, Any], policy: Any = None, context: Any = None) -> dict[str, Any]:
    """Execute once through an explicitly selected adapter; validate before and after invocation."""
    t = validate_task(task)
    provider, model = _validate_selection(selection)
    p = _policy(t, {} if policy is None else policy)
    c = _validate_context({} if context is None else context)
    if not isinstance(registry, Mapping) or provider not in registry:
        raise ValueError("unknown provider")
    adapter = registry[provider]
    if not callable(getattr(adapter, "decide", None)):
        raise ValueError("selected adapter must provide decide")
    model_policy = selection.get("returned_model_policy", "exact")
    adapter_selection = {"provider": provider, "model": model, "returned_model_policy": model_policy}
    # Local selection validation precedes the potentially dispatched operation boundary.
    validator = getattr(adapter, "validate_selection", None)
    if validator is not None:
        if not callable(validator):
            raise ValueError("adapter validate_selection must be callable")
        validator(dict(adapter_selection))
    try:
        record = adapter.decide(json.loads(json.dumps(t, ensure_ascii=False)), adapter_selection, dict(c))
    except Exception:
        record = {"contract_version": RECORD_VERSION, "provider": provider, "requested_model": model,
                  "returned_model": None, "status": "pending", "answers": {}, "usage": None, "billing": None,
                  "billing_state": "unknown", "estimate": None, "receipt": {"id": c.get("receiptId"), "reused": c.get("reused", False)},
                  "uncertain": True, "error": {"code": "transport", "http_status": None}}
    receipt_mismatch = (isinstance(record, Mapping) and isinstance(record.get("receipt"), Mapping)
                        and (("receiptId" in c and record["receipt"].get("id") != c["receiptId"])
                             or record["receipt"].get("reused") != c.get("reused", False)))
    try:
        valid_record = _valid_record(record, t, provider, model, model_policy)
    except (TypeError, ValueError, OverflowError):
        valid_record = False
    if receipt_mismatch or not valid_record:
        record = _clean_observation(record, provider, model, c)
    # The generic operation boundary retains independently observed billable costs on errors.
    if not _valid_record(record, t, provider, model, model_policy):
        raise ValueError("unable to normalize adapter record")
    result = evaluate_record(t, {"provider": provider, "model": model, "returned_model_policy": model_policy}, record, p)
    return result


def make_jev_adapter(config: Any, registry: Any):
    """Bridge the legacy Python provider registry into the neutral adapter protocol."""
    from .core import DecisionError, DecisionRequest, ModelConfig, execute
    from .contract import to_record

    if not isinstance(config, ModelConfig):
        raise TypeError("config must be ModelConfig")

    class JevAdapter:
        def validate_selection(self, selection: Mapping[str, str]) -> None:
            if config.provider != selection["provider"] or config.model != selection["model"]:
                raise ValueError("adapter configuration does not match selection")

        def decide(self, task: Mapping[str, Any], selection: Mapping[str, str], context: Mapping[str, Any]) -> dict[str, Any]:
            self.validate_selection(selection)
            questions = {qid: {"type": "choice", "instructions": q["instructions"], "criteria": dict(q["criteria"])}
                         for qid, q in task["questions"].items()}
            request = DecisionRequest.from_mapping(task["state"], questions, rules_version=task["rules_version"])
            try:
                outcome = execute(request, config, registry)
            except DecisionError as exc:
                outcome = exc
            return to_record(outcome, config, receipt_id=context.get("receiptId"), reused=context.get("reused"))

    return JevAdapter()
