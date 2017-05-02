"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for loading FreeIPA configuration
from a remote LDAP server.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import ldap

import entities
import utils
from core import FreeIPAManagerCore
from errors import ManagerError


class LdapLoader(FreeIPAManagerCore):
    """
    Responsible for loading configuration YAML files from LDAP server.
    """
    def __init__(self, addr='localhost'):
        """
        :param str addr: FreeIPA LDAP server address (without ldap://)
        """
        super(LdapLoader, self).__init__()
        self.addr = 'ldap://%s' % addr
        self._init_connection()
        self.entity_classes = {
            'hostgroups': entities.FreeIPAHostGroup,
            'users': entities.FreeIPAUser,
            'usergroups': entities.FreeIPAUserGroup
        }

    def _init_connection(self):
        """
        Initialize a connection to LDAP server & setup Kerberos authentication.
        """
        self.lg.debug('Initializing LDAP connection to %s', self.addr)
        self.server = ldap.initialize(self.addr)
        self.lg.debug('Binding GSSAPI to LDAP connection for Kerberos auth')
        try:
            self.server.sasl_interactive_bind_s('', ldap.sasl.gssapi())
        except ldap.LDAPError as e:
            msg = '%s%s' % (
                e[0].get('desc', ''),
                ' (%s)' % e[0].get('info') if 'info' in e[0] else '')
            raise ManagerError(
                'Error authenticating via Kerberos: %s' % msg if msg else e)
        self.lg.info('LDAP connection initialized')


class LdapDownloader(LdapLoader):
    def load_entities(self, filters=utils.ENTITY_TYPES):
        """
        Load entities of selected types from LDAP server at given address
        and parse them into FreeIPA entity object representations.
        :param list(str) filters: list of entity types to load
        """
        self.entities = dict()
        for conftype in sorted(filters):
            self._search_entities(conftype)
            self.lg.debug('Parsed %s: %s', conftype, self.entities[conftype])
            self.lg.info(
                'Parsed %d %s', len(self.entities[conftype]), conftype)

    def _search_entities(self, entity_type):
        """
        Search LDAP entities of the given entity type.
        :param str entity_type: entity type to search (users, usergroups etc.)
        """
        self.lg.debug('Searching for %s', entity_type)
        self.entities[entity_type] = []
        self.entity_class = self.entity_classes[entity_type]
        base = utils.ldap_get_dn(entity_type)
        attrlist = utils.ENTITY_ARGS[entity_type]
        data = self.server.search_s(
            base, ldap.SCOPE_SUBTREE, '(%s=*)' % utils.LDAP_ID[entity_type],
            self._map_attrlist(attrlist, entity_type))
        for item in data:
            dn, attrs = item
            if dn == base:  # there is a top-level entity we don't parse
                continue
            self.entities[entity_type].append(self.entity_class(dn, attrs))

    def _map_attrlist(self, attrs, conftype):
        """
        Map configuration attribute names to their LDAP counterparts.
        :param list attrs: list of attributes to map
        :param str conftype: config type (users, usergroups, hostgroups)
        :returns: attribute list translated to LDAP format
        :rtype: list
        """
        mapdict = utils.LDAP_CONF_MAPPING[conftype]
        return [mapdict.get(key) if mapdict.get(key) else key for key in attrs]
