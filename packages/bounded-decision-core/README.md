# Bounded decision core

Connect an application's prepared finite-choice task to an explicitly selected provider adapter. The core validates the common operation record and applies the application's local acceptance profile. It uses native Node TypeScript on Node 24.16+ and carries zero runtime dependencies.

Read the [shared contract](contract/README.md) for roles, fields, accounting and recovery. Use the [Jev adapter](../jev-decision-core/README.md) for the current concrete provider transport.

## Install into an existing application

Keep `bounded-decision-core` and `jev-decision-core` as sibling source directories under the application's chosen vendor folder. The Jev adapter imports the neutral sibling. Native Node TypeScript runs these source files outside `node_modules`. The existing application owns its dependency, job and storage setup.

## Adapter interface

Register explicit adapters in a `Map` keyed by provider identity. Each adapter implements `decide(task, selection, context)` and returns a `bounded-decisions/1` operation record for success, error or pending. `executeTask` validates task/selection/profile/context before selecting and calling the adapter. An unexpected adapter exception yields an uncertain pending outcome for reconciliation. Invalid configuration stops before invocation.

The core imports provider-neutral code only. A provider adapter owns request mapping, transport, response normalization and provenance. The application adapter owns factual preparation, criteria, abstention meaning and downstream action. Replace one adapter while keeping the task and the other adapter stable, then verify the resulting behavior.

## Checks and interpretation

Run `npm test` here. Tests cover synthetic observations and the shared neutral fixture matrix. `accepted`, `review` and `rejected` describe the configured acceptance profile. Optional `expected_choices` compares a labeled regression answer; confidence describes the model's reported observation. Keep acceptance and quality records with the input/rule versions used for that operation.
