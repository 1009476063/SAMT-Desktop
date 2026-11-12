"""Lightweight package namespace.

Importing ``core.<module>`` must not construct the model stack: the consent
gate and first workbench paint run before any checkpoint work is allowed.
"""

__all__ = (
    "InferenceEngine",
    "PatientCase",
    "ScanResult",
    "discover_cases",
    "validate_case",
)


def __getattr__(name: str):
    if name in __all__:
        from . import engine
        return getattr(engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
