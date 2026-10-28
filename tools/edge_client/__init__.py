"""Reference BITORA Edge client primitives.

This package is a contract simulator/reference implementation. It is not a
certified hardware client.
"""

from .client import DatasetVerificationError, EdgeClient, EdgeClientError, EdgeScope

__all__ = ["DatasetVerificationError", "EdgeClient", "EdgeClientError", "EdgeScope"]
