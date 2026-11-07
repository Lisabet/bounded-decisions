# Changelog

## 0.1.1rc1

- Added bounded-decisions/1 record mapping and bundled schemas/shared fixtures.
- Persisted common records and billing provenance in CLI error receipts.
- Preserved known response billing through body-read and validation failures.
- Aligned strict decimal headers, optional-field null rejection and safe token counts across runtimes.


## 0.1.0

- Added the provider-neutral choice request/result contracts and explicit `ModelConfig` with task capabilities, limits, and pricing provenance.
- Added centrally validated provider registry dispatch and the PlusVibe adapter.
- Added a plan-first CLI with bounded explicit execution, atomic cohort manifests/receipts, reuse, and pending/unknown-spend stops.
- Added legacy `decision_model` and `cmd_decision_model` compatibility imports for staged migrations.
- Added offline unit and CLI coverage plus generalized examples.
