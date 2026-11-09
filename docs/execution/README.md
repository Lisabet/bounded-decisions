# Execution lifecycle and ownership

A provider adapter performs one operation and returns a common operation record. The application runner owns the lifecycle around it: permissions, request/spend caps, durable attempt identity, reservation before send, persistence, retries, reconciliation, and terminal-result reuse.

The Python `decision-kit` CLI provides a bounded multi-case runner with plans, atomic receipts, locks, resume, and reuse. The TypeScript cores expose one-operation execution; the consuming application provides its runner. This difference is visible in the [core map](../core/README.md).

Record observed charges with provider evidence and keep tariff estimates separate. A known charge remains attached to an error or uncertain attempt. Pending attempts require reconciliation under their original identity. Reuse retains the historical receipt and charge; newly issued operation totals count each durable attempt once. The Python runner holds automatic paid continuation when spend is unknown or billing is malformed.

Before connecting live traffic, verify the host runner's saved-outcome parity, pending recovery, and zero-call reuse using its own accepted cases. Provider API calls, budgets, and credentials belong to a separately authorized application operation.