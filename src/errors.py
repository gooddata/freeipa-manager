class ManagerError(Exception):
    """General error, used mainly for derivation of other exceptions."""
    pass


class ConfigError(ManagerError):
    """Error raised in case of encountering an invalid configuration."""
    pass
