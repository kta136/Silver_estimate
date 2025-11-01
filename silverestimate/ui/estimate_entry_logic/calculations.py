"""Calculation helper functions for estimate entry UI.

This module re-exports the core calculation functions from the services layer
and provides additional UI-specific calculation helpers.
"""

from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_totals,
    compute_wage_amount,
)

__all__ = [
    "compute_net_weight",
    "compute_fine_weight",
    "compute_wage_amount",
    "compute_totals",
    "calculate_net_weight_from_row",
    "calculate_fine_weight_from_row",
    "calculate_wage_from_row",
]


def calculate_net_weight_from_row(gross: float, poly: float) -> float:
    """Calculate net weight from gross and poly values.

    This is a convenience wrapper around compute_net_weight for UI use.

    Args:
        gross: The gross weight
        poly: The poly weight

    Returns:
        The calculated net weight
    """
    return compute_net_weight(gross, poly)


def calculate_fine_weight_from_row(net_weight: float, purity: float) -> float:
    """Calculate fine weight from net weight and purity.

    This is a convenience wrapper around compute_fine_weight for UI use.

    Args:
        net_weight: The net weight
        purity: The purity percentage

    Returns:
        The calculated fine weight
    """
    return compute_fine_weight(net_weight, purity)


def calculate_wage_from_row(
    wage_basis: str,
    net_weight: float,
    wage_rate: float,
    pieces: int,
) -> float:
    """Calculate wage amount from row data.

    This is a convenience wrapper around compute_wage_amount for UI use.

    Args:
        wage_basis: The wage calculation basis ("WT" for weight, "PC" for pieces)
        net_weight: The net weight
        wage_rate: The wage rate
        pieces: The number of pieces

    Returns:
        The calculated wage amount
    """
    return compute_wage_amount(
        wage_basis=wage_basis,
        net_weight=net_weight,
        wage_rate=wage_rate,
        pieces=pieces,
    )
