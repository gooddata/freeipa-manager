class ManagerError(Exception):
    """General error, used mainly for derivation of other exceptions."""


class ConfigError(ManagerError):
    """Error raised in case of encountering an invalid configuration."""


class AuthError(ManagerError):
    """Error raised in case of LDAP Kerberos authentication error."""
