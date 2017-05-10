"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for loading FreeIPA configuration
from a remote LDAP server.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import dns.resolver
import ldap

import entities
import utils
from core import FreeIPAManagerCore
from errors import ManagerError


class LdapLoader(FreeIPAManagerCore):
    """
    Responsible for loading configuration YAML files from LDAP server.
    :param str domain: domain of the FreeIPA server ((prod|int|dev)gdc.com)
    """
    def __init__(self, domain):
        super(LdapLoader, self).__init__()
        self.addr = 'ldap://%s' % domain
        if domain != 'localhost':
            query = '_kerberos._tcp.%s' % domain
            self.addr = 'ldap://%s' % self._resolve_ldap_srv(query)
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
        self.lg.info('Connecting to LDAP server %s', self.addr)
        self.lg.debug('Initializing LDAP connection')
        self.server = ldap.initialize(self.addr)
        self.lg.debug('Binding GSSAPI to LDAP connection for Kerberos auth')
        try:
            self.server.sasl_interactive_bind_s('', ldap.sasl.gssapi())
        except ldap.LDAPError as e:
            raise ManagerError('Error authenticating via Kerberos: %s' % e)
        self.lg.info('LDAP connection initialized')

    def _resolve_ldap_srv(self, query):
        """
        Resolve the FreeIPA SRV query for the highest-priority LDAP server.
        :param str query: query to resolve
        :returns: domain with the highest priority in the SRV record
        :rtype: str
        """
        try:
            answer = dns.resolver.query(query, 'SRV')
        except dns.exception.DNSException as e:
            raise ManagerError('Cannot resolve FreeIPA server: %s' % e)
        result = answer.response.answer[0][0].target.to_text()
        self.lg.debug('FreeIPA SRV record resolved to %s', result)
        return result


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
