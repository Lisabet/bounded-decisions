# decision-kit brand evidence recipe

This recipe prepares a bounded brand-attribution or token-role cohort for `decision-kit`. It resolves exact current accepted decisions, direct source brand fields, and unique accepted-alias matches in product titles. The calling application owns packet storage, factual acceptance, and follow-up actions; `decision-kit` handles provider transport and operation records. Residual model choices are recommendations for human semantic review.

## Prepare and plan

The fictional packet at `examples/example.packet.json` shows the `brand-evidence-packet/1` schema. Each case has a unique `case_id` and task key (`stable_id`, `task_kind`, and `token` for token-role cases), a `source_row`, candidate choices, and evidence. Optional fields include accepted aliases, accepted brand history, explicit raw brand, evidence-backed `accepted_term_roles`, packet-level `shared_term_facts`, and local evaluation labels. A term role is `{term, role, evidence_id}` with role `brand`, `line`, `product_title`, or `product_type`; its evidence reference must resolve within the same effective case. A shared fact is `{term, role, evidence}` and its evidence object uses the same fields as case evidence. The fictional packet includes a shared fact used across matching cases. Item package and shipping carton stay separate; unknown factual values may be `null`.

A caller can prepare the packet and write an offline plan with its own configuration:

```python
from decision_kit.cli import config_from_mapping, read, run
from decision_kit.recipes.brand_evidence import prepare_effective_cases, prepare_packet

packet = read("examples/example.packet.json")
prepared = prepare_packet(packet)
model_cases = prepared["model_cases"]
# If accepted brand fingerprints must be prepared for shared facts:
effective_cases = prepare_effective_cases(packet)
if model_cases:
    config = config_from_mapping(read("caller-config.json"))
    plan = run(model_cases, "./brand-review", config=config,
               execute_calls=False, max_requests=len(model_cases), max_cost=0)
    print(plan["status"], plan["new_requests_this_run"])
else:
    print("All cases have a local resolution.")
```

`caller-config.json` is supplied by the caller using the installed package's config schema. The dry plan records zero provider requests. Inspect it before considering a paid run. That later call must be an explicit caller decision with `execute_calls=True`, finite request and spend caps, configured pricing provenance, provider credentials, and a registered provider. `decision-kit` owns transport, spend controls, receipts, and recovery.

## Decisions and evidence

An accepted brand resolves only when its stable ID and `facts_sha256` match current effective facts. Use `prepare_effective_cases(packet)` to obtain copied cases with matching shared facts applied before computing fingerprints. Changed accepted facts are held for reconciliation. Shared facts apply by exact normalized token phrase in the original title, exact token-role token, or exact candidate canonical name/accepted alias. `Garden` therefore matches a standalone `Garden` token and the exact candidate `Garden`, while `Gardenish` remains separate. Product-title matching uses accepted alias registry terms and complete Unicode token boundaries. An accepted `product_type`, `product_title`, or `line` filters candidates whose canonical name or accepted alias exactly matches that term. Other candidates remain for review even when only one is left; an empty brand-choice set yields local `insufficient`. The model receives accepted term roles and evidence, with direct guidance that a shared product type across producers is category evidence and brand identity comes from separate evidence. Input packet objects remain unchanged; `packet_sha256` binds the original packet, while each case fingerprint covers its effective facts.

A `token_role` case remains a separate question with `brand`, `line`, `product_title`, `product_type`, `insufficient`, and `conflict` choices. An exact normalized token with a current accepted term role resolves locally. A current accepted brand is included as context for the role question; conflicting brand facts go to reconciliation. `RULES_VERSION` is now `brand-evidence-review/2`. Populated accepted term roles and token-role facts use the v2 fingerprint; brand-attribution facts use the v1 fingerprint whenever accepted term roles are empty, preserving reuse for established accepted-brand records. Existing token-role accepted fingerprints require reconciliation under v2.

Local evaluation labels (`expected` and `expected_basis`) support caller-side scoring. Provider questions receive evidence-backed state and choice criteria. Every model choice is a recommendation for human semantic review; the calling application controls factual acceptance and any follow-up action.

## Offline tests

With Python 3.10+, pytest, and `decision-kit` installed:

```console
python -m pytest -q tests/test_brand_evidence.py
```

Tests load the recipe directly and exercise the installed `decision_kit.cli.run` dry-plan path. The dry-plan check records zero provider calls.

## Conditional control cases

Set `case_origin: "synthetic_control"` for fictional controls. Their `SYNTHETIC_CONTROL` evidence supplies a conditional premise scoped to the stated product and package. Unmarked cases with this evidence are held before accepted-brand, RAW, and alias shortcuts; marked cases pass through the existing accepted-decision and conflict checks. Unknown origins are rejected. The origin enters the request and fact fingerprint, while ordinary cases that omit it retain their established fingerprints. Brand attribution follows evidence naming the product or a family that explicitly includes its package; missing applicable evidence yields `insufficient`, and contradictory applicable evidence yields `conflict`.
