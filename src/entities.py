"""
GoodData FreeIPA tooling
Configuration parsing tool

Object representations of the entities configured in FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from abc import ABCMeta, abstractmethod

import utils
from core import FreeIPAManagerCore


class FreeIPAEntity(FreeIPAManagerCore):
    """
    General FreeIPA entity (user, group etc.) representation.
    Can only be used via subclasses, not directly.
    """
    __metaclass__ = ABCMeta

    def __init__(self, name, data):
        """
        :param str name: entity name (user login, group name etc.)
        :param dict data: dictionary of entity configuration values
        """
        super(FreeIPAEntity, self).__init__()
        self._parse_dn(name)
        self.data = data

    def _parse_dn(self, name):
        """
        Determine if the name parameter is a simple entity name
        or a full LDAP DN, and parse it accordingly.
        """
        nametype, cn, base = utils.ldap_parse_dn(name)
        if cn:  # name successfully parsed as full LDAP DN
            self.name = cn
            self.dn = name
        else:  # name is a simple entity name; construct DN
            self.name = name
            self.dn = self._construct_dn(name)

    @abstractmethod
    def _construct_dn(self, name):
        """
        Construct entity's LDAP DN from its name.
        This is abstract because the DN is entity type-specific.
        :param str name: entity name (e.g., firstname.lastname for users,
                         sample-group for a group)
        :returns: full LDAP entity DN (examples:
                  uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,gdc=com
                  cn=sample-group,cn=groups,cn=accounts,dc=intgdc,dc=com)
        """
        pass

    def __repr__(self):
        return self.dn


class FreeIPAGroup(FreeIPAEntity):
    """Abstract representation a FreeIPA group entity (host/user group)."""
    meta_group_suffix = ''

    @property
    def is_meta(self):
        """
        Check whether the group is a meta-group.
        A meta-group can only contain other groups, not hosts/users.
        If meta_group_suffix is an empty string, this is not enforced.
        """
        return self.meta_suffix and not self.name.endswith(self.meta_suffix)

    @property
    def meta_suffix(self):
        return self.meta_group_suffix


class FreeIPAHostGroup(FreeIPAGroup):
    """Representation of a FreeIPA host group entity."""
    meta_group_suffix = '-hosts'

    def _construct_dn(self, name):
        return utils.ldap_get_dn('hostgroups', name)


class FreeIPAUserGroup(FreeIPAGroup):
    """Representation of a FreeIPA user group entity."""
    meta_group_suffix = '-users'

    def _construct_dn(self, name):
        return utils.ldap_get_dn('usergroups', name)


class FreeIPAUser(FreeIPAEntity):
    """Representation of a FreeIPA user entity."""

    def _construct_dn(self, name):
        return utils.ldap_get_dn('users', name)

    def _adjust_data(self):
        """
        Adjust the data format to make it consistent
        with config repository data model.
        """
        manager = self.data.get('manager')
        if manager:  # manager is a full DN from LDAP; parse manager name
            _, manager_name, _ = utils.ldap_parse_dn(manager)
            if manager_name:
                self.data['manager'] = manager_name
