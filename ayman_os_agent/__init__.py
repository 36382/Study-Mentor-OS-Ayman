"""Ayman OS Agent package."""

__all__ = ["OSAgent"]

__version__ = "0.3.0"


def __getattr__(name: str):
    if name == "OSAgent":
        from .agent import OSAgent

        return OSAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
