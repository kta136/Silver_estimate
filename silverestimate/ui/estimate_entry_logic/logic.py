from __future__ import annotations

from .base import _EstimateBaseMixin
from .dialogs import _EstimateDialogsMixin
from .persistence import _EstimatePersistenceMixin
from .table import _EstimateTableMixin


class EstimateLogic(
    _EstimateDialogsMixin,
    _EstimatePersistenceMixin,
    _EstimateTableMixin,
    _EstimateBaseMixin,
):
    """Composite mixin that retains the original EstimateLogic API."""

    def __init__(self) -> None:
        _EstimateBaseMixin.__init__(self)
