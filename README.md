# Bounded Decisions

Connect an application's prepared facts and named choices to a decision provider. Python and TypeScript share a task/result contract, local acceptance checks, and operation records that retain observed costs through success and failure.

## One request path

```text
application records -> application adapter / optional recipe
  |-- locally resolved cases ----------------------> application
  `-- remaining bounded-task/1 + provider/model + local profile
        -> core task checks
        -> runner reserves budget and attempt identity
        -> provider adapter -> bounded-decisions/1 operation record
        -> core record checks and local acceptance evaluation
        -> accepted / review / rejected -> runner persists outcome
```

`bounded-task/1` contains stable task identity, rules version, factual `state`, and questions with instructions, criteria, and optional abstention choice. Provider/model selection and the local acceptance profile travel as separate inputs. Before dispatch, the application's runner reserves budget and durable attempt identity; after evaluation, it persists the result and owns recovery and continuation. The operation record reports provider and model identity, answers, usage, observed billing with source, a separate estimate, and attempt receipt. The core returns the record with its local evaluation outcome. The application adapter prepares facts; the provider adapter maps the task to a service protocol; the application's runner owns permissions, caps, durable storage, retries, recovery, and next action.

| Role and current route | Canonical source | Readiness |
| --- | --- | --- |
| Shared task/result contract, schemas, offline examples | [`packages/decision-contract`](packages/decision-contract/README.md) | Python and TypeScript implementations use the shared JSON contract |
| Python core and universal task executor | [`decision_kit/universal.py`](packages/decision-kit/decision_kit/universal.py), [`decision_kit/core.py`](packages/decision-kit/decision_kit/core.py) | Shipped in `decision-kit` |
| Python PlusVibe Jev adapter and batch runner | [`decision_kit/providers/plusvibe.py`](packages/decision-kit/decision_kit/providers/plusvibe.py), [`decision_kit/cli.py`](packages/decision-kit/decision_kit/cli.py) | Shipped API route; batch planning, receipts, reuse, and spend admission in Python |
| TypeScript provider-neutral core | [`src/index.ts`](packages/bounded-decision-core/src/index.ts) | Shipped single-operation execution; host application supplies its runner |
| TypeScript PlusVibe Jev transport and record mapper | [`src/adapter.ts`](packages/jev-decision-core/src/adapter.ts), [`src/jev.ts`](packages/jev-decision-core/src/jev.ts) | Shipped API route; single operation |
| Generic provider adapter interface | Python [`decision_kit/universal.py`](packages/decision-kit/decision_kit/universal.py); TypeScript [`src/index.ts`](packages/bounded-decision-core/src/index.ts) | Interface and injected synthetic examples are available offline; service transports and accounting maps are implementation work |
| Brand-evidence application adapter and recipe | [`decision_kit/recipes/brand_evidence.py`](packages/decision-kit/decision_kit/recipes/brand_evidence.py), [guide](packages/decision-kit/BRAND_EVIDENCE.md) | Python recipe; accepted facts and exact local matches resolve locally, residual questions can go to a model for human semantic review |
| OpenAI service integration | Provider adapter extension point above | Planned |
| Optional agent skill | [`skills/run-bounded-decisions/SKILL.md`](skills/run-bounded-decisions/SKILL.md) | Integration workflow; install separately from runtime packages |

## Start offline

Clone the repository, then run commands from its root:

```sh
git clone https://github.com/Lisabet/bounded-decisions.git
cd bounded-decisions
```

Python 3.10 or newer:

```sh
python -m pip install ./packages/decision-kit
python packages/decision-contract/examples/python_app.py
```

Node 24.x, version 24.16 or newer:

```sh
node packages/decision-contract/examples/typescript_app.ts
```

Both examples use synthetic adapters and produce zero provider operations. The fixtures exercise the common task/result boundary; the [Python brand-evidence recipe](packages/decision-kit/BRAND_EVIDENCE.md) is an application-specific local preparation route. See the [offline examples](packages/decision-contract/examples/README.md).

## Start with an application

Prepare `bounded-task/1` with stable identity, rules version, factual state, named questions and choices, plus an insufficient-facts choice where needed. Select provider/model and local acceptance profile separately. An application adapter prepares one task; the selected core invokes one provider operation and evaluates the returned operation record. The application's runner persists the attempt and applies its follow-up rules.

Python installs into the existing project environment with `python -m pip install ./packages/decision-kit`; its universal API and batch CLI are described in [Python setup](docs/runtimes/python.md). For Node, keep `bounded-decision-core` and `jev-decision-core` as sibling source directories; see [TypeScript setup](docs/runtimes/typescript.md). The TypeScript adapter imports its sibling core, so preserve that source layout.

## Add a provider adapter

A provider adapter receives one prepared task, explicit provider/model selection, and operation context; it returns a `bounded-decisions/1` operation record for a completed response, known error, or uncertain pending outcome. Implement wire mapping, safe failure metadata, and observed billing provenance. The shipped API integration is PlusVibe through Jev in Python and TypeScript. The generic interface has offline synthetic examples. Additional API transports and their accounting maps are future integration work; OpenAI integration is planned. Read [provider routes](docs/providers/README.md).

Before enabling requests, check service semantics, charged failures, missing or malformed cost observations, timeout recovery, and result reuse through the owning application runner. The runner tracks attempt identity, limits, persistence, reconciliation, and continuation. See [execution ownership](docs/execution/README.md).

## Connect PlusVibe

Configure an API key, endpoint, model, verified tariff, and request/spend limits through your application's established configuration. Start with a saved plan; the Python batch CLI's default mode makes zero provider operations.

[Create a PlusVibe account (referral link)](https://plusvibeapi.ru/?ref=JWGVWW4S). The referral link is optional; [provider setup and accounting](docs/providers/README.md) describe the integration. Verify tariffs in the direct [model catalog](https://gw.plusvibeapi.ru/models) before execution.

Run [offline checks](CONTRIBUTING.md) before adapter changes. Both runtimes use shared synthetic fixtures; application regression data stays with its owner. The kit has also been exercised in Python and TypeScript applications with live cost recording and completed-result reuse.

## Use with an agent

Ask your agent's skill installer to install `skills/run-bounded-decisions` from the repository revision you use. Clone the repository separately for its runtime packages. The skill provides the integration workflow; package setup follows the commands above.

## Brand evidence recipe

The Python package includes a [brand evidence recipe](packages/decision-kit/BRAND_EVIDENCE.md). It prepares source-backed brand and term-role questions, applies accepted facts and exact matches locally, then sends residual questions to a model for recommendations that receive human semantic review. Start with the fictional packet and offline plan in the recipe guide.

## Feedback and license

We welcome feedback from other applications, models and environments. Open an issue with your setup, expected behavior and a synthetic or anonymized example. See [data and credential handling](SECURITY.md) before sharing a report.

[MIT license](LICENSE). Package versions and extension boundaries are listed in the component READMEs. Find the complete [documentation map](docs/README.md).