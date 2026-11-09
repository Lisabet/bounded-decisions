# Connecting providers

This guide covers the shipped PlusVibe Jev integration and the generic provider interface. See the [documentation map](../README.md), [shared contracts](../contracts/README.md), and [execution ownership](../execution/README.md).

Choose a path based on the provider's actual API and accounting format. The neutral task and local acceptance profile remain owned by your application.

## PlusVibe with Python

You need a PlusVibe account, an API key and a verified model/tariff. [Account registration (referral link)](https://plusvibeapi.ru/?ref=JWGVWW4S); [model catalog](https://gw.plusvibeapi.ru/models).

From the repository root, install the package and generate the synthetic starter files:

```sh
python -m pip install ./packages/decision-kit
python -m decision_kit.examples example-inputs
python -m decision_kit --config example-inputs/plusvibe.json --cases example-inputs/cases.json --output decision-run
```

The last command writes a plan with zero provider operations. Inspect the case cohort, model, endpoint, price provenance and output directory. `plusvibe.json` contains the explicit provider identity, model, limits and pricing. Its optional `endpoint` field supplies a full HTTPS decisions URL; the shipped PlusVibe client also has its service default.

Set `PLUSVIBE_API_KEY` in the current process using your existing secret-management method. For PowerShell, use `$env:PLUSVIBE_API_KEY = 'your-key'`; for a POSIX shell, use `export PLUSVIBE_API_KEY='your-key'`.

After approving the plan and budget, use the CLI's `--execute --max-requests 1 --max-cost 0.10` flags with those same paths. The cost cap uses the configuration's currency. Repeat with the same inputs and output directory to reuse saved completed receipts. The runner holds uncertain outcomes and unknown spend for reconciliation.

For embedded Python use, create `ModelConfig`, register `PlusVibeAdapter` in `ProviderRegistry`, then pass `make_jev_adapter(config, registry)` to `decision_kit.universal.execute_task`. The [Python API example](../../packages/decision-kit/README.md#api-example) provides the explicit configuration. Your application's runner supplies reservations, persistence and the execution gate.

## PlusVibe or another Jev-compatible endpoint with TypeScript

Configure the full HTTPS decisions URL, Bearer key, model and a stable provider identifier. Keep runtime directories as siblings under the application's vendor folder:

```ts
import {makeJevAdapter} from './vendor/jev-decision-core/src/adapter.ts';

const endpoint = process.env.JEV_ENDPOINT;
const apiKey = process.env.JEV_API_KEY;
const provider = process.env.JEV_PROVIDER;
const model = process.env.JEV_MODEL;
if (!endpoint || !apiKey || !provider || !model) {
  throw new Error('Configure JEV_ENDPOINT, JEV_API_KEY, JEV_PROVIDER and JEV_MODEL');
}
const selection = {provider, model};
const registry = new Map([[provider, makeJevAdapter({
  url: new URL(endpoint), apiKey, fetchImpl: fetch, timeoutMs: 30_000,
})]]);
// Pass selection and registry to executeTask through your application's runner.
```

This setup prepares an adapter. Your runner decides when to call `executeTask`. The transport sends one POST with Bearer authorization and JSON fields `model`, `state` and `questions`; each question contains `type`, `instructions` and `criteria`. It checks returned question/choice/model identities and preserves safe failure metadata. Verify these requirements against the service's documented API and saved responses.

The provider identifier `plusvibe` enables observed RUB billing from the `x-pv-cost-rub` response header. For another identifier, the shipped adapter returns `billing: null` and `billing_state: "unknown"`. A successful response with unknown billing requires review; known operation errors remain rejected, and pending attempts require reconciliation. Implement the service's own billing mapping in its adapter, including charged failures. Record actual amount, currency and evidence source; keep tariff-based estimates in `estimate`.

Python's supplied `PlusVibeAdapter` enforces `provider="plusvibe"` and its RUB accounting. For a different service, register your own provider adapter in the Python API or implement the neutral interface below. Provider identity and accounting provenance should identify the service actually used.

## Another API or accounting format

Implement a provider adapter with `decide(task, selection, context)`. Register it by the same provider identifier used in selection. Return the common [operation record](../../packages/decision-contract/record.schema.json) for a completed response, a known error or an uncertain attempt. The core validates the record and evaluates the local profile.

An optional `validate_selection` in Python or `validateSelection` in TypeScript performs local configuration checks before dispatch. Translate provider-specific fields at this boundary; preserve observed charges when transport, decoding or validation fails. The [offline Python](../../packages/decision-contract/examples/python_app.py) and [TypeScript](../../packages/decision-contract/examples/typescript_app.ts) examples demonstrate registration and common results using two synthetic adapters.

Before enabling requests, verify the normal answer, abstention, model identity, charged HTTP/body/JSON failure, missing or malformed billing, timeout recovery and completed-result reuse. Keep evidence under the same attempt identity. Your application's runner reconciles uncertain attempts and counts new spending by newly issued attempts.
