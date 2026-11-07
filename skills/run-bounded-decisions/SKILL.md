---
name: run-bounded-decisions
description: Prepare and run a finite set of evidence-based choices through an explicitly configured decision model, with spend limits, durable receipts and safe resumption. Use for prepared classification or comparison residuals after accepted decisions and deterministic rules have been applied.
---

# Run bounded decisions

Turn prepared facts and named options into reviewable recommendations through a batch runner or an embedded application adapter. The caller owns source preparation, accepted business decisions and downstream writes. This skill owns the bounded model step and the checks on its evidence.

## Establish the task

Identify the question, factual sources, allowed options and the person or process that accepts the result. Apply existing accepted decisions and deterministic rules first. Return missing or contradictory source facts to preparation. Keep the ambiguous, factually prepared remainder for the model.

Each question needs a finite criteria map and an explicit abstention choice. Record its exact ID and downstream meaning. An existing `clarify` choice can serve this role in an embedded application. The Python batch CLI requires the literal `insufficient`; use its supported format or prepare an explicitly reviewed adapter mapping. Describe what evidence supports each option. Keep benchmark answers, accepted decisions, internal file paths, hashes and rule versions in local evaluation or freshness fields. The application prepares `state`: inspect its contents as well as the provider payload allowlist before execution.

## Choose the execution route

For a finite offline or batch cohort, use the installed Python package and follow the batch steps below. For an application with its own event/job runner, use a module in that application's existing runtime and follow the embedded route. For a shared Python/TypeScript integration, use `bounded-task/1` for the provider-neutral task and `bounded-decisions/1` for the operation record. Read the bundled common contract and shared synthetic fixtures. Keep provider/model selection and the local acceptance profile separate from the factual task. The Jev wire request has its own transport schema. Record the chosen version, acceptance profile, request/result contract and owners of budgeting, durable outcomes, reuse and recovery. A provider transport performs one operation; the selected runner owns orchestration.

## Prepare a batch plan

Require Python 3.10+ and the locally installed `decision-kit` package. Resolve the approved package version and read its README and migration instructions. Installation from a trusted checkout uses `python -m pip install /path/to/decision-kit`; preserve the project's dependency environment.

Choose an explicit config with provider, model, supported tasks, request limits, currency and pricing provenance. Confirm the configured adapter and model support the question. Additional live providers and model changes follow the caller's authority. The shipped live adapter is PlusVibe `/v1/decisions`; the second protocol exists in offline tests.

Generate the installed package's synthetic starter files with `python -m decision_kit.examples example-inputs`. Adapt `example-inputs/cases.json` and `example-inputs/plusvibe.json` into the project's chosen case/config files. Give each case a stable ID. Include significant source/rule versions in local `cache_context` so changing evidence invalidates reuse.

```sh
python -m decision_kit --config config.json --cases cases.json --output review-run
```

The default command validates the cohort and saves its plan. Review the request count, estimated spend, local freshness identities and intended output directory. Keep factual unknowns explicit. Expected answers stay local for scoring.

## Execute a batch within authority

Before the paid step, establish the approved provider/model, exact cohort, request cap and spend cap. Use the configured credential environment variable. Keep credentials in memory and their existing secret store.

```sh
python -m decision_kit --config config.json --cases cases.json --output review-run --execute --max-requests 8 --max-cost 1
```

For the batch command, the spend value uses the configuration's currency. The local estimate controls admission; receipts record actual provider cost separately. Review the package's estimate method and tariff provenance when setting the cap. Unknown billing stops further calls for investigation.

The runner persists a pending receipt before calling the provider. An interrupted or uncertain request remains held for reconciliation with the provider's records. Resolve the exact outcome before considering a resubmission. Preserve receipt and lock evidence during recovery; verify the recorded process before removing an abandoned lock. Automatic paid retries remain disabled.

## Embedded application route

Read the approved module's task/result contract, then identify its actual consumer. Build an application adapter for its facts, named questions, abstention and next action. Select a provider adapter separately; the neutral task remains stable when changing providers. Validate the response structurally, evaluate the consumer's local acceptance profile, and compare local expected answers only for explicitly labeled quality checks. TypeScript `bounded-decision-core` supplies neutral execution and evaluation; the `jev-decision-core` adapter supplies one-operation transport and normalization. Python exposes the same neutral JSON interface through `decision_kit.universal`. Read its documented capabilities and pending contract gaps. Keep task criteria, confidence thresholds, abstention mapping, urgent-route priority, permissions and fallback selection in the application adapter.

Name the existing owners of job identity, deadlines, attempt reservations, request/spend caps, durable pending/terminal outcomes, recovery and zero-call reuse. Verify that the combined caller and module enforce them. If an owner or check is missing, finish the independent local checks and report the exact gap before paid execution. Preserve approved application behavior while extracting a module; record any difference from the shared safety policy and bring accepted-meaning changes to its owner.

Separate normalized provider observations from consumer acceptance. Record requested/returned model, actual billed amount/currency/source when observed, estimated amount and tariff separately, optional usage/probabilities/confidence, uncertainty and receipt/reuse metadata. Validate optional observations when present. A consumer that requires confidence or usage must have an explicit missing-field/fallback rule. A successful response and a charged error each need accounting provenance in the owning runner. Preserve an observed charge through HTTP, body-read, decoding and validation failures; retain known zero, unknown amount and malformed billing separately. Use the versioned record mapper after acceptance, and persist pending/final records under the same attempt ID. Verify the interrupted charged response and the repeat run with zero new calls. Reused records retain historical billing; count new spending by newly issued attempt IDs.

Validate model identity before new shared-contract acceptance. An existing compatibility policy that accepts returned aliases or a nonmatching model needs its own recorded scope and parity checks. For an uncertain attempt, retain its identity/outcome for reconciliation. Record transport attempts separately from job restarts and check their combined duplicate-charge exposure. Resolve an accepted retry-policy conflict before changing that policy.

Freeze baseline inputs and compare the original and extracted caller/module on identical saved outcomes. For an existing application, use its authorized real regression population and preserve source gaps; supplement it with synthetic conformance fixtures for every option and relevant failure state. Mark reconstructed confidence/usage separately. Verify payloads, selected routes, abstentions, critical priorities, fallback, reservations, deadlines and delivery-facing state. Keep exact evidence for module parity and fresh model-quality evaluation separately scoped.

## Resume and accept

For the batch route, repeat the same command with the same inputs and output directory to reuse terminal receipts. For the embedded route, replay the same completed job identity through its owning runner. Verify zero new requests and zero new cost. A changed provider, model, request or significant local dependency needs a fresh reviewed identity and plan; the batch CLI uses a fresh output directory. Keep the original run for provenance.

Review valid choices, abstentions, refusals, technical errors and uncertain requests separately. Provider probabilities are optional at the common contract layer; the consumer owns any stricter acceptance rule. Match each recommendation to the supplied evidence and preserve the caller's acceptance authority before any business write.

Hand off the chosen package/module/runtime version and contract identity, configured provider and requested model, returned-model evidence with its receipt provenance, answered and held counts, known billed cost, estimate and currency, reused receipts, unresolved outcomes, and durable result location. Label saved or reconstructed observations by their source. Keep private evidence with its owning project.

## Connect another project

Prepare facts in the project's own script, run accepted-rule filtering, then pass the residual cases through the chosen runtime route. Keep source, model/provider, rule and local dependency identities explicit. Test a new adapter's normalized response offline before any live request. Use the Python package's migration guide for the legacy `decision_model` interface. For export, select reusable code/contracts and synthetic fixtures, while retaining real examples, credentials, internal paths and application policy in their owning storage.
