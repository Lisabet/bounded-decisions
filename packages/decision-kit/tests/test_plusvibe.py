import json

from decision_kit import (DecisionError, DecisionRequest, ModelConfig, PricingInfo,
                          ProviderRegistry, PlusVibeAdapter, execute)


def request():
    return DecisionRequest.from_mapping("plain factual state", {
        "q": {"type": "choice", "instructions": "Choose one.",
              "criteria": {"yes": "supported", "no": "unsupported"}}
    })


class Transport:
    def __init__(self, body=None, status=200, headers=None, error=None):
        self.body = body or json.dumps({"model": "test/model", "answers": {
            "q": {"type": "choice", "choice": "yes"}},
            "usage": {"input_tokens": 10, "output_tokens": 4}}).encode()
        self.status, self.headers, self.error, self.calls = status, headers or {"x-pv-cost-rub": "0.01"}, error, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, dict(headers), body))
        if self.error:
            raise self.error
        return self.status, self.headers, self.body


def test_plusvibe_actual_adapter_has_optional_probabilities_and_separate_costs():
    transport = Transport()
    endpoint = "https://example.invalid/v1/decisions"
    cfg = ModelConfig("plusvibe", "test/model", pricing=PricingInfo("RUB", 5, 7, "fixture tariff"),
                      provider_settings={"endpoint": endpoint})
    registry = ProviderRegistry()
    registry.register("plusvibe", PlusVibeAdapter(api_key="dummy-secret", transport=transport))
    result = execute(request(), cfg, registry)
    assert transport.calls[0][0] == endpoint
    assert result.answer == {"q": "yes"}
    assert "probabilities" not in result.answers["q"]
    assert result.billed_cost == 0.01 and result.estimated_cost == (10 * 5 + 4 * 7) / 1_000_000
    assert result.billed_cost_provenance == "PlusVibe x-pv-cost-rub response header"
    assert "dummy-secret" not in json.dumps(result.__dict__)


def test_bad_choice_model_schema_and_http_error_are_safe():
    cfg = ModelConfig("plusvibe", "test/model")
    for transport in (
        Transport(body=json.dumps({"model": "test/model", "answers": {"q": {"choice": "other"}},
                                   "usage": {"input_tokens": 1, "output_tokens": 1}}).encode()),
        Transport(body=b"private malformed response"),
        Transport(status=503, headers={}, body=b"private server message"),
    ):
        registry = ProviderRegistry()
        registry.register("plusvibe", PlusVibeAdapter(api_key="dummy-secret", endpoint="https://example.invalid", transport=transport))
        try:
            execute(request(), cfg, registry)
        except DecisionError as exc:
            assert "private" not in str(exc) and "dummy-secret" not in str(exc)
        else:
            raise AssertionError("invalid response accepted")


def test_provider_rejects_cross_currency_price():
    cfg = ModelConfig("plusvibe", "test/model", pricing=PricingInfo("USD", 1, 1, "fixture"))
    registry = ProviderRegistry()
    registry.register("plusvibe", PlusVibeAdapter(api_key="x", transport=Transport()))
    try:
        execute(request(), cfg, registry)
    except DecisionError as exc:
        assert exc.error_class == "pricing_currency_mismatch"
    else:
        raise AssertionError("cross-currency pricing accepted")


def test_unpriced_direct_result_keeps_estimate_unknown():
    cfg = ModelConfig("plusvibe", "test/model")
    registry = ProviderRegistry()
    registry.register("plusvibe", PlusVibeAdapter(api_key="x", endpoint="https://example.invalid", transport=Transport()))
    result = execute(request(), cfg, registry)
    assert result.estimated_cost is None and result.estimated_currency is None


def test_stdlib_read_failure_retains_response_billing(monkeypatch):
    from decision_kit.legacy import client
    class Response:
        status=200
        headers={"x-pv-cost-rub":"0.012"}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): raise TimeoutError("private read failure")
    class Opener:
        def open(self,*args,**kwargs): return Response()
    monkeypatch.setattr(client.urllib.request,'build_opener',lambda *args:Opener())
    registry=ProviderRegistry();registry.register('plusvibe',PlusVibeAdapter(api_key='dummy-secret',endpoint='https://example.invalid'))
    try: execute(request(),ModelConfig('plusvibe','test/model'),registry)
    except DecisionError as error:
        assert error.uncertain and error.billed_cost==0.012 and error.status==200
        assert error.currency=='RUB' and error.billed_cost_provenance=='PlusVibe x-pv-cost-rub response header'
        assert 'private' not in str(error) and 'dummy-secret' not in str(error)
    else: raise AssertionError('read failure accepted')


def test_jev_113_compat_tariff_has_free_output_and_preserves_billed_header(tmp_path):
    from decision_kit import compat
    from decision_kit.cli import encoded
    cases = [{"case_id": "tariff", "state": "sample", "question": {
        "type": "choice", "instructions": "Choose.",
        "criteria": {"yes": "supported", "insufficient": "missing facts"}}}]
    prepared = compat.prepare(cases)
    payload = {"provider": "plusvibe", "model": "typesafe/jev-1.13",
               **prepared[0]["payload"], "dependencies": {}, "rules_version": "1"}
    assert prepared[0]["estimated_upper_cost_rub"] == len(encoded(payload)) * 7.4 / 1_000_000
    compat.run(cases, tmp_path)
    plan = compat.read(tmp_path / "plan.json")
    assert "2026-11-07" in plan["pricing_provenance"]
    assert plan["estimated_upper_cost"] == prepared[0]["estimated_upper_cost_rub"]
    cfg = ModelConfig("plusvibe", "test/model", pricing=PricingInfo("RUB", 7.4, 0, "Jev 1.13 tariff fixture"))
    registry = ProviderRegistry()
    registry.register("plusvibe", PlusVibeAdapter(api_key="dummy", transport=Transport()))
    result = execute(request(), cfg, registry)
    assert result.estimated_cost == 10 * 7.4 / 1_000_000
    assert result.billed_cost == 0.01
