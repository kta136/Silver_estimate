"""Compact deletion confirmation shared by entry and history."""

from .message_dialogs import confirm_destructive


def confirm_estimate_deletion(parent, voucher_no: str, summary: str = "") -> bool:
    """Confirm deleting one estimate.

    ``summary`` identifies the estimate beyond its number (date, total, note)
    so the user can see they picked the right one.
    """
    detail = "This estimate will be permanently deleted. This action cannot be undone."
    if summary:
        detail = f"{summary}\n\n{detail}"
    return confirm_destructive(
        parent,
        title="Delete Estimate",
        heading=f"Delete estimate {voucher_no}?",
        detail=detail,
        action_label="Delete Estimate",
    )
