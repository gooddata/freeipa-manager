"""
GoodData FreeIPA tooling
Configuration parsing tool

Validation schemas for FreeIPA entities configuration.

NOTE: 'noldap_'-prefixed attributes are only used internally
      by the script and are not propagated to FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from voluptuous import Required

schema_users = {
    str: {
        Required('emailAddress'): str,
        Required('firstName'): str,
        Required('lastName'): str,
        Required('initials'): str,
        Required('organizationUnit'): str,
        Required('manager'): str,
        'githubLogin': str,
        'title': str,
        'memberOf': [str]
    }
}

schema_usergroups = {
    str: {
        Required('description'): str,
        'memberOf': [str]
    }
}
