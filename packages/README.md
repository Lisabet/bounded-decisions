# Package source map

| Path | Role | Current implementation |
| --- | --- | --- |
| [`decision-contract`](decision-contract/README.md) | Shared contract, schemas, fixtures, offline examples | Canonical JSON contract plus Python and TypeScript examples |
| [`decision-kit`](decision-kit/README.md) | Python runtime, provider registry, recipe, batch runner | PlusVibe adapter; Python generic interface in `decision_kit/universal.py` |
| [`bounded-decision-core`](bounded-decision-core/README.md) | TypeScript provider-neutral core | Task checks, adapter dispatch, record checks, evaluation |
| [`jev-decision-core`](jev-decision-core/README.md) | TypeScript Jev protocol adapter | Single operation and PlusVibe cost-header mapping |

The two TypeScript directories remain siblings because the Jev adapter imports the neutral core by sibling source path. Host applications own their integration storage and runner. See [architecture docs](../docs/README.md) for roles and onboarding routes.