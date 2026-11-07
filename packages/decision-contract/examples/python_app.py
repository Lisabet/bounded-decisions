"""Run from any directory after installing decision-kit; uses only synthetic observations."""
from decision_kit.universal import execute_task

TASK = {"task_version": "bounded-task/1", "task_id": "synthetic-support-1", "rules_version": "support/1", "state": {"message": "Move delivery to Friday"}, "questions": {"route": {"type": "choice", "instructions": "Choose the matching department.", "criteria": {"delivery": "Delivery scheduling", "payment": "Payment and refunds", "review": "Human review"}, "abstain_choice": "review"}}}

class OfflineAdapter:
    def decide(self, task, selection, context):
        return {"contract_version": "bounded-decisions/1", "provider": selection["provider"], "requested_model": selection["model"], "returned_model": selection["model"], "status": "ok", "answers": {"route": {"type": "choice", "choice": "delivery"}}, "usage": None, "billing": {"amount": 0, "currency": "USD", "source": "Synthetic observation"}, "billing_state": "observed", "estimate": None, "receipt": {"id": context.get("receiptId"), "reused": False}, "uncertain": False, "error": None}

for provider in ("fixture-a", "fixture-b"):
    outcome = execute_task(TASK, {"provider": provider, "model": "synthetic/model"}, {provider: OfflineAdapter()}, {"expected_choices": {"route": "delivery"}}, {"receiptId": "offline-attempt"})
    assert outcome["evaluation"]["status"] == "accepted"
    assert outcome["evaluation"]["quality"]["matched"] is True
    print(provider, outcome["record"]["answers"]["route"]["choice"], outcome["evaluation"]["status"])
