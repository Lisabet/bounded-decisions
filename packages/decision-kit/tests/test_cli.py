import json
from pathlib import Path
import copy

import pytest

from decision_kit import DecisionError, DecisionResult, ModelConfig, PricingInfo, ProviderRegistry
from decision_kit.cli import run, save, read


def test_uncertain_outcome_with_known_charge_holds_next_request(tmp_path):
    two = cases() + cases()
    two[1]['case_id'] = 'two'
    fake = FakeProvider(error=DecisionError('timeout', billed_cost=0.001, currency='USD', uncertain=True))
    with pytest.raises(ValueError, match='uncertain'):
        run(two, tmp_path, config=config(), registry=registry(fake), execute_calls=True)
    assert fake.calls == 1
    assert read(next((tmp_path / 'receipts').glob('*.json')))['status'] == 'pending'


def test_insufficient_operational_answer_is_counted():
    from decision_kit.cli import summarize
    summary = summarize([{'status': 'ok', 'actual': 'insufficient', 'match': None, 'billed_cost': 0.001}])
    assert summary['cohorts']['unspecified']['insufficient'] == 1


def cases():
    return [{"case_id": "one", "state": {"label": "sample A"},
        "question": {"type": "choice", "instructions": "Choose supported category.",
                     "criteria": {"a": "A", "b": "B", "insufficient": "Evidence is insufficient."}},
        "expected": "a", "dependencies": {"input": "v1", "rules": "r1"}, "rules_version": "r1"}]


def config():
    return ModelConfig("test", "model-v1", pricing=PricingInfo("USD", 10, 10, "offline fixture"))


class FakeProvider:
    def __init__(self, *, billed=0.001, error=None):
        self.billed, self.error, self.calls = billed, error, 0

    def decide(self, request, model_config):
        self.calls += 1
        if self.error:
            raise self.error
        return DecisionResult.create(answer={"decision": "a"}, answers={"decision": {
            "choice": "a", "probabilities": {"a": 1, "b": 0, "insufficient": 0}}},
            config=model_config, returned_model=model_config.model,
            usage={"input": 5, "output": 2}, billed_cost=self.billed,
            billed_currency="USD" if self.billed is not None else None,
            billed_cost_provenance="fixture meter" if self.billed is not None else None,
            estimated_cost=0.001, estimated_currency="USD", estimated_cost_provenance="fixture")


def registry(provider):
    r = ProviderRegistry(); r.register("test", provider); return r


def test_default_plan_writes_plan_without_provider_call(tmp_path):
    fake = FakeProvider()
    result = run(cases(), tmp_path, config=config(), registry=registry(fake))
    assert result["status"] == "planned" and fake.calls == 0
    assert (tmp_path / "plan.json").exists() and not (tmp_path / "receipts").exists()


def test_execute_resumes_receipt_without_call_and_invalidates_provider_model_dependency(tmp_path):
    fake = FakeProvider()
    first = run(cases(), tmp_path, config=config(), registry=registry(fake), execute_calls=True)
    second = run(cases(), tmp_path, config=config(), registry=registry(fake), execute_calls=True)
    assert fake.calls == 1 and first["new_requests_this_run"] == 1
    assert second["new_requests_this_run"] == 0 and second["reused_receipts"] == 1
    assert first["new_billed_cost_known"] == 0.001
    assert second["new_billed_cost_known"] == 0.0
    for changed_config, changed_cases in (
        (ModelConfig("other", "model-v1", pricing=config().pricing), cases()),
        (ModelConfig("test", "model-v2", pricing=config().pricing), cases()),
    ):
        with pytest.raises(ValueError, match="changed inputs"):
            run(changed_cases, tmp_path, config=changed_config, registry=registry(fake), execute_calls=True)
    changed = cases(); changed[0]["dependencies"]["rules"] = "r2"
    with pytest.raises(ValueError, match="changed inputs"):
        run(changed, tmp_path, config=config(), registry=registry(fake), execute_calls=True)
    changed_config = ModelConfig("test", "model-v1", pricing=config().pricing,
                                 provider_settings={"endpoint": "https://other.invalid"})
    with pytest.raises(ValueError, match="changed inputs"):
        run(cases(), tmp_path, config=changed_config, registry=registry(fake), execute_calls=True)
    changed = cases(); changed[0]["cache_context"] = {"schema": "s2"}
    with pytest.raises(ValueError, match="changed inputs"):
        run(changed, tmp_path, config=config(), registry=registry(fake), execute_calls=True)


def test_unknown_cost_stops_next_call_and_is_retained(tmp_path):
    two = cases() + [copy.deepcopy(cases()[0])]
    two[1]["case_id"] = "two"
    fake = FakeProvider(billed=None)
    with pytest.raises(ValueError, match="unknown billed cost"):
        run(two, tmp_path, config=config(), registry=registry(fake), execute_calls=True)
    assert fake.calls == 1
    records = list((tmp_path / "receipts").glob("*.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text())["status"] == "unknown_spend"


def test_timeout_pending_stops_without_retry_and_caps_validate_before_call(tmp_path):
    two = cases() + [copy.deepcopy(cases()[0])]; two[1]["case_id"] = "two"
    fake = FakeProvider(error=DecisionError("timeout", uncertain=True))
    with pytest.raises(ValueError, match="uncertain"):
        run(two, tmp_path, config=config(), registry=registry(fake), execute_calls=True)
    assert fake.calls == 1
    assert json.loads(next((tmp_path / "receipts").glob("*.json")).read_text())["status"] == "pending"
    clean = tmp_path / "caps"
    with pytest.raises(ValueError, match="request limit"):
        run(two, clean, config=config(), registry=registry(FakeProvider()), execute_calls=True, max_requests=1)
    assert not list(clean.glob("receipts/*.json"))


def test_lock_is_not_replaced_and_invalid_schema_stops_preflight(tmp_path):
    (tmp_path / "execution.lock").write_text("owner")
    with pytest.raises(ValueError, match="already owned"):
        run(cases(), tmp_path, config=config(), execute_calls=True)
    assert (tmp_path / "execution.lock").read_text() == "owner"
    invalid = cases(); invalid[0]["question"]["type"] = "text"
    with pytest.raises(ValueError, match="choice schema"):
        run(invalid, tmp_path / "invalid", config=config(), execute_calls=True)


def test_refusal_is_distinct_and_known_charge_is_retained(tmp_path):
    two = cases() + [copy.deepcopy(cases()[0])]; two[1]["case_id"] = "two"
    fake = FakeProvider(error=DecisionError("model_refusal", billed_cost=0.0003, currency="USD"))
    result = run(two, tmp_path, config=config(), registry=registry(fake), execute_calls=True)
    assert fake.calls == 2
    assert result["billed_cost_known"] == 0.0006
    rows = [json.loads(p.read_text()) for p in (tmp_path / "receipts").glob("*.json")]
    assert all(row["status"] == "error" and row["error_class"] == "model_refusal" for row in rows)


def test_prior_costs_are_preloaded_before_next_budget_check(tmp_path):
    two = cases() + [copy.deepcopy(cases()[0])]; two[1]["case_id"] = "two"
    fake = FakeProvider(billed=0.4)
    first_dir = tmp_path / "old"
    run(two, first_dir, config=config(), registry=registry(fake), execute_calls=True, max_cost=1.0)
    target = tmp_path / "partial"
    target.mkdir()
    source_receipts = list((first_dir / "receipts").glob("*.json"))
    target.mkdir(exist_ok=True)
    (target / "receipts").mkdir()
    first_receipt = json.loads(source_receipts[0].read_text())
    save(target / "receipts" / source_receipts[0].name, first_receipt)
    fresh = FakeProvider(billed=0.01)
    with pytest.raises(ValueError, match="remaining cost budget"):
        run(two, target, config=config(), registry=registry(fresh), execute_calls=True, max_cost=0.1)
    assert fresh.calls == 0


@pytest.mark.parametrize('kind,billed,uncertain', [('http_error',0.003,False),('malformed_json',0,False),('timeout',0.004,True),('http_error',None,False)])
def test_charged_error_contract_persists_and_resume_never_resubmits(tmp_path,kind,billed,uncertain):
    fake=FakeProvider(error=DecisionError(kind,billed_cost=billed,currency='USD' if billed is not None else None,
        billed_cost_provenance='fixture meter' if billed is not None else None,uncertain=uncertain))
    if uncertain or billed is None:
        with pytest.raises(ValueError): run(cases(),tmp_path,config=config(),registry=registry(fake),execute_calls=True)
    else:
        run(cases(),tmp_path,config=config(),registry=registry(fake),execute_calls=True)
    row=read(next((tmp_path/'receipts').glob('*.json')))
    contract=row['contract_result']
    assert contract['receipt']['id'] and contract['uncertain']==uncertain
    if billed is None: assert contract['billing'] is None and contract['billing_state']=='unknown'
    else: assert contract['billing']=={'amount':billed,'currency':'USD','source':'fixture meter'}
    if uncertain:
        with pytest.raises(ValueError,match='pending'): run(cases(),tmp_path,config=config(),registry=registry(fake),execute_calls=True)
    else:
        repeat=run(cases(),tmp_path,config=config(),registry=registry(fake),execute_calls=True)
        assert repeat['new_requests_this_run']==0 and repeat['new_billed_cost_known']==0
    assert fake.calls==1
