"""Public exports only; imports do not contact services or create runtime files."""

from .adapter import HANDLERS
from .definition import DEFINITION

__all__ = ["DEFINITION", "HANDLERS"]
