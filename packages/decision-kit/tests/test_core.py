from decision_kit import (ChoiceQuestion, DecisionError, DecisionRequest, DecisionResult,
                          ModelConfig, PricingInfo, ProviderRegistry, execute)


def test_invalid_negative_charge_is_not_trusted_as_billing_evidence():
    from dataclasses import replace
    req, cfg = setup_request_config()
    class InvalidCharge(AlternateProtocolAdapter):
        def decide(self, request, config):
            return replace(super().decide(request, config), billed_cost=-1)
    registry = ProviderRegistry()
    registry.register('alternate', InvalidCharge())
    try:
        execute(req, cfg, registry)
    except DecisionError as exc:
        assert exc.billed_cost is None
    else:
        raise AssertionError('negative provider cost accepted')


def setup_request_config():
    req = DecisionRequest("record", {"q": ChoiceQuestion("Choose", {"a": "A", "b": "B"})})
    cfg = ModelConfig("alternate", "model-x", pricing=PricingInfo("USD", 1, 2, "test fixture"))
    return req, cfg


class AlternateProtocolAdapter:
    """Test adapter uses a different response protocol and normalizes locally."""
    def __init__(self, *, choice="a", returned_model="model-x", usage=None, probabilities=None):
        self.choice, self.returned_model = choice, returned_model
        self.usage = usage or {"input_units": 4, "output_units": 1}
        self.probabilities = probabilities

    def decide(self, request, config):
        # This fixture models a provider returning {selected, model_name, meter}.
        wire = {"selected": self.choice, "model_name": self.returned_model, "meter": self.usage}
        answer = {"q": wire["selected"]}
        detail = {"choice": wire["selected"]}
        if self.probabilities is not None:
            detail["probabilities"] = self.probabilities
        return DecisionResult.create(answer=answer, answers={"q": detail}, config=config,
            returned_model=wire["model_name"], usage=wire["meter"], billed_cost=0.002,
            billed_currency="USD", billed_cost_provenance="alternate meter", estimated_cost=0.003,
            estimated_currency="USD", estimated_cost_provenance="test tariff")


def test_different_adapter_protocol_normalizes_to_common_result():
    req, cfg = setup_request_config()
    registry = ProviderRegistry()
    registry.register("alternate", AlternateProtocolAdapter())
    result = execute(req, cfg, registry)
    assert result.provider == "alternate"
    assert result.requested_model == result.returned_model == "model-x"
    assert result.answer == {"q": "a"}
    assert result.usage == {"input_units": 4, "output_units": 1}
    assert result.billed_currency == "USD" and result.estimated_cost == 0.003
    assert result.answers["q"].get("probabilities") is None


def test_core_rejects_adapter_answer_model_and_usage_defects():
    req, cfg = setup_request_config()
    for adapter in (AlternateProtocolAdapter(choice="unknown"),
                    AlternateProtocolAdapter(returned_model="other"),
                    AlternateProtocolAdapter(usage={"input_units": -1}),
                    AlternateProtocolAdapter(probabilities={"a": 0.4, "b": 0.4})):
        registry = ProviderRegistry()
        registry.register("alternate", adapter)
        try:
            execute(req, cfg, registry)
        except DecisionError:
            pass
        else:
            raise AssertionError("invalid provider output accepted")


def test_invalid_config_values_are_rejected():
    for provider, model in (("", "m"), ("p", "  ")):
        try:
            ModelConfig(provider, model)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid provider/model accepted")
    for values in ({"bad": float("nan")}, {"bad": float("inf")}):
        try:
            ModelConfig("p", "m", limits=values)
        except ValueError:
            pass
        else:
            raise AssertionError("non-finite limit accepted")
    for price in (float("nan"), float("inf"), -1):
        try:
            PricingInfo("USD", price, 1, "fixture")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid pricing accepted")


def test_registry_has_no_implicit_fallback():
    registry = ProviderRegistry()
    try:
        registry.get("missing")
    except DecisionError as exc:
        assert exc.error_class == "unsupported_provider"
    else:
        raise AssertionError("missing provider silently resolved")


def test_direct_execute_enforces_configured_question_limit():
    request = DecisionRequest("facts", {
        "q1": ChoiceQuestion("First", {"a": "A", "b": "B"}),
        "q2": ChoiceQuestion("Second", {"a": "A", "b": "B"}),
    })
    config = ModelConfig("alternate", "model-x", limits={"questions": 1})
    registry = ProviderRegistry()
    registry.register("alternate", AlternateProtocolAdapter())
    try:
        execute(request, config, registry)
    except DecisionError as exc:
        assert exc.error_class == "question_limit_exceeded"
    else:
        raise AssertionError("question limit was not enforced")
