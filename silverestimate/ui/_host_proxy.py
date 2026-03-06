"""Helpers for controller objects bound to a widget/dialog host."""

from __future__ import annotations

from typing import Any


class HostProxy:
    """Forward most attribute access and state mutation to a bound host object."""

    def __init__(self, host: Any) -> None:
        object.__setattr__(self, "_host", host)

    @property
    def host(self) -> Any:
        return object.__getattribute__(self, "_host")

    def __getattribute__(self, name: str) -> Any:
        if name in {
            "_host",
            "host",
            "__class__",
            "__dict__",
            "__setattr__",
            "__getattr__",
            "__getattribute__",
        }:
            return object.__getattribute__(self, name)

        host = object.__getattribute__(self, "_host")
        host_dict = getattr(host, "__dict__", {})
        if name in host_dict:
            return host_dict[name]
        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.host, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_host":
            object.__setattr__(self, name, value)
            return
        setattr(self.host, name, value)
