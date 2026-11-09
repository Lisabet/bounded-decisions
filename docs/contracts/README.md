# Contracts

The cross-runtime task and result contracts live in [`packages/decision-contract`](../../packages/decision-contract/README.md). Its canonical JSON schemas describe `bounded-task/1`, provider/model selection, local acceptance policy, `bounded-decisions/1` operation records, and evaluated outcomes. Synthetic Python and TypeScript examples show identical task/result concepts.

The application adapter converts owned records into prepared factual state, named questions, criteria, and permitted choices. The shared contract carries those prepared facts and decision boundaries across the provider call. The provider adapter maps them to its wire request and normalizes the response and accounting observations.

Task identity, rules version, question IDs, choice membership, model identity, usage, billing provenance, estimate, and durable attempt receipt have separate fields. This lets each runtime apply structural checks and then evaluate its local profile. The [component README](../../packages/decision-contract/README.md) is canonical for field details, mappings, and fixtures.