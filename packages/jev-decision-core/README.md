# Jev decision core — 0.1.0-candidate.3

Typed TypeScript transport for the Jev decisions protocol, for Node 24.16+.
The module has zero runtime dependencies. Run `npm test` for the offline synthetic conformance fixtures.

## Integration

1. Prepare a `JevRequest`: explicit `model`, factual `state`, and named choice `questions` with instructions and criteria.
2. Pass an explicit endpoint, API key, fetch implementation, timeout and optional positive byte limits to `postJevOnce`.
3. Call `validateJevResult(result, request)` before accepting the decision. It requires matching model identity and question/choice IDs; optional observations are validated when present.
4. Apply the application's confidence, abstention, spending, retry and delivery policy. Persist an outcome before any downstream operation and retain uncertain attempts for reconciliation.

Only `model`, `state`, `questions`, and the nested `type`/`instructions`/`criteria` fields reach the provider. Keep local expected answers, cache identities and provenance outside `state`. The application prepares that factual state.

`postJevOnce` performs one POST with redirects disabled. Default limits: 160000 request bytes and 1048576 response bytes. An injected fetch must honor AbortSignal. HTTPS is required except for loopback test endpoints. Keys stay in the request header; errors carry a code, optional HTTP status/retry delay and an uncertainty flag.

`JevNormalizedResult` preserves requested/returned models, answers, optional token usage, an observed RUB charge from the PlusVibe `x-pv-cost-rub` response header, and a separate optional caller estimate. Missing observations remain absent; malformed usage/billing is flagged for strict validation. The endpoint and chosen model remain explicit configuration owned by the caller.

## Relationship to decision-kit 0.1.2rc1

This TypeScript protocol module is an extraction candidate for applications with an existing job runner. The Python decision-kit package owns its provider registry, multi-case CLI, receipt files, locks, reuse and spend admission. This module supplies the one-operation transport/validation layer; the consumer owns those orchestration functions.

Native observation fields: normalized names follow TypeScript camelCase and RUB-specific billing fields; timestamp, model version, provider label and elapsed time are caller metadata. Probabilities/confidence and usage can be absent at normalization. A strict acceptance call requires model identity. HTTP, body-read, size-limit, UTF-8/JSON and validation failures retain observed amount, RUB currency, header source and status. Safe responseStatus metadata survives copying and serialization. Application compatibility adapters may retain their established validation policy explicitly.

## Export boundary

The package contains this README, package metadata, transport and contract source modules, synthetic tests and a file-hash manifest. The source distribution uses vendored TypeScript files. The `private: true` package setting reserves registry publication for an explicit release decision. Host applications keep task-specific criteria, real conversations, credentials, receipts and repository history in their own storage.


## Common operation record

Import `acceptDecisionRecord` and `toDecisionRecord` from `jev-decision-core/contract`. Accept the normalized response with `acceptDecisionRecord(result, request, {provider: 'plusvibe', receiptId: attemptId})`; map a caught `JevTransportError` with `toDecisionRecord`. This emits the same `bounded-decisions/1` record as Python. The module bundles schemas and shared synthetic fixtures under `contract/`. Caller estimates can carry `estimateSource` in the mapping context. Missing estimate provenance uses null.

The application runner persists pending/final records, accounts billed amounts by attempt ID, and provides caps, reconciliation and zero-call reuse. A known charge remains attached to an uncertain stream failure. Malformed or missing billing requires a hold before further paid work. The shared contract README explains profile requirements, field mapping and recovery examples.


## Universal task interface

The provider-neutral task, application acceptance profile and one-operation adapter interface are documented in the [shared contract](contract/README.md). The existing entry points remain available. New application integrations can use the neutral task while keeping their own preparation, reservations, storage and next-action rules.


Use `makeJevAdapter` from `src/adapter.ts` with `executeTask` from the sibling `bounded-decision-core/src/index.ts`. Configure its URL, credential, injected fetch and timeout explicitly. Register it under the selected provider identity. It translates the neutral task into the Jev request and returns a common operation record, including failures.

The `plusvibe` provider identity enables the observed RUB cost header mapping. Other explicit identities using this wire protocol produce unknown observed billing. `allowExtraAnswers` and `returned_model_policy: any_nonempty` are explicit consumer compatibility choices. Local `onError` and `onResult` callbacks expose safe transport metadata for an existing runner's retry timing and validation receipts. The application continues to own its retry and recovery rules.
