class EngineError(Exception):
    """An engine operation could not be completed."""


class PlanError(EngineError):
    """A plan is invalid or no longer matches the filesystem."""
