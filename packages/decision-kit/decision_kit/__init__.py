"""Portable, provider-neutral bounded decision module."""
from .core import (ChoiceQuestion, DecisionError, DecisionRequest, DecisionResult,
                  ModelConfig, PricingInfo, ProviderRegistry, execute)
from .providers import PlusVibeAdapter
from .contract import CONTRACT_VERSION, to_record
from .universal import evaluate_record, execute_task, make_jev_adapter, validate_task

__version__ = "0.1.2rc3"
__all__ = ["ChoiceQuestion", "DecisionError", "DecisionRequest", "DecisionResult",
           "ModelConfig", "PricingInfo", "ProviderRegistry", "PlusVibeAdapter", "execute", "CONTRACT_VERSION", "to_record",
           "validate_task", "evaluate_record", "execute_task", "make_jev_adapter"]
