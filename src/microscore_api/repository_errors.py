"""Repository-level errors shared by SQLite and PostgreSQL backends."""


class DuplicateUserError(ValueError):
    """Raised when a repository already contains the requested user."""


class DuplicateOrganizationError(ValueError):
    """Raised when a repository already contains the requested organization."""


class DuplicateModelVersionError(ValueError):
    """Raised when a repository already contains the requested model version."""


class InvalidApplicationTransitionError(ValueError):
    """Raised when an application lifecycle transition is not allowed."""


class UnsupportedStorageBackendError(ValueError):
    """Raised when configuration requests an unsupported repository backend."""
