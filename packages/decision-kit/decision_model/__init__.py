"""Compatibility imports for applications using the former decision_model API."""
from decision_kit.legacy.client import DecisionClient, DecisionClientError, DecisionResult

__all__ = ["DecisionClient", "DecisionClientError", "DecisionResult"]
