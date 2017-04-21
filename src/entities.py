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
    def __repr__(self):
        return '<FreeIPAUser %s>' % self.name


class FreeIPAUserGroup(FreeIPAEntity):
    """Representation of a FreeIPA user group entity."""
    def __repr__(self):
        return '<FreeIPAUserGroup %s>' % self.name
