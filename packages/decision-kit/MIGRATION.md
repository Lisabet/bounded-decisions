# Migration guide

## Install and choose a configuration

Install the local package with `python -m pip install .` from the package root, or install its reviewed wheel. Runtime dependencies come from the Python standard library. Run `python -m decision_kit.examples example-inputs` to create the bundled synthetic starter files from an installed package. Create an explicit config with provider, model, task capabilities, limits, and pricing source. Keep credentials in the provider's documented environment variable; the PlusVibe adapter reads `PLUSVIBE_API_KEY` only when a provider request is made.

## Move a direct client call

The earlier imports continue to work during migration:

```python
from decision_model import DecisionClient

result = DecisionClient(api_key=key).decide(state, questions)
```

The provider-neutral interface makes provider/model configuration and cost provenance explicit:

```python
from decision_kit import DecisionRequest, ModelConfig, PricingInfo, ProviderRegistry, PlusVibeAdapter, execute

request = DecisionRequest.from_mapping(state, questions, dependencies={"source": "snapshot-v1"})
config = ModelConfig("plusvibe", "typesafe/jev-1.13",
    task_capabilities=frozenset({"choice"}),
    limits={"request_bytes": 100_000, "questions": 20},
    pricing=PricingInfo("RUB", 7.4, 0, "PlusVibe Jev 1.13 catalog; verified 2026-11-07"))
registry = ProviderRegistry()
registry.register("plusvibe", PlusVibeAdapter(api_key=key))
result = execute(request, config, registry)
```

Existing application code can import the compatible names through `decision_kit.compat`, which exports `DecisionClient`, `read`, `save`, `run`, and `encoded`. The runner retains the `run(cases, output, execute=False, max_requests=..., max_cost_rub=..., client_factory=...)` shape and forwards bounded execution to the shared runner with legacy receipt aliases. This namespaced route works alongside application-local modules named `cmd_decision_model` or `decision_model`.

## Move a bounded cohort

1. Put only decision facts and question criteria in the case file. Keep known-answer labels, private evidence, and expected outcomes local.
2. Give each case a stable ID. Set `dependencies` and `rules_version` to the exact local versions that affect interpretation. Use `cache_context` for additional local fingerprints.
3. Run the CLI in plan mode by omitting `--execute`, inspect `plan.json`, and confirm provider, model, full cohort, limits, pricing currency, and tariff provenance.
4. Execute with explicit `--max-requests` and `--max-cost`. Reuse the same output directory only for the exact same cohort and provider configuration.
5. Read receipts and `summary.json`. Reconcile a `pending` request with provider-side records before creating a fresh output directory or resubmitting. A receipt with unknown billed cost stops subsequent calls in that cohort.

The result schema allows provider-specific usage keys, optional probability vectors, actual billed cost, and a separate estimate. Provider adapters normalize their response into this schema; the common validator checks the returned model and answer against the requested configuration and question.

## Compatibility limits

The application owner retains business mappings and persistence. Validate the existing decision flow against the new package before applying the migration.
