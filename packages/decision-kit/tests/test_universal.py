import copy
import json
from pathlib import Path
import pytest
from importlib.resources import files

from decision_kit import ModelConfig, ProviderRegistry, PlusVibeAdapter
from decision_kit.universal import evaluate_record, execute_task, make_jev_adapter, validate_task


TASK = {"task_version": "bounded-task/1", "task_id": "t1", "rules_version": "r1", "state": {"x": 1},
        "questions": {"q": {"type": "choice", "instructions": "choose", "criteria": {"a": "A", "b": "B"}, "abstain_choice": "b"}}}
SELECT = {"provider": "fixture", "model": "m1"}


def record(**changes):
    value = {"contract_version": "bounded-decisions/1", "provider": "fixture", "requested_model": "m1",
             "returned_model": "m1", "status": "ok", "answers": {"q": {"type": "choice", "choice": "a", "confidence": .8}},
             "usage": {"input_tokens": 1, "output_tokens": 2}, "billing": {"amount": 0, "currency": "USD", "source": "fixture"},
             "billing_state": "observed", "estimate": None, "receipt": {"id": "rcpt", "reused": False},
             "uncertain": False, "error": None}
    value.update(changes)
    return value


class Adapter:
    def __init__(self, output): self.output, self.calls = output, 0
    def decide(self, task, selection, context): self.calls += 1; return copy.deepcopy(self.output)


def test_task_validation_and_preflight_zero_calls():
    adapter = Adapter(record())
    assert validate_task(TASK)["task_id"] == "t1"
    bad = copy.deepcopy(TASK); bad["questions"]["q"]["abstain_choice"] = "missing"
    with pytest.raises(ValueError): execute_task(bad, SELECT, {"fixture": adapter})
    with pytest.raises(ValueError): execute_task(TASK, SELECT, {"fixture": adapter}, {"expected_choices": {"q": "missing"}})
    with pytest.raises(ValueError): execute_task(TASK, SELECT, {"fixture": adapter}, context={"reused": True})
    assert adapter.calls == 0


def test_arbitrary_adapter_and_policy_quality():
    adapter = Adapter(record())
    out = execute_task(TASK, SELECT, {"fixture": adapter}, {"expected_choices": {"q": "a"}, "minimum_confidence": .7})
    assert adapter.calls == 1
    assert out["evaluation"] == {"status": "accepted", "issues": [], "quality": {"matched": True, "questions": {"q": True}}}


def test_review_issue_order_and_abstention():
    r = record(answers={"q": {"type": "choice", "choice": "b"}}, billing_state="unknown", billing=None, usage=None)
    out = evaluate_record(TASK, SELECT, r, {"require_confidence": True, "require_probabilities": True, "require_usage": True})
    assert out["evaluation"]["status"] == "review"
    assert out["evaluation"]["issues"] == ["billing_unknown", "confidence_required:q", "probabilities_required:q", "abstained:q", "usage_required"]


def test_error_and_pending_retain_valid_billing_and_receipt():
    for status, uncertain, code, expect in [("error", False, "http", "rejected"), ("pending", True, "timeout", "review")]:
        r = record(returned_model=None, status=status, answers={}, usage=None, uncertain=uncertain,
                   error={"code": code, "http_status": 503})
        out = evaluate_record(TASK, SELECT, r)
        assert out["record"]["billing"]["amount"] == 0
        assert out["evaluation"]["status"] == expect
    r = record(returned_model=None, status="pending", answers={}, usage=None, uncertain=True,
               error={"code": "timeout", "http_status": None}, receipt={"id": "old", "reused": True})
    assert evaluate_record(TASK, SELECT, r)["record"]["receipt"] == {"id": "old", "reused": True}


def test_invalid_adapter_record_is_sanitized_preserving_valid_charge():
    r = record(requested_model="wrong", billing={"amount": 2, "currency": "USD", "source": "meter"})
    out = execute_task(TASK, SELECT, {"fixture": Adapter(r)})
    assert out["record"]["error"] == {"code": "invalid_response", "http_status": None}
    assert out["record"]["billing"]["amount"] == 2
    assert out["evaluation"]["status"] == "rejected"


def test_invalid_billing_becomes_invalid_state_and_review_issue():
    r = record(billing={"amount": float("nan"), "currency": "USD", "source": "meter"})
    out = execute_task(TASK, SELECT, {"fixture": Adapter(r)})
    assert out["record"]["billing"] is None and out["record"]["billing_state"] == "invalid"
    assert "billing_invalid" in out["evaluation"]["issues"]


def test_minimum_confidence_missing_emits_required_issue():
    r = record(answers={"q": {"type": "choice", "choice": "a"}})
    out = evaluate_record(TASK, SELECT, r, {"minimum_confidence": .5})
    assert out["evaluation"]["issues"] == ["confidence_required:q"]


def test_registry_shape_and_receipt_identity_are_preflighted_or_sanitized():
    with pytest.raises(ValueError): execute_task(TASK, SELECT, {"fixture": object()})
    adapter = Adapter(record(receipt={"id": "other", "reused": False}))
    out = execute_task(TASK, SELECT, {"fixture": adapter}, context={"receiptId": "expected"})
    assert adapter.calls == 1
    assert out["record"]["error"]["code"] == "invalid_response"
    assert out["record"]["receipt"]["id"] == "expected"


def test_json_safe_task_rejects_cycles_and_unsafe_numbers():
    bad = copy.deepcopy(TASK)
    bad["state"] = {"n": float("nan")}
    with pytest.raises(ValueError): validate_task(bad)
    cycle = []; cycle.append(cycle)
    bad["state"] = {"cycle": cycle}
    with pytest.raises(ValueError): validate_task(bad)


def test_explicit_returned_model_alias_and_adapter_input_isolation():
    class MutatingAdapter(Adapter):
        def decide(self, task, selection, context):
            self.calls += 1
            task["questions"].clear()
            return copy.deepcopy(self.output)
    r = record(returned_model="alias")
    adapter = MutatingAdapter(r)
    out = execute_task(TASK, {**SELECT, "returned_model_policy": "any_nonempty"}, {"fixture": adapter})
    assert out["evaluation"]["status"] == "accepted"
    assert out["task_id"] == TASK["task_id"]


def test_malformed_record_is_sanitized_without_losing_charge_or_uncertainty():
    r = record(status=[], billing={"amount": .2, "currency": "USD", "source": "meter"}, uncertain=True)
    out = execute_task(TASK, SELECT, {"fixture": Adapter(r)})
    assert out["record"]["status"] == "pending"
    assert out["record"]["billing"]["amount"] == .2
    assert out["evaluation"]["issues"] == ["operation_pending"]


def test_usage_requirement_does_not_mask_operation_failure():
    r = record(returned_model=None, status="error", answers={}, usage=None, uncertain=False,
               error={"code": "http", "http_status": 503})
    out = evaluate_record(TASK, SELECT, r, {"require_usage": True})
    assert out["evaluation"]["issues"] == ["operation_error"]


def test_canonical_shared_fixtures():
    fixtures_path = files("decision_kit.contract_data").joinpath("universal-fixtures.json")
    data = json.loads(fixtures_path.read_text(encoding="utf-8"))
    for item in data["cases"]:
        actual = evaluate_record(item["task"], item["selection"], item["record"], item.get("policy", {}))
        assert actual["evaluation"] == item["expected_evaluation"], item["id"]


@pytest.mark.parametrize("case_id", ["ok", "http-charged", "timeout"])
def test_jev_adapter_reuses_legacy_wire_fixtures(case_id):
    fixtures = json.loads(files("decision_kit.contract_data").joinpath("fixtures.json").read_text(encoding="utf-8"))
    item = next(case for case in fixtures["cases"] if case["id"] == case_id)
    request = item["request"]
    def transport(*args):
        if item["transport_error"] == "timeout": raise TimeoutError()
        if item["transport_error"]: raise OSError("synthetic")
        response = item["response"]
        body = response["body"]
        return response["status"], response["headers"], (body if isinstance(body, str) else json.dumps(body)).encode()
    config = ModelConfig("plusvibe", request["model"])
    registry = ProviderRegistry()
    registry.register("plusvibe", PlusVibeAdapter(api_key="synthetic", endpoint="https://example.invalid/v1/decisions", transport=transport))
    task = {"task_version": "bounded-task/1", "task_id": case_id, "rules_version": "fixture/1",
            "state": request["state"], "questions": request["questions"]}
    output = execute_task(task, {"provider": "plusvibe", "model": request["model"]},
                          {"plusvibe": make_jev_adapter(config, registry)}, context={"receiptId": "attempt-fixture"})
    expected = copy.deepcopy(item["expected"])
    expected["receipt"] = {"id": "attempt-fixture", "reused": False}
    assert output["record"] == expected



def test_adapter_cannot_mark_new_operation_as_reused_without_caller_context():
    import json
    from pathlib import Path
    item = json.loads(files("decision_kit.contract_data").joinpath("universal-fixtures.json").read_text(encoding="utf-8"))["cases"][0]
    record = item["record"]
    record["receipt"]["reused"] = True
    class Adapter:
        def decide(self, task, selection, context): return record
    outcome = execute_task(item["task"], item["selection"], {item["selection"]["provider"]: Adapter()})
    assert outcome["record"]["status"] == "error"
    assert outcome["record"]["receipt"]["reused"] is False
    assert outcome["record"]["billing"]["amount"] == 0


@pytest.mark.parametrize("selected", [{"provider": "plusvibe", "model": "other"}, {"provider": "other", "model": "configured"}])
def test_jev_selection_mismatch_is_local_preflight_with_zero_operations(selected):
    class NeverProvider:
        calls = 0
        def decide(self, *args):
            self.calls += 1
            raise AssertionError("provider reached")
    provider = NeverProvider()
    registry = ProviderRegistry(); registry.register("plusvibe", provider)
    adapter = make_jev_adapter(ModelConfig("plusvibe", "configured"), registry)
    with pytest.raises(ValueError, match="configuration does not match selection"):
        execute_task(TASK, selected, {selected["provider"]: adapter}, context={"receiptId": "attempt-1"})
    assert provider.calls == 0


def test_adapter_preflight_rejection_and_unexpected_dispatch_failure_have_distinct_outcomes():
    class Checked:
        calls = 0
        def validate_selection(self, selection):
            raise ValueError("local configuration")
        def decide(self, *args): self.calls += 1
    adapter = Checked()
    with pytest.raises(ValueError, match="local configuration"):
        execute_task(TASK, SELECT, {"fixture": adapter})
    assert adapter.calls == 0
    class Dispatched:
        def decide(self, *args): raise RuntimeError("unknown dispatch state")
    result = execute_task(TASK, SELECT, {"fixture": Dispatched()})
    assert result["record"]["status"] == "pending"
    assert result["record"]["uncertain"] is True


def test_adapter_preflight_receives_an_isolated_selection():
    class Checked(Adapter):
        def validate_selection(self, selection): selection["model"] = "mutated"
        def decide(self, task, selection, context):
            assert selection["model"] == "m1"
            return super().decide(task, selection, context)
    assert execute_task(TASK, SELECT, {"fixture": Checked(record())})["evaluation"]["status"] == "accepted"
