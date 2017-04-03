"""
GoodData FreeIPA tooling
Configuration parsing tool

Object representations of the entities configured in FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from core import FreeIPAManagerCore


class FreeIPAEntity(FreeIPAManagerCore):
    """General FreeIPA entity (user, group etc.) representation."""
    def __init__(self, name, data):
        """
        :param str name: entity name (user login, group name etc.)
        :param dict data: dictionary of entity configuration values
        """
        super(FreeIPAEntity, self).__init__()
        self.name = name
        self.data = data


class FreeIPAUser(FreeIPAEntity):
    """Representation of a FreeIPA user entity."""
    def __init__(self, login, data):
        """
        :param str login: user login (user key in the config)
        :param dict data: dictionary of user values (parsed from the config)
        """
        super(FreeIPAUser, self).__init__(login, data)

    def __repr__(self):
        return '<FreeIPAUser %s>' % self.name
