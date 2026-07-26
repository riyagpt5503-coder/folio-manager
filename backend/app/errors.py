class DataFetchError(Exception):
    """Raised when historical price data cannot be retrieved or is unusable."""


class OptimizationError(Exception):
    """Raised when the portfolio optimizer fails to produce a solution."""
