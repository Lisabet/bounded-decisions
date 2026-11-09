from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "decision_kit" / "recipes" / "brand_evidence.py"
spec = importlib.util.spec_from_file_location("portable_brand_evidence", MODULE)
brand = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = brand
spec.loader.exec_module(brand)


def case(**updates):
    value = {
        "case_id": "example-case",
        "stable_id": "example-item-01",
        "task_kind": "brand_attribution",
        "source_row": {
            "supplier": "Fable Grove Ltd",
            "original_name": "Citrus sauce, Riverlight 250 ml",
            "article": "FG-01",
            "item_package": {"quantity": 250, "unit": "ml", "container": "bottle"},
            "carton": {"count": 8},
            "raw_fields": {"brand": None},
            "source_ref": {"file": "fictional-catalog.xlsx", "sheet": "Items", "row": 4},
        },
        "candidates": [
            {"id": "riverlight", "name": "Riverlight"},
            {"id": "orchard-line", "name": "Orchard Line"},
        ],
        "evidence": [{
            "id": "source-01", "source_type": "OFFICIAL_SITE", "locator": "https://example.invalid/items/01",
            "accessed_at": "2030-01-01", "text": "Fictional evidence names Riverlight as the product brand.",
            "scope": "product brand",
        }],
        "accepted_aliases": {"River Light": "Riverlight", "Riverlight": "Riverlight"},
    }
    value.update(updates)
    return value


def packet(*cases):
    return {"schema": "brand-evidence-packet/1", "cases": list(cases)}


def test_accepted_alias_resolves_and_title_match_uses_token_boundaries():
    title = brand.prepare_packet(packet(case()))
    assert title["resolved"][0]["route"] == "raw_title_brand"
    assert title["resolved"][0]["recommendation"] == "riverlight"
    exact_alias = case(source_row={**case()["source_row"], "original_name": "River Light citrus sauce"})
    exact = brand.prepare_packet(packet(exact_alias))
    assert exact["resolved"][0]["route"] == "raw_title_brand"
    substring = case(source_row={**case()["source_row"], "original_name": "Riverlightish citrus sauce"})
    assert len(brand.prepare_packet(packet(substring))["model_cases"]) == 1


def test_title_candidate_without_accepted_alias_stays_residual():
    item = case(source_row={**case()["source_row"], "original_name": "Orchard Line citrus sauce"},
                accepted_aliases={})
    prepared = brand.prepare_packet(packet(item))
    assert len(prepared["model_cases"]) == 1


def test_changed_accepted_facts_are_held_for_reconciliation():
    item = case(source_row={**case()["source_row"], "original_name": "Unmarked citrus sauce"})
    previous = {"brand": "Riverlight", "covers_stable_id": item["stable_id"],
                "facts_sha256": brand.facts_sha256(item)}
    item["accepted_brand"] = previous
    assert brand.prepare_packet(packet(item))["resolved"][0]["route"] == "accepted_brand"
    changed = {**item, "source_row": {**item["source_row"], "article": "FG-02"}}
    held = brand.prepare_packet(packet(changed))
    assert held["holds"][0]["route"] == "technical_hold"
    assert not held["model_cases"]


def test_same_product_can_have_brand_and_distinct_token_role_tasks():
    brand_case = case(case_id="brand-task", source_row={**case()["source_row"], "original_name": "Unmarked item"})
    token_case = case(case_id="token-task", task_kind="token_role", token="Select", source_row={**case()["source_row"], "original_name": "Unmarked item"})
    prepared = brand.prepare_packet(packet(brand_case, token_case))
    assert prepared["counts"]["model"] == 2
    with pytest.raises(ValueError, match="stable_id/task_kind/token"):
        brand.prepare_packet(packet(token_case, {**token_case, "case_id": "duplicate-token-task"}))


def test_token_role_keeps_accepted_brand_as_context_not_shortcut():
    item = case(case_id="token-context", task_kind="token_role", token="Select",
                explicit_raw_brand="Riverlight",
                source_row={**case()["source_row"], "original_name": "Unmarked item"})
    item["accepted_brand"] = {"brand": "Riverlight", "covers_stable_id": item["stable_id"],
                              "facts_sha256": brand.facts_sha256(item)}
    prepared = brand.prepare_packet(packet(item))
    assert prepared["counts"]["resolved"] == 0
    assert len(prepared["model_cases"]) == 1
    assert prepared["model_cases"][0]["state"]["accepted_brand_context"]["brand"] == "Riverlight"
    assert prepared["model_cases"][0]["state"]["explicit_raw_brand"] == "Riverlight"
    assert set(prepared["model_cases"][0]["question"]["criteria"]) == {
        "brand", "line", "product_title", "product_type", "insufficient", "conflict"}


def test_item_package_and_shipping_carton_remain_separate():
    item = case(source_row={**case()["source_row"], "original_name": "Unmarked item"})
    state = brand.prepare_packet(packet(item))["model_cases"][0]["state"]["source_row"]
    assert state["item_package"] == {"quantity": 250, "unit": "ml", "container": "bottle"}
    assert state["carton"] == {"count": 8}


def test_installed_decision_kit_accepts_example_in_offline_plan(tmp_path):
    from decision_kit.cli import config_from_mapping, read, run

    example = read(ROOT / "examples" / "example.packet.json")
    prepared = brand.prepare_packet(example)
    model_cases = prepared["model_cases"]
    assert len(model_cases) == 1
    config_path = tmp_path / "caller-config.json"
    config_path.write_text(json.dumps({"provider": "offline-fixture", "model": "offline-choice"}), encoding="utf-8")
    caller_config = config_from_mapping(read(config_path))
    plan = run(model_cases, tmp_path / "plan", config=caller_config,
               execute_calls=False, max_requests=len(model_cases), max_cost=0)
    assert plan["status"] == "planned"
    assert plan["new_requests_this_run"] == 0
    saved_plan = json.loads((tmp_path / "plan" / "plan.json").read_text(encoding="utf-8"))
    assert saved_plan["execute"] is False


def type_case(*, task_kind="brand_attribution", token=None, roles=None, candidates=None, **updates):
    value = case(case_id="type-case", stable_id="type-item-01", task_kind=task_kind,
        source_row={**case()["source_row"], "original_name":"Citrus Garden blend"},
        candidates=candidates or [
            {"id":"citrus","name":"Citrus Garden"},
            {"id":"citrus-foods","name":"Citrus Garden Foods"},
            {"id":"riverlight","name":"Riverlight"}],
        accepted_aliases={"Citrus Garden":"Citrus Garden", "Citrus Garden Foods":"Citrus Garden Foods",
                          "River Light":"Riverlight", "Riverlight":"Riverlight"},
        accepted_term_roles=roles or [{"term":"Citrus Garden", "role":"product_type", "evidence_id":"source-01"}])
    if token is not None: value["token"] = token
    value.update(updates)
    return value


def test_accepted_product_type_resolves_normalized_token_role_without_model():
    item=type_case(task_kind="token_role",token="  CITRUS garden  ")
    result=brand.prepare_packet(packet(item))
    assert result["resolved"][0]["route"]=="accepted_term_role"
    assert result["resolved"][0]["recommendation"]=="product_type"
    assert result["resolved"][0]["role_evidence_id"]=="source-01"
    assert not result["model_cases"]


def test_type_filters_exact_candidate_and_two_other_brands_stay_residual():
    item=type_case(expected="citrus-foods",expected_basis="fictional local label")
    before=json.dumps(item,ensure_ascii=False,sort_keys=True)
    prepared=brand.prepare_packet(packet(item))
    assert prepared["counts"]["model"]==1
    model_case=prepared["model_cases"][0]
    assert [c["id"] for c in model_case["state"]["candidates"]]==["citrus-foods","riverlight"]
    assert model_case["state"]["accepted_term_roles"]==item["accepted_term_roles"]
    assert "expected" not in json.dumps(model_case) and "expected_basis" not in json.dumps(model_case)
    assert json.dumps(item,ensure_ascii=False,sort_keys=True)==before


def test_empty_brand_choice_set_is_insufficient_and_longer_brand_is_not_excluded():
    only_type=type_case(candidates=[{"id":"citrus","name":"Citrus Garden"}],
        accepted_aliases={"Citrus Garden":"Citrus Garden"})
    result=brand.prepare_packet(packet(only_type))
    assert result["resolved"][0]["recommendation"]=="insufficient"
    assert result["resolved"][0]["route"]=="accepted_term_role"
    longer=type_case(source_row={**case()["source_row"],"original_name":"Citrus Garden Foods blend"},
        candidates=[{"id":"foods","name":"Citrus Garden Foods"},{"id":"riverlight","name":"Riverlight"}],
        accepted_aliases={"Citrus Garden Foods":"Citrus Garden Foods","Riverlight":"Riverlight"})
    result=brand.prepare_packet(packet(longer))
    assert result["resolved"][0]["route"]=="raw_title_brand"
    assert result["resolved"][0]["recommendation"]=="foods"


def test_explicit_and_accepted_brands_conflicting_with_type_role_hold():
    explicit=type_case(explicit_raw_brand="Citrus Garden")
    assert "accepted non-brand term role" in brand.prepare_packet(packet(explicit))["holds"][0]["reason"]
    accepted=type_case(candidates=[{"id":"citrus","name":"Citrus Garden"}],
        accepted_aliases={"Citrus Garden":"Citrus Garden"})
    accepted["accepted_brand"]={"brand":"Citrus Garden","covers_stable_id":accepted["stable_id"],
                                "facts_sha256":brand.facts_sha256(accepted)}
    assert "accepted brand conflicts" in brand.prepare_packet(packet(accepted))["holds"][0]["reason"]


def test_bad_term_role_evidence_fails_before_runner_and_duplicates_conflict():
    invalid=type_case(accepted_term_roles=[{"term":"Citrus Garden","role":"product_type","evidence_id":"missing"}])
    calls=[]
    with pytest.raises(ValueError,match="reference current case evidence"):
        brand.prepare_packet(packet(invalid))
    assert not calls
    duplicate=type_case(accepted_term_roles=[
        {"term":"Citrus Garden","role":"product_type","evidence_id":"source-01"},
        {"term":" CITRUS   GARDEN ","role":"line","evidence_id":"source-01"}])
    with pytest.raises(ValueError,match="duplicate normalized"):
        brand.prepare_packet(packet(duplicate))


def test_term_role_facts_change_fingerprint_but_plain_brand_facts_keep_legacy_hash():
    import hashlib
    plain=case(source_row={**case()["source_row"],"original_name":"Unmarked item"})
    old_payload={k:plain.get(k) for k in ("source_row","candidates","evidence","accepted_aliases","explicit_raw_brand","task_kind","token")}
    old_payload["rules_version"]="brand-evidence-review/1"
    old_hash=hashlib.sha256(json.dumps(old_payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()
    assert brand.facts_sha256(plain)==old_hash
    assert brand.facts_sha256(type_case())!=brand.facts_sha256({**type_case(),"accepted_term_roles":[]})


def test_type_token_conflicting_with_accepted_or_explicit_brand_holds():
    item=type_case(task_kind="token_role",token="CITRUS GARDEN",
        candidates=[{"id":"citrus","name":"Citrus Garden"}],
        accepted_aliases={"Citrus Garden":"Citrus Garden"})
    item["accepted_brand"]={"brand":"Citrus Garden","covers_stable_id":item["stable_id"],"facts_sha256":brand.facts_sha256(item)}
    assert "conflicts" in brand.prepare_packet(packet(item))["holds"][0]["reason"]
    item.pop("accepted_brand"); item["explicit_raw_brand"]="Citrus Garden"
    assert "conflicts" in brand.prepare_packet(packet(item))["holds"][0]["reason"]

def test_unrelated_accepted_brand_allows_type_role_and_unknown_brand_holds():
    item=type_case(task_kind="token_role",token="Citrus Garden",
        candidates=[{"id":"riverlight","name":"Riverlight"}],
        accepted_aliases={"Riverlight":"Riverlight"})
    item["accepted_brand"]={"brand":"Riverlight","covers_stable_id":item["stable_id"],"facts_sha256":brand.facts_sha256(item)}
    assert brand.prepare_packet(packet(item))["resolved"][0]["recommendation"]=="product_type"
    item["accepted_brand"]={"brand":"Unknown brand","covers_stable_id":item["stable_id"],"facts_sha256":brand.facts_sha256(item)}
    assert brand.prepare_packet(packet(item))["holds"]


def test_invalid_term_role_reference_fails_before_runner_path():
    invalid=type_case(accepted_term_roles=[{"term":"Citrus Garden","role":"product_type","evidence_id":"missing"}])
    calls=[]
    with pytest.raises(ValueError,match="reference current case evidence"):
        brand.prepare_packet(packet(invalid))
    assert not calls


def shared_term_fact(term="Citrus Garden",role="product_type",evidence=None):
    return {"term":term,"role":role,"evidence":evidence or case()["evidence"][0]}

def shared_case(case_id,title,candidates=None,stable_id=None,**updates):
    item=type_case(case_id=case_id,stable_id=stable_id or case_id,source_row={**case()["source_row"],"original_name":title},
        candidates=candidates or [
            {"id":"citrus","name":"Citrus Garden"},
            {"id":"riverlight","name":"Riverlight"},
            {"id":"meadowvale","name":"Meadow Vale"}])
    item.pop("accepted_term_roles",None)
    item.update(updates)
    return item

def test_shared_fact_propagates_across_ids_and_respects_boundaries_without_mutation():
    first=shared_case("random-case-a","Citrus Garden marinade")
    second=shared_case("synthetic-case-z","A Citrus Garden sauce")
    unrelated=shared_case("random-case-b","Citrus Gardenish marinade",
        candidates=[{"id":"riverlight","name":"Riverlight"},{"id":"meadowvale","name":"Meadow Vale"}],
        accepted_aliases={"Riverlight":"Riverlight","Meadow Vale":"Meadow Vale"})
    packet_value=packet(first,second,unrelated)
    packet_value["shared_term_facts"]=[shared_term_fact()]
    before=json.dumps(packet_value,ensure_ascii=False,sort_keys=True)
    effective=brand.prepare_effective_cases(packet_value)
    assert [len(c.get("accepted_term_roles",[])) for c in effective]==[1,1,0]
    assert all(c["evidence"][-1]["id"]=="source-01" for c in effective[:2])
    admission=brand.prepare_packet(packet_value)
    expected_packet_hash=__import__("hashlib").sha256(brand._canonical(packet_value)).hexdigest()
    assert admission["packet_sha256"]==expected_packet_hash
    assert json.dumps(packet_value,ensure_ascii=False,sort_keys=True)==before
    assert [brand.facts_sha256(c) for c in effective]==[brand.facts_sha256(c) for c in brand.prepare_effective_cases(packet_value)]

def test_shared_fact_applies_by_exact_token_and_candidate_alias():
    token=shared_case("token-task","Unmarked sauce",task_kind="token_role",token=" citrus garden ")
    alias=shared_case("alias-task","Unmarked sauce",
        candidates=[{"id":"citrus","name":"Citrus Garden"},{"id":"riverlight","name":"Riverlight"},{"id":"meadowvale","name":"Meadow Vale"}],
        accepted_aliases={"Citrus Blend":"Citrus Garden","Riverlight":"Riverlight","Meadow Vale":"Meadow Vale"})
    packet_value=packet(token,alias); packet_value["shared_term_facts"]=[shared_term_fact("Citrus Garden")]
    effective=brand.prepare_effective_cases(packet_value)
    assert len(effective[0]["accepted_term_roles"])==1
    assert len(effective[1]["accepted_term_roles"])==1

def test_shared_facts_validate_when_unused_and_detect_evidence_or_role_conflicts():
    unused=shared_case("unused","Plain sauce",
        candidates=[{"id":"riverlight","name":"Riverlight"},{"id":"meadowvale","name":"Meadow Vale"}],
        accepted_aliases={"Riverlight":"Riverlight","Meadow Vale":"Meadow Vale"})
    invalid=shared_term_fact(); invalid["evidence"]["text"]=""
    with pytest.raises(ValueError,match="shared_term_facts.*text"):
        brand.prepare_packet({**packet(unused),"shared_term_facts":[invalid]})
    conflicting=shared_case("evidence-id-conflict","Citrus Garden sauce")
    conflicting["evidence"].append({**case()["evidence"][0],"text":"different payload"})
    with pytest.raises(ValueError,match="shared evidence ID conflicts"):
        brand.prepare_packet({**packet(conflicting),"shared_term_facts":[shared_term_fact()]})
    override=shared_case("role-override","Citrus Garden sauce",
        accepted_term_roles=[{"term":"CITRUS GARDEN","role":"line","evidence_id":"source-01"}])
    with pytest.raises(ValueError,match="conflicts with case-level"):
        brand.prepare_packet({**packet(override),"shared_term_facts":[shared_term_fact()]})

def test_shared_fact_evidence_schema_and_duplicate_roles_are_validated_even_when_unmatched():
    unused=shared_case("unused-shared","Plain sauce",
        candidates=[{"id":"riverlight","name":"Riverlight"},{"id":"meadowvale","name":"Meadow Vale"}],
        accepted_aliases={"Riverlight":"Riverlight","Meadow Vale":"Meadow Vale"})
    f1=shared_term_fact("Unmatched term","product_type")
    f2=shared_term_fact(" unmatched   TERM ","brand",{**case()["evidence"][0],"id":"other-evidence"})
    with pytest.raises(ValueError,match="conflicting roles"):
        brand.prepare_packet({**packet(unused),"shared_term_facts":[f1,f2]})


def test_legacy_duplicate_case_roles_remain_invalid():
    item=shared_case("legacy-duplicate","Plain item",accepted_term_roles=[
        {"term":"Citrus Garden","role":"product_type","evidence_id":"source-01"},
        {"term":" citrus   garden ","role":"product_type","evidence_id":"source-01"}])
    with pytest.raises(ValueError,match="duplicate normalized accepted term roles"):
        brand.prepare_packet(packet(item))


def conditional_case():
    item=case(accepted_aliases={})
    item["evidence"][0]["source_type"]="SYNTHETIC_CONTROL"
    item["evidence"][0]["text"]="In this fictional case, all Citrus sauces in bottles are branded Riverlight."
    return item

def test_conditional_origin_preserves_premise_and_expected_is_local():
    item=conditional_case(); item["case_origin"]="synthetic_control";item["expected"]="riverlight"
    result=brand.prepare_packet(packet(item)); model=result["model_cases"][0]
    assert model["state"]["case_origin"]=="synthetic_control"
    assert model["state"]["evidence"]==item["evidence"]
    assert "expected" not in json.dumps(model)

def test_unmarked_conditional_evidence_holds_before_raw_shortcut():
    item=conditional_case();item["explicit_raw_brand"]="Riverlight"
    result=brand.prepare_packet(packet(item))
    assert result["counts"]["holds"]==1 and result["counts"]["resolved"]==0

def test_conditional_origin_keeps_existing_conflict_guard():
    item=conditional_case();item["case_origin"]="synthetic_control";item["explicit_raw_brand"]="Orchard Line"
    item["accepted_brand"]={"brand":"Riverlight","covers_stable_id":item["stable_id"],"facts_sha256":brand.facts_sha256(item)}
    assert brand.prepare_packet(packet(item))["counts"]["holds"]==1


def test_invalid_case_origin_is_rejected():
    item = case(source_row={**case()["source_row"], "original_name": "Unmarked item"})
    item["case_origin"] = "ordinary_source"
    with pytest.raises(ValueError, match="case_origin must be synthetic_control"):
        brand.prepare_packet(packet(item))


def test_ordinary_case_fingerprint_is_unchanged_without_origin():
    item = case(source_row={**case()["source_row"], "original_name": "Unmarked item"})
    assert "case_origin" not in item
    assert brand.facts_sha256(item) == "6d99241697f8f70ef018a8f16cd12a20155bd9aabc906b636440ea72c6cdf89f"
