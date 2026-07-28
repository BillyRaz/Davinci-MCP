"""Domain exceptions returned to MCP clients as useful messages."""


class ResolveError(RuntimeError):
    """Base error for Resolve connection and operation failures."""


class ConnectionError(ResolveError):
    """Resolve is unavailable or scripting is not enabled."""


class NotFoundError(ResolveError):
    """A requested Resolve object could not be found."""


class ValidationError(ResolveError):
    """An input is invalid in the current Resolve context."""


class OperationError(ResolveError):
    """Resolve rejected an otherwise valid operation."""


class CapabilityError(ResolveError):
    """The official Resolve scripting API does not expose the operation."""
