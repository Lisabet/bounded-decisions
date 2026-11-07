# Contributing

Use Python 3.10+ and Node 24.16+. From the repository root:

```sh
python -m pip install ./packages/decision-kit pytest
python -m pytest packages/decision-kit/tests -p no:cacheprovider
python packages/decision-contract/examples/python_app.py
node packages/decision-contract/examples/typescript_app.ts
npm --prefix packages/bounded-decision-core test
npm --prefix packages/jev-decision-core test
```

On Windows with PowerShell 7, also run `./scripts/check_decision_contract.ps1`. It validates schemas and exact contract copies bundled with each runtime. CI runs the offline suites on Linux and Windows with Python 3.10 and 3.12.

Keep examples synthetic and tests offline. For adapter changes, check success, identity mismatches, charged failures, unknown billing and pending recovery. Preserve the distinction between provider observations, local acceptance and labeled quality measurements. Add shared fixtures when changing the cross-runtime contract, and update all bundled copies together.

Open a focused issue or pull request describing the behavior, expected outcome and checks performed. Use synthetic inputs and remove keys, personal data and application records from reports.
