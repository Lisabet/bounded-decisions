"""Legacy API retained for staged migration."""
from .client import DecisionClient, DecisionClientError, DecisionResult

__all__ = ["DecisionClient", "DecisionClientError", "DecisionResult"]
