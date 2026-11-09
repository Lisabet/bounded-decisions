# Recipes

Recipes package application-specific fact preparation around the shared decision contract. The current brand-evidence recipe ships in the Python `decision-kit` package at [`packages/decision-kit/BRAND_EVIDENCE.md`](../../packages/decision-kit/BRAND_EVIDENCE.md), with its implementation under `packages/decision-kit/decision_kit/recipes/brand_evidence.py` and fictional packet under `packages/decision-kit/examples/example.packet.json`.

That recipe resolves current accepted evidence and exact local matches before creating residual finite-choice tasks. Model choices remain recommendations for human semantic review; the calling application controls factual acceptance and follow-up. The recipe is currently available in Python. Its source guide contains packet fields, fingerprint rules, planning example, and offline checks.

Use the shared [task contract](../contracts/README.md) for another application-specific recipe. Keep domain facts, accepted decisions, and local evaluation examples with their owning application.