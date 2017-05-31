"""
GoodData FreeIPA tooling
Configuration parsing tool

Object representations of the entities configured in FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import re
import voluptuous
from abc import ABCMeta, abstractproperty

import schemas
from core import FreeIPAManagerCore
from errors import ConfigError


class FreeIPAEntity(FreeIPAManagerCore):
    """
    General FreeIPA entity (user, group etc.) representation.
    Can only be used via subclasses, not directly.
    """
    __metaclass__ = ABCMeta
    entity_id_type = 'cn'  # entity name identificator inside LDAP DN
    key_mapping = {}  # attribute name mapping between local config and LDAP

    def __init__(self, name, data, domain):
        """
        :param str name: entity name (user login, group name etc.)
        :param dict data: dictionary of entity configuration values
        :param str domain: LDAP server domain
        """
        super(FreeIPAEntity, self).__init__()
        self.domain = domain
        self._parse_data(name, data)

    def _parse_data(self, name, data):
        """
        Determine if the entity was loaded from FreeIPA or from local config,
        and set the name and data attributes accordingly.
        :param str name: entity name (may be a common name or a DN)
        :param dict data: dictionary of entity configuration attributes
        """
        _, entity_id, base = self._parse_dn(name)
        if entity_id:  # name parsed as full DN = entity loaded from FreeIPA
            self.data = data
            # there is just one cn/uid item, so just take the first list item
            self.name = self.data.get(self.entity_id_type, [entity_id])[0]
            self.dn = name
        else:  # name is a simple entity name = entity loaded from local config
            try:
                self.validation_schema(data)
            except voluptuous.Error as e:
                raise ConfigError('Error validating %s: %s' % (name, e))
            self.data = self._convert(data)
            self.name = name
            self.dn = self.construct_dn(self.domain, name)

    @classmethod
    def construct_dn(cls, domain, name=''):
        """
        Construct entity's LDAP DN from its name.
        :param str name: entity name (e.g., firstname.lastname for users,
                         sample-group for a group)
        :param str domain: LDAP server domain (for DN construction)
        :returns: full LDAP entity DN (examples:
                  uid=firstname.lastname,cn=users,cn=accounts,dc=localhost
                  cn=sample-group,cn=groups,cn=accounts,dc=localhost)
        """
        domain_dn = ','.join('dc=%s' % i for i in domain.split('.'))
        base_dn = '%s,%s' % (cls.type_dn, domain_dn)
        if not name:
            return base_dn
        entity_prefix = '%s=%s,' % (cls.entity_id_type, name)
        return '%s%s' % (entity_prefix, base_dn)

    def _parse_dn(self, dn):
        """
        Parse DN into ID name, entity name and base DN.
        A sample DN looks like this:
            - uid=firstname.lastname,cn=users,cn=accounts,dc=localhost
            - cn=group-one,cn=groups,cn=accounts,dc=localhost
        :param str dn: entity DN to parse
        """
        match = re.match(r'(\w+)=([^,]+),(.*)', dn)
        if match:
            return match.groups()
        return (None, None, None)

    def _convert(self, data):
        """
        Convert entry from config format to LDAP format. This is needed
        because LDAP configuration storing has some specifics which would
        not be practical to copy in the local configuration (non-intuitive
        attribute names, each attribute as a list and so on).
        :param dict data: entity data parsed from configuration
        :returns: data transformed to LDAP entry-compatible format
        :rtype: dict
        """
        result = dict()
        for key, value in data.items():
            new_key = self.key_mapping.get(key, key)
            if new_key == 'memberOf':
                result[new_key] = self._map_memberof(value)
            else:
                result[new_key] = value if isinstance(value, list) else [value]
        return result

    def _map_memberof(self, membership_data):
        """
        Parse memberOf entry of configuration into an LDAP-compatible list.
        The memberOf dict we store locally has entries organized by type
        of the target entity (group, sudo/HBAC rules), while LDAP requires
        a list of DNs of entities that our entity is a member of.
        :param dict membership_data: memberOf dictionary parsed from config
        :returns: list of LDAP DN values
        :rtype: list
        """
        result = list()
        for entity_type in membership_data:
            entity_class = self._get_entity_class(entity_type)
            for target in membership_data[entity_type]:
                result.append(entity_class.construct_dn(self.domain, target))
        return result

    @staticmethod
    def _get_entity_class(name):
        class_dict = {
            'HBAC rules': FreeIPAHBACRule,
            'hostgroups': FreeIPAHostGroup,
            'sudorules': FreeIPASudoRule,
            'usergroups': FreeIPAUserGroup,
            'users': FreeIPAUser
        }
        return class_dict.get(name)

    @abstractproperty
    def type_dn(self):
        """
        Get base DN (FreeIPA distinguished name) for the entity of given type.
        :returns: entity type DN (e.g., cn=sudo or cn=users,cn=accounts)
        :rtype: str
        """

    @abstractproperty
    def config_folder(self):
        """
        Get configuration subfolder name for the given entity type.
        :returns: configuration subfolder name
        :rtype: str
        """

    @abstractproperty
    def ldap_attrlist(self):
        """
        Get list of attributes to synchronize with LDAP.
        The cn attribute is usually added to the list to ensure
        we receive the common name of the entity (because some entities
        don't use their common name as a part of the DN).
        :returns: list of LDAP attribute names to sync
        :rtype: list(str)
        """

    @abstractproperty
    def ldap_filter(self):
        """
        Get LDAP entity filter to use when performing ldapsearch.
        :returns: LDAP entity filter (e.g., '(uid=*)')
        :rtype: str
        """

    @abstractproperty
    def validation_schema(self):
        """
        :returns: entity validation schema
        :rtype: voluptuous.Schema
        """

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.dn == other.dn

    def __ne__(self, other):
        return not self == other


class FreeIPAGroup(FreeIPAEntity):
    """Abstract representation a FreeIPA group entity (host/user group)."""
    ldap_attrlist = ['description', 'memberOf']
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
    config_folder = 'hostgroups'
    entity_name = 'hostgroups'
    ldap_filter = '(objectclass=ipahostgroup)'
    meta_group_suffix = '-hosts'
    validation_schema = voluptuous.Schema(schemas.schema_hostgroups)
    type_dn = 'cn=hostgroups,cn=accounts'


class FreeIPAUserGroup(FreeIPAGroup):
    """Representation of a FreeIPA user group entity."""
    config_folder = 'usergroups'
    entity_name = 'usergroups'
    ldap_filter = (
        '(&(objectclass=ipausergroup)(!(objectclass=mepManagedEntry)))')
    meta_group_suffix = '-users'
    validation_schema = voluptuous.Schema(schemas.schema_usergroups)
    type_dn = 'cn=groups,cn=accounts'


class FreeIPAUser(FreeIPAEntity):
    """Representation of a FreeIPA user entity."""
    config_folder = 'users'
    entity_name = 'users'
    key_mapping = {
        'emailAddress': 'mail',
        'firstName': 'givenName',
        'lastName': 'sn',
        'organizationUnit': 'ou',
        'githubLogin': 'carLicense'
    }
    ldap_attrlist = [
        'emailAddress', 'firstName', 'lastName', 'initials',
        'organizationUnit', 'manager', 'githubLogin', 'title', 'memberOf']
    ldap_filter = '(objectclass=person)'
    entity_id_type = 'uid'
    validation_schema = voluptuous.Schema(schemas.schema_users)
    type_dn = 'cn=users,cn=accounts'

    def _convert(self, data):
        result = super(FreeIPAUser, self)._convert(data)
        if 'manager' in result:
            result['manager'] = [
                self.construct_dn(self.domain, m) for m in result['manager']]
        return result


class FreeIPAHBACRule(FreeIPAEntity):
    """Representation of a FreeIPA HBAC (host-based access control) rule."""
    config_folder = 'hbacrules'
    entity_name = 'HBAC rules'
    key_mapping = {'enabled': 'ipaEnabledFlag'}
    ldap_attrlist = ['cn', 'description', 'enabled']
    ldap_filter = '(objectclass=ipahbacrule)'
    validation_schema = voluptuous.Schema(schemas.schema_hbac)
    type_dn = 'cn=hbac'


class FreeIPASudoRule(FreeIPAEntity):
    """Representation of a FreeIPA sudo rule."""
    config_folder = 'sudorules'
    entity_name = 'sudo rules'
    key_mapping = {
        'enabled': 'ipaEnabledFlag',
        'options': 'ipaSudoOpt',
        'runAsGroupCategory': 'ipaSudoRunAsGroupCategory',
        'runAsUserCategory': 'ipaSudoRunAsUserCategory'
    }
    ldap_attrlist = [
        'cn', 'cmdCategory', 'description', 'enabled', 'options',
        'runAsGroupCategory', 'runAsUserCategory']
    ldap_filter = '(objectclass=ipasudorule)'
    validation_schema = voluptuous.Schema(schemas.schema_sudo)
    type_dn = 'cn=sudo'
