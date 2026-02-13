from __future__ import annotations

from .constants import *  # noqa: F401,F403

__all__ = ["EstimateLogic"] + [
    name for name in globals().keys() if name.startswith("COL_")
]


def __getattr__(name: str):
    if name == "EstimateLogic":
        from .logic import EstimateLogic

        return EstimateLogic
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
