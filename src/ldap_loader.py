"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for loading FreeIPA configuration
from a remote LDAP server.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import dns.resolver
import ldap
import ldap.sasl

from core import FreeIPAManagerCore
from errors import AuthError, ManagerError
from utils import ENTITY_CLASSES


class LdapLoader(FreeIPAManagerCore):
    """
    Responsible for loading configuration YAML files from LDAP server.
    :param str domain: domain of the FreeIPA server ((prod|int|dev)gdc.com)
    """
    def __init__(self, domain):
        super(LdapLoader, self).__init__()
        self.domain = domain
        self._connect()

    def _connect(self):
        self.connected = False
        if self.domain == 'localhost':
            records = ['localhost']
        else:
            records = self._resolve_ldap_srv('_ldap._tcp.%s' % self.domain)
        if not records:
            raise ManagerError('No FreeIPA servers available')
        while not self.connected and records:
            server = 'ldap://%s' % records.pop(0)
            try:
                self._init_connection(server)
            except ldap.LDAPError as e:
                self.lg.warning(
                    'Error connecting to %s, trying next one: %s', server, e)
        if not self.connected:
            raise ManagerError('Unable to connect to any FreeIPA server')

    def _init_connection(self, server):
        """
        Initialize a connection to LDAP server & setup Kerberos authentication.
        :param str server: LDAP server to connect to
        """
        self.lg.info('Connecting to LDAP server %s', server)
        self.lg.debug('Initializing LDAP connection')
        self.server = ldap.initialize(server)
        self.server.set_option(ldap.OPT_NETWORK_TIMEOUT, 3)
        self.lg.debug('Enabling Kerberos (GSSAPI) authentication')
        try:
            self.server.sasl_interactive_bind_s('', ldap.sasl.gssapi())
        except ldap.LDAPError as e:
            raise AuthError('Error authenticating via Kerberos: %s' % e)
        self.connected = True
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
        result = [i.target.to_text() for i in answer.response.answer[0]]
        self.lg.debug(
            'FreeIPA SRV query resolved to records: [%s]', ', '.join(result))
        return result


class LdapDownloader(LdapLoader):
    def load(self):
        """
        Load entities of selected types from LDAP server at given address
        and parse them into FreeIPA entity object representations.
        :param list(str) filters: list of entity types to load
        """
        self.entities = dict()
        for entity_class in sorted(ENTITY_CLASSES):
            self.lg.debug('Searching for %s', entity_class.entity_name)
            self.entities[entity_class.entity_name] = []
            attrlist = entity_class.ldap_attrlist
            search_base = entity_class.construct_dn(self.domain)
            data = self.server.search_s(
                search_base, ldap.SCOPE_SUBTREE, entity_class.ldap_filter,
                self._map_attrlist(attrlist, entity_class))
            for item in data:
                dn, attrs = item
                self.entities[entity_class.entity_name].append(
                    entity_class(dn, attrs, self.domain))
            self.lg.debug(
                'Found %s: %s', entity_class.entity_name,
                self.entities[entity_class.entity_name])
            self.lg.info(
                'Parsed %d %s', len(self.entities[entity_class.entity_name]),
                entity_class.entity_name)

    def _map_attrlist(self, attrs, entity_class):
        """
        Map configuration attribute names to their LDAP counterparts.
        :param list attrs: list of attributes to map
        :param FreeIPAEntity entity_class: entity class reference
        :returns: attribute list translated to LDAP format
        :rtype: list
        """
        mapdict = entity_class.key_mapping
        return [mapdict.get(key, key) for key in attrs]
