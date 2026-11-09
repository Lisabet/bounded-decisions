# Python runtime

Requires Python 3.10 or newer. Install into the existing project environment from the repository root:

```sh
python -m pip install ./packages/decision-kit
python packages/decision-contract/examples/python_app.py
```

The offline example injects synthetic adapters and makes zero provider operations. For a prepared task in an existing application, import `execute_task` and `make_jev_adapter` from `decision_kit.universal`; see [`decision-kit`](../../packages/decision-kit/README.md) and the [shared contract](../../packages/decision-contract/README.md).

The CLI adds bounded batch planning, admission limits, durable receipts, completed-result reuse, and pending-attempt holds. Run a default plan first and inspect the cohort and accounting configuration before any separately authorized provider execution. The shipped production adapter is PlusVibe; another API can implement the generic Python provider interface.

The Python-only [brand-evidence recipe](../../packages/decision-kit/BRAND_EVIDENCE.md) prepares source-backed questions and routes residual choices to human semantic review.