# Offline application examples

Both examples prepare a delivery-routing task, select each of two synthetic providers, and receive the same accepted route with a labeled quality match. External provider operations and spending are zero. The examples illustrate the application/core/provider boundary.

From the repository root, after installing `decision-kit`, run `python packages/decision-contract/examples/python_app.py`. With Node 24.x (24.16 or newer), run `node packages/decision-contract/examples/typescript_app.ts`. Each prints an accepted delivery route for `fixture-a` and `fixture-b`.

To connect Jev, register the concrete Jev adapter instead of the synthetic adapter. Keep the task unchanged, select an approved provider/model, and supply the application's explicit attempt, accounting and recovery owners. Additional API adapters implement the same single-operation record contract and require their own protocol and quality checks.
