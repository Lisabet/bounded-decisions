# TypeScript runtime

Node 24.x, version 24.16 or newer, runs the TypeScript source directly. From the repository root, run the offline example:

```sh
node packages/decision-contract/examples/typescript_app.ts
```

It uses injected synthetic adapters and makes zero provider operations. For an existing Node application, keep [`bounded-decision-core`](../../packages/bounded-decision-core/README.md) and [`jev-decision-core`](../../packages/jev-decision-core/README.md) as sibling source directories under its vendor folder. This sibling relationship is part of the current import layout.

`bounded-decision-core` provides provider-neutral task execution and local evaluation. `jev-decision-core` maps one Jev operation, including the PlusVibe observed RUB header. The host application's runner owns durable storage, budgets, attempt recovery, and completed-result reuse. The generic adapter interface supports new implementations; each additional wire protocol and billing map is prospective work.