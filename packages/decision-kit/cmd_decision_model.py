"""Import-compatible forwarding shim for the namespaced compatibility API."""
from decision_kit.compat import DecisionClient, DecisionClientError, DecisionResult
from decision_kit.compat import encoded, prepare, read, run, save

__all__ = ["DecisionClient", "DecisionClientError", "DecisionResult", "encoded", "prepare", "read", "run", "save"]
