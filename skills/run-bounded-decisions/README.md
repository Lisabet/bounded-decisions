# Run bounded decisions

Use prepared facts and named options to produce decisions with explicit acceptance checks, operation records and cost evidence. Connect an existing application through an application adapter, and select a model API through a provider adapter. Python and TypeScript share the same task and result contracts.

## Choose your path

| Your job | Entry point | What you supply |
| --- | --- | --- |
| Review a finite batch | Python batch CLI | Cases, provider configuration, limits and durable output directory |
| Classify within an existing application | Universal task executor | Prepared task, provider selection, acceptance profile and adapter registry |
| Connect another model API | Provider adapter interface | Wire mapping, one operation, safe error mapping and observed accounting |

Read the [shared explanation](../../packages/decision-contract/README.md) first: it follows a request through the application, core, provider and back to the application's next action. [Task](../../packages/decision-contract/task.schema.json), [selection](../../packages/decision-contract/selection.schema.json), [local profile](../../packages/decision-contract/policy.schema.json) and [outcome](../../packages/decision-contract/outcome.schema.json) have versioned JSON schemas. The [Jev wire request](../../packages/decision-contract/request.schema.json) is the current transport mapping.

## Install the skill and choose a runtime

Install `skills/run-bounded-decisions` through your agent's skill installer from this repository. Clone the same approved revision to use its runtime packages; the skill's instructions and runtime code have separate installation steps.

From the repository root, for Python 3.10+, install the package into your project's existing dependency environment:

```sh
python -m pip install ./packages/decision-kit
```

The Python package offers `execute_task`, `evaluate_record` and `make_jev_adapter` through `decision_kit.universal`. Its existing batch command is described in the [Python README](../../packages/decision-kit/README.md). A default CLI run saves a plan with zero provider operations.

For Node 24.x (24.16 or newer), copy `packages/bounded-decision-core` and `packages/jev-decision-core` into sibling directories in the application's vendor folder. Import the source files there. The [TypeScript core README](../../packages/bounded-decision-core/README.md) explains the registry and module boundary. The [offline examples](../../packages/decision-contract/examples/) demonstrate both entry points with injected synthetic adapters.

## Configure the application boundary

Prepare `bounded-task/1` with a stable task ID, rules version, factual state and named choice questions. Specify the abstention choice and its meaning. Configure provider/model selection and local acceptance separately. Keep credentials, expected answers, thresholds and local storage identities in the owning application.

Structural checks validate the operation record and requested choices. The local profile determines `accepted`, `review` or `rejected`. Optional expected choices support labeled quality comparisons. An application can keep an existing alias or extra-answer compatibility policy explicitly in its adapter, with its regression examples.

The application's runner owns permission to call, request/spend caps, pre-request reservations, durable pending state, retries, reconciliation and zero-call reuse. A provider adapter performs one operation. Check those owners before enabling paid execution. Keep model confidence, acceptance and measured quality separate in the resulting evidence.

## Verify before use

Run the Python and both TypeScript package tests, then `scripts/check_decision_contract.ps1` on Windows. These checks use synthetic provider observations. Test your application's own saved cohort, critical priorities, failure accounting, pending recovery and completed-result reuse through its existing runner. Keep private cohorts with the application and export synthetic examples with the reusable core.
