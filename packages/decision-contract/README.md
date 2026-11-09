# Bounded decisions: tasks, adapters and operation records

Use `bounded-task/1` to describe a prepared finite-choice task and `bounded-decisions/1` to record a provider operation. Python and TypeScript exchange the same JSON. Applications supply facts, criteria and acceptance rules; provider adapters translate the task into their wire protocol and normalize the response, errors and observed costs.


## Roles and one request path

An application adapter builds a task from its own records. The task names its ID and rules version, prepared factual state, questions, allowed choices and optional abstention choice. The application separately chooses a provider/model and local acceptance profile. A provider adapter sends one operation and returns an operation record. The common core validates the record and evaluates the local profile. The application's existing runner persists attempts and decides its next action.

```text
Application data -> application adapter -> bounded-task/1
                                          |
                         explicit provider/model + provider adapter
                                          |
                                bounded-decisions/1
                                          |
                      common validation + local acceptance profile
                                          |
                           application's next action and storage
```

The neutral task stays the same when a provider changes. A new application supplies its own factual preparation and interpretation of accepted, review and rejected outcomes. A new provider supplies its wire mapping, safe error mapping and cost provenance. The current Jev adapter is the first concrete transport; additional APIs can implement the same adapter interface. Their model quality and provider-specific accounting require their own checks.

## Neutral task and local profile

The exact task fields are `task_version: bounded-task/1`, `task_id`, `rules_version`, `state` and `questions`. Each question has `type: choice`, `instructions`, at least two `criteria` entries and an optional `abstain_choice` naming one of those entries. The schema is [task.schema.json](task.schema.json); runtimes also enforce cross-field membership, whitespace and JSON-value checks. The core supports one to twenty questions.

```json
{
  "task_version": "bounded-task/1",
  "task_id": "synthetic-delivery-1",
  "rules_version": "support-routes/1",
  "state": {"message": "Move delivery to Friday"},
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "Choose the department from the prepared facts.",
      "criteria": {
        "delivery": "Delivery scheduling",
        "payment": "Payment and refunds",
        "review": "A person should review the request"
      },
      "abstain_choice": "review"
    }
  }
}
```

Pass provider/model selection, credentials and acceptance separately. Provider adapters send factual state and question instructions/criteria. Task IDs, rules versions, abstention metadata, expected answers and acceptance thresholds remain local. The caller includes any evidence needed to answer within the factual state.

The evaluation outcome retains task identity, the full operation record and three separate observations:

- Structural validation checks exact fields, selected option membership, model identity, numeric ranges and record consistency. An invalid provider answer produces a safe error record with usable observed billing retained.
- Local acceptance returns `accepted`, `review` or `rejected`. A profile can require confidence, complete probabilities, token usage or a minimum confidence; explicitly named choices may bypass the confidence threshold. Abstention and unknown billing request review. The application defines how to handle that review, reservations and recovery.
- Optional quality comparison checks selected answers against local `expected_choices`. It returns per-question matches and an overall match. This supports labeled regression cases; the expected answers stay with the caller. Model-reported confidence remains a separate answer observation.

The neutral core performs one adapter operation per invocation. The owning runner provides caps, pending-before-send storage, deadlines, terminal reuse and reconciliation. It reconciles a `review` result with the application's accepted policies before further paid work. Reuse retains the historical charge and attempt ID. New-operation totals deduplicate by durable attempt identity.

Default returned-model acceptance requires an exact match. An existing consumer can explicitly select `returned_model_policy: any_nonempty` and record its compatibility scope. The Jev adapter separately exposes `allowExtraAnswers` for consumers that historically ignore additional answer IDs. Keep these choices explicit in that consumer's adapter and regression tests.

## Choose the runtime

Python `decision-kit 0.1.2rc4` provides provider registration, budget admission, a batch CLI, atomic receipts and resume. TypeScript `bounded-decision-core` provides neutral validation, provider selection and local evaluation. `jev-decision-core` supplies a single Jev transport operation and its adapter. An embedded application's runner supplies durable pending outcomes, attempt identities, budgets and reconciliation.

The bundled JSON schemas describe the wire request and operation record. Their canonical copies and synthetic response matrix live here. Each runtime bundles byte-identical copies so installed packages carry the contract. Shared fixtures test the same provider responses and expected records in both runtimes.

## Request and local context

The Jev wire-specific `request.schema.json` allows explicit `model`, a nonempty factual `state`, and one to twenty named choice questions. Each question has `type: choice`, instructions and at least two criteria keyed by option ID. Select an explicit abstention ID and keep its downstream meaning in the application. The Python batch CLI uses `insufficient`.

The application owns input population, evidence and acceptance. Expected answers, source versions, cache identities, credentials, receipt IDs and budget settings belong to local context. Prepare the factual state before transport and inspect the resulting payload. Whitespace-only identifiers or descriptions fail runtime validation.

## Operation record

| Field | Meaning |
| --- | --- |
| `contract_version` | Exact record version: `bounded-decisions/1`. |
| `provider`, `requested_model`, `returned_model` | Explicit adapter identity, requested model and accepted returned model. Error records use a null returned model. |
| `status`, `error`, `uncertain` | Accepted `ok`, terminal `error`, or held `pending`; safe error code and observed HTTP status accompany failures. |
| `answers` | Accepted named choices with optional confidence/probabilities. Error records use an empty object. |
| `usage` | Observed `input_tokens` and/or `output_tokens`, or null when unavailable. Values are nonnegative JavaScript-safe integers. |
| `billing`, `billing_state` | Observed amount, currency and source, or null with `unknown`/`invalid` state. A known zero has `observed` state. |
| `estimate` | Caller estimate with its currency and source, separate from observed billing. A null source records unavailable provenance. |
| `receipt` | Caller-owned attempt ID and an explicit reuse flag. Reuse requires a durable ID. |

All fields are present. Optional observations use null or omitted nested keys as specified in `record.schema.json`. Confidence and probability values, when supplied, are numeric and within 0–1. A probability vector covers every available choice and totals 1 within tolerance 0.02. JSON null in those answer fields fails strict validation. Model identity and option membership are validated against the request. Schema checks cover structure and cross-field consistency; runtime validators also check the matching request.

The common observation contract permits missing token observations. Python's PlusVibe acceptance profile requires both token counts. The existing TypeScript strict profile validates usage when supplied. A consumer can require confidence, usage or other observations through its own explicit acceptance/fallback rule. These profiles remain visible at integration time.

## Field mapping and acceptance

| Python | TypeScript | Record |
| --- | --- | --- |
| `requested_model` / `returned_model` | `requestedModel` / `returnedModel` | `requested_model` / `returned_model` |
| `billed_cost`, `billed_currency`, `billed_cost_provenance` | `observedBilledCostRub` and the PlusVibe adapter's RUB/header provenance | `billing.amount`, `currency`, `source` |
| `billing_header_invalid` | `billingHeaderInvalid` | `billing_state: invalid` |
| `estimated_cost`, currency/provenance | `estimatedCostRub`, optional caller provenance | `estimate` |
| `receipt`, `reused` | explicit mapper context | `receipt` |
| `DecisionError` fields | `JevTransportError` fields | `error`, `uncertain`, retained billing |

In Python, call `execute(request, config, registry)`, catch `DecisionError`, and map either accepted result or safe error with `to_record(value, config, receipt_id=attempt_id)`. The CLI persists this record as `contract_result` alongside its established receipt fields.

In TypeScript, call `postJevOnce`, then `acceptDecisionRecord(result, request, {provider: 'plusvibe', receiptId: attemptId})`. Catch `JevTransportError` and call `toDecisionRecord(error, request, context)`. The low-level mapping helpers accept already validated results or safe errors; acceptance is performed before mapping. TypeScript's Jev adapter derives RUB billing from the PlusVibe header for the explicitly selected PlusVibe provider. Additional wire protocols need their own adapter mapping. Python's explicitly supported generic `input`/`output` usage aliases map to token keys; other custom usage units remain in the native result.

## Charged failure and recovery

For an HTTP 503 response with `x-pv-cost-rub: 0.03`, both implementations retain:

```json
{
  "status": "error",
  "billing": {"amount": 0.03, "currency": "RUB", "source": "PlusVibe x-pv-cost-rub response header"},
  "billing_state": "observed",
  "uncertain": false,
  "error": {"code": "http", "http_status": 503}
}
```

This excerpt shows the failure fields; the full record also carries contract, provider, request and receipt identity. Headers are read before response decoding. Both runtimes preserve observed billing on HTTP errors, interrupted reads, invalid UTF-8/JSON and strict response rejection. TypeScript also retains billing when its response byte limit is reached. TypeScript keeps safe response status in the normalized result so copying or serializing it preserves later validation evidence.

A pre-header timeout records `pending`, unknown billing and its attempt ID. A stream interruption after a charged header records `pending` with the observed amount. Retain that amount while reconciling the uncertain attempt. Missing or malformed billing blocks automatic paid continuation in the Python runner; the embedded runner must provide the same hold and recovery ownership. Accepted application retry policies are reconciled with this common policy before adopting it.

Persist the pending identity before the call, then atomically store the final record. On resume, reuse terminal receipts with zero new calls. Deduplicate billing by attempt ID: a reused record still describes the historical charge, while new-call totals count only newly issued attempts. Error records expose structural metadata; credentials and provider response text stay outside the record.

## Verify and integrate

From `packages/decision-kit`, run `python -m pytest tests -p no:cacheprovider`. From `packages/jev-decision-core`, run `npm test` on Node 24.x (24.16 or newer). The fixture matrix includes success, optional observations, unknown/zero/invalid charges, HTTP errors, malformed JSON, wrong model/choice, invalid confidence/probabilities/usage, timeouts and unusual question IDs. All provider responses and amounts are synthetic; calls and spending in these tests are zero.

`scripts/check_decision_contract.ps1` validates the schemas, rejects contradictory records and checks bundled copies. Before adoption, test the actual consumer's saved-outcome parity, pending recovery and zero-call resume. Live model-quality checks use their own authorized cohort and budget. Choose the public package scope, license and exact release text before publication.


### Adapter selection preflight

Adapters with fixed local configuration may expose `validate_selection(selection)` in Python or `validateSelection(selection)` in TypeScript. The hook validates a copied selection synchronously before `decide`, performs zero provider operations, and raises a local validation exception on mismatch. Python's Jev bridge checks its configured provider and model at this boundary. The caller can correct configuration before creating a dispatched-attempt record. Once `decide` begins, an unexpected exception retains the conservative `pending` outcome for reconciliation. Provider adapters return safe operation records for known transport failures and observed charges.
