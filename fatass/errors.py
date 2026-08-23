class TopologyValidationError(Exception):
    """Raised when nodes/ doesn't correspond to fatass/topology/."""


class FreeError(Exception):
    """Raised when the underlying `claude` CLI call fails."""


class FreeCoercionError(Exception):
    """Raised when an agent's returned output doesn't match `returns`."""
