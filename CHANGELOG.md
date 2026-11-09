# Bounded Decisions 0.1.0-preview.5

Adds an optional Python recipe for preparing evidence-backed brand-attribution and term-role questions. Accepted facts, direct source fields and accepted aliases resolve locally; residual model choices are recommendations for human semantic review. Start with the fictional example and offline plan in [the recipe guide](packages/decision-kit/BRAND_EVIDENCE.md).

Python package: `0.1.2rc4`. Shared task/result contracts and provider adapters retain their existing versions.

---

# Bounded Decisions 0.1.0-preview.4

Connect prepared finite-choice tasks from your application to an explicitly selected decision provider. The new universal core has Python and TypeScript entry points, a shared task/result contract and separate adapters for application data and provider APIs.

The first concrete provider adapter uses the Jev decisions protocol. Local profiles validate the response and decide whether it is accepted, needs review or is rejected. Labeled examples can also compare the chosen answer with an expected answer. Operation records retain observed costs and safe error metadata, including charged failures and uncertain attempts.

Start with the runnable offline examples, then connect your application's own reservations, durable outcomes and recovery. Both runtimes use the same synthetic conformance matrix.

We use this workflow in our own projects and would love your feedback, especially from other applications, models and environments. Synthetic or anonymized examples help us improve the task and adapter boundaries.

Adapters can validate a configured selection before execution. Configuration mismatches raise a local validation error with zero provider operations; uncertain dispatched operations retain their pending recovery path.

The Jev 1.13 example and compatibility configuration use the official PlusVibe tariff checked on 2026-11-07: RUB 7.40 per million input tokens and RUB 0 per million output tokens. Provider-reported billing remains separately recorded. The shared source has been checked in installed Python and TypeScript applications, including live billing and completed-result reuse.

See the [provider guide](https://github.com/Lisabet/bounded-decisions/blob/v0.1.0-preview.4/docs/providers.md) for PlusVibe setup and other Jev-compatible services. PlusVibe [account registration](https://plusvibeapi.ru/?ref=JWGVWW4S) uses a referral link.
