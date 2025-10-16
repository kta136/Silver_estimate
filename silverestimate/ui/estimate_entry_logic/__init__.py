from __future__ import annotations

from .base import _EstimateBaseMixin
from .dialogs import _EstimateDialogsMixin
from .persistence import _EstimatePersistenceMixin
from .table import _EstimateTableMixin
from .constants import *  # noqa: F401,F403


class EstimateLogic(
    _EstimateDialogsMixin,
    _EstimatePersistenceMixin,
    _EstimateTableMixin,
    _EstimateBaseMixin,
):
    """Composite mixin that retains the original EstimateLogic API."""

    def __init__(self) -> None:
        _EstimateBaseMixin.__init__(self)


__all__ = [
    "EstimateLogic",
] + [name for name in globals().keys() if name.startswith("COL_")]
