# decision-kit 0.1.2rc3

`decision-kit` is a small, provider-neutral Python package for bounded multiple-choice decisions. It provides a typed request and result contract, explicit provider/model configuration, a provider registry, centrally validated results, and a resumable CLI. Runtime dependencies are from the Python standard library.

## Install and prepare

From this directory, install with `python -m pip install .`. Python 3.10 or newer is required.

Generate the shipped synthetic starter files, then create a local plan. The plan validates the full cohort and writes `plan.json`. Provider calls start only when `--execute` is present:

```console
python -m decision_kit.examples example-inputs
python -m decision_kit --config example-inputs/plusvibe.json --cases example-inputs/cases.json --output ./decision-run
```

Inspect the plan, then explicitly enable requests with finite request and spend caps:

```console
set PLUSVIBE_API_KEY=your-key
python -m decision_kit --config example-inputs/plusvibe.json --cases example-inputs/cases.json --output ./decision-run --execute --max-requests 1 --max-cost 0.05
```

In PowerShell, use `$env:PLUSVIBE_API_KEY = '...'` for the current session. The CLI keeps the key in process memory and excludes it from plans, receipts, and console output. The Jev 1.13 example uses the PlusVibe catalog tariff checked on 2026-11-07: RUB 7.40 per million input tokens and RUB 0 per million output tokens (https://gw.plusvibeapi.ru/models). Confirm the tariff again before a future execution. The plan records the configured currency and pricing provenance. The estimate uses UTF-8 request bytes as an input-size proxy plus a configured output allowance; it is a budget guard, while the provider response header supplies the recorded billed amount.

Input JSON uses `provider`, `model`, `task_capabilities`, `limits`, and a `pricing` object with currency, input/output rates per million, and provenance. `endpoint` and `timeout` can be set for a provider configuration. Each case contains `case_id`, `state`, one explicit `choice` question, an `insufficient` choice, optional local `expected`, local `dependencies`/`cache_context`, and `rules_version`. `expected`, dependencies, and cache context stay local; only `state` and question instructions/criteria go to the adapter.

## Result and safety behavior

The normalized result reports the selected choice, provider, requested and returned model, UTC timestamp, usage, optional probabilities, actual billed cost and currency/provenance, estimated cost and its separate provenance, and reuse status. Missing probabilities remain absent. The shared validator checks provider/model identity, question and choice IDs, optional probability vectors, usage, costs, and currencies for every adapter.

The CLI writes an atomic plan and receipt files. An output directory is bound to the complete case cohort and provider configuration, including endpoint, model and local dependency versions. Existing receipts are checked before any new request. A matching completed receipt is reused with zero provider calls. A pending request blocks resume until an operator reconciles its outcome. Unknown spend blocks subsequent requests. Each request is sent once; a lock records the current process owner, and recovery starts after owner inspection.

The shipped adapter is PlusVibe. It uses HTTPS, sends one request per call through a redirect-disabled transport, and keeps arbitrary transport/provider response text out of surfaced errors. The registry dispatches providers by explicit registration. Add another provider by implementing `DecisionProvider.decide(request, config)` and returning a `DecisionResult`; the shared validator then applies the same result checks. `tests/test_core.py` contains an offline adapter with a deliberately different wire protocol to demonstrate normalization using an in-memory response.

## API example

```python
from decision_kit import (
    ChoiceQuestion, DecisionRequest, ModelConfig, PricingInfo,
    ProviderRegistry, PlusVibeAdapter, execute,
)

request = DecisionRequest(
    state={"description": "Container marked 500 ml"},
    questions={"category": ChoiceQuestion(
        "Choose the supported category.",
        {"volume": "A volume measure", "insufficient": "Insufficient facts"},
    )},
    dependencies={"input": "record-v1", "rules": "category-v2"},
    rules_version="category-v2",
)
config = ModelConfig(
    provider="plusvibe", model="typesafe/jev-1.13",
    task_capabilities=frozenset({"choice"}),
    limits={"request_bytes": 100_000, "questions": 20},
    pricing=PricingInfo("RUB", 7.4, 0, "PlusVibe Jev 1.13 catalog; verified 2026-11-07"),
)
registry = ProviderRegistry()
registry.register("plusvibe", PlusVibeAdapter())
# execute(request, config, registry) sends a provider request and uses PLUSVIBE_API_KEY.
```

Use `execute` for a single validated provider operation. Use the CLI when the task needs a durable plan, a bounded cohort, receipts, and safe continuation.

## Compatibility

The package includes the namespaced compatibility API `decision_kit.compat`, with `DecisionClient`, `read`, `save`, `run`, and `encoded`. The top-level `decision_model` and `cmd_decision_model` imports support callers whose import paths are unshadowed by application-local modules. For applications with modules under those names, import through `decision_kit.compat`. Compatibility receipt files retain legacy fields such as `actual` and `billed_cost_rub` alongside normalized fields.

Run the offline tests from this directory with `python -m pytest tests -p no:cacheprovider`. The test suite uses in-memory provider transports.


## Shared Python/TypeScript record

`bounded-decisions/1` provides a JSON operation record and bundled request/result schemas in `decision_kit.contract_data`. Use `to_record(result_or_error, config, receipt_id=attempt_id)` after central acceptance. The CLI stores `contract_result` in each completed or held receipt. Known billed amount, currency and source survive HTTP, body-read, JSON and response-validation failures. A zero charge stays observed; missing or invalid billing keeps paid continuation held. Interrupted body reads retain observed headers and an uncertain pending outcome.

This candidate adds stricter rejection of malformed billing headers, explicit null confidence/probabilities and unsafe token integers. Existing installed 0.1.0 consumers can evaluate the candidate through their saved-outcome checks before changing dependencies. See the shared contract's README and bundled schemas for fields, profile differences and recovery ownership.


## Universal task interface

The provider-neutral task, application acceptance profile and one-operation adapter interface are documented in the [shared contract](../decision-contract/README.md). The existing entry points remain available. New application integrations can use the neutral task while keeping their own preparation, reservations, storage and next-action rules.
