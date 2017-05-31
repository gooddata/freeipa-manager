"""
GoodData FreeIPA tooling
Configuration parsing tool

Validation schemas for FreeIPA entities configuration.

NOTE: 'noldap_'-prefixed attributes are only used internally
      by the script and are not propagated to FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from voluptuous import Any, Invalid


def _schema_memberof(memberof, allowed, entity_name):
    """
    Validate that the membership values of an entity are correctly set.
    The memberOf key value must be a dictionary of entity types where each key
    stores a list of entity names (strings) of which the entity is a member.
    :param dict memberof: memberOf value from the entity configuration dict
    :param list(str) allowed: entity type names that entity can be a member of
    :param str entity_name: name of the entity type (e.g. user, usergroup)
                            (used for display in the error message)
    """
    result = dict()
    for key, value in memberof.iteritems():
        if key not in allowed:
            raise Invalid('%s cannot be a member of %s' % (entity_name, key))
        for target in value:
            if not isinstance(target, str):
                raise Invalid('memberOf values must be string entity names')
        result[key] = value
    return result


def _schema_memberof_users(value):
    """
    Interface between the `_schema_memberof` method and voluptuous
    validation module to provide validation of memberOf values in user config.
    """
    return _schema_memberof(
        value, ['HBAC rules', 'sudorules', 'usergroups'], 'User')


def _schema_memberof_usergroups(value):
    """
    Interface between the `_schema_memberof` method and voluptuous validation
    module to provide validation of memberOf values in usergroup config.
    """
    return _schema_memberof(
        value, ['HBAC rules', 'sudorules', 'usergroups'], 'User group')


def _schema_memberof_hostgroups(value):
    """
    Interface between the `_schema_memberof` method and voluptuous validation
    module to provide validation of memberOf values in hostgroup config.
    """
    return _schema_memberof(
        value, ['HBAC rules', 'hostgroups', 'sudorules'], 'Host group')


schema_users = {
    'emailAddress': str,
    'firstName': str,
    'lastName': str,
    'initials': str,
    'organizationUnit': str,
    'manager': str,
    'githubLogin': str,
    'title': str,
    'memberOf': _schema_memberof_users
}


schema_usergroups = {
    'description': str,
    'memberOf': _schema_memberof_usergroups
}


schema_hostgroups = {
    'description': str,
    'memberOf': _schema_memberof_hostgroups
}


schema_hbac = {
    'description': str,
    'enabled': Any('TRUE', 'FALSE')
}


schema_sudo = {
    'cmdCategory': str,
    'description': str,
    'enabled': Any('TRUE', 'FALSE'),
    'options': [str],
    'runAsGroupCategory': str,
    'runAsUserCategory': str
}
