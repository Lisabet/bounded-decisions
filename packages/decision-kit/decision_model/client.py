"""Compatibility module forwarding to the packaged legacy facade."""
from decision_kit.legacy.client import (DecisionClient, DecisionClientError,
                                        DecisionResult, ENDPOINT, MODEL,
                                        DEFAULT_PRICE_RUB_PER_MILLION)

__all__ = ["DecisionClient", "DecisionClientError", "DecisionResult", "ENDPOINT", "MODEL",
           "DEFAULT_PRICE_RUB_PER_MILLION"]
