# Bounded Decisions

Connect your application's prepared facts and named choices to a decision provider. Python and TypeScript share a task/result contract, local acceptance checks and operation records that retain observed costs through success and failure.

Use this kit to classify records, route requests or evaluate a finite set of options inside an existing application. Your application prepares the facts and controls what happens after the decision. The core validates the result; a provider adapter handles the API.

## Start offline

Python 3.10+:

```sh
git clone https://github.com/Lisabet/bounded-decisions.git
cd bounded-decisions
git checkout v0.1.0-preview.4
python -m pip install ./packages/decision-kit
python packages/decision-contract/examples/python_app.py
```

The synthetic example prints an accepted delivery-routing result for each of two injected adapters. Provider calls: zero.

Node 24.x (24.16 or newer) can run the TypeScript example directly from this checkout:

```sh
node packages/decision-contract/examples/typescript_app.ts
```

For an existing Node application, copy `packages/bounded-decision-core` and `packages/jev-decision-core` into sibling directories in its vendor folder. The [TypeScript setup](packages/bounded-decision-core/README.md) explains the source layout.

## Connect a provider

The shipped production adapter supports PlusVibe's Jev decisions endpoint. Configure your own API key, endpoint, model, verified tariff and request/spend limits. Start with a saved plan, then explicitly enable paid execution through your application's runner or the Python batch CLI.

[Create a PlusVibe account (referral link)](https://plusvibeapi.ru/?ref=JWGVWW4S). The referral link is optional; API setup and accounting are described in [Connecting providers](docs/providers.md). Use the direct [model catalog](https://gw.plusvibeapi.ru/models) to verify tariffs before execution.

For another Jev-compatible service, the TypeScript transport accepts its HTTPS endpoint and Bearer key. Add that service's observed-cost mapping and verify its response/error behavior. Python's shipped transport is registered for PlusVibe; a different provider implements the shared adapter interface. The [provider guide](docs/providers.md) walks through these paths.

## Fit the kit into your application

1. Prepare a `bounded-task/1` task: stable identity, rules version, factual state, named questions and choices, including what to do when facts are insufficient.
2. Select the provider/model and configure a local acceptance profile. Optional expected answers support labeled regression checks.
3. Reserve an attempt and budget in your runner, invoke one operation, then persist its `bounded-decisions/1` record and local evaluation.
4. Continue according to the application's rules. Reuse completed outcomes by identity and reconcile uncertain attempts before another paid call.

The core returns choices, acceptance/review/rejection, model identity, optional usage/confidence, observed billing with provenance and a separate estimate. Your runner owns permissions, caps, durable storage, retries and recovery. [The shared explanation](packages/decision-contract/README.md) follows a complete request and explains these responsibilities.

## Components

| Component | Purpose |
| --- | --- |
| [decision-kit](packages/decision-kit/README.md) | Python API, provider registry, resumable bounded batch CLI and universal task interface |
| [bounded-decision-core](packages/bounded-decision-core/README.md) | Provider-neutral TypeScript execution and local evaluation |
| [jev-decision-core](packages/jev-decision-core/README.md) | One-operation Jev transport and normalization |
| [decision-contract](packages/decision-contract/README.md) | Shared JSON schemas, synthetic conformance cases and offline examples |
| [run-bounded-decisions](skills/run-bounded-decisions/SKILL.md) | Optional agent skill for preparing and checking integrations |

## Use with an agent

Ask your agent's skill installer to install `skills/run-bounded-decisions` from this repository at the release revision. Clone the repository separately for its runtime packages. The skill provides the integration workflow; package setup follows the commands above.

## Development and feedback

Run the [offline checks](CONTRIBUTING.md) before changing an adapter. Both runtimes use shared synthetic fixtures; application-specific regression data stays with its owner. This preview has also been exercised in our own Python and TypeScript applications, including live cost recording and completed-result reuse.

We would love feedback from other applications, models and environments. Open an issue with your setup, expected behavior and a synthetic or anonymized example. See [data and credential handling](SECURITY.md) before sharing a report.

[MIT license](LICENSE). Package versions and extension boundaries are listed in the component READMEs.
