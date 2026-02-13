"""Factory namespace for UI adapters used by EstimateEntryWidget."""

__all__ = ["EstimateTableAdapter"]


def __getattr__(name: str):
    if name == "EstimateTableAdapter":
        from .estimate_table_adapter import EstimateTableAdapter

        return EstimateTableAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
