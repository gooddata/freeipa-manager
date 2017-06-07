import logging
import mock
import os
import pytest
import sys
from testfixtures import LogCapture


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('ldap_loader')
entities = __import__('entities')


class TestLdapDownloader(object):
    def setup_method(self, method):
        with mock.patch('ldap_loader.LdapDownloader._connect'):
            self.loader = tool.LdapDownloader('localhost')
        self.loader.entities = dict()
        self.loader.server = mock.Mock()
        self.loader.server.search_s = self._search_s

    def mock_srv_query(self, *args):
        rrset = []
        for i in range(1, 4):
            record = mock.Mock()
            record.target.to_text.return_value = 'ipa0%d' % i
            rrset.append(record)
        response = mock.Mock(answer=[rrset])
        answer = mock.Mock(response=response)
        return answer

    def test_resolve_ldap_srv(self):
        with mock.patch('ldap_loader.dns.resolver.query', self.mock_srv_query):
            assert self.loader._resolve_ldap_srv('ldap_query') == [
                'ipa01', 'ipa02', 'ipa03']

    def test_resolve_ldap_srv_error(self):
        with mock.patch('ldap_loader.dns.resolver.query') as mock_query:
            mock_query.side_effect = tool.dns.exception.DNSException(
                'No SRV record available')
            with pytest.raises(tool.ManagerError) as exc:
                self.loader._resolve_ldap_srv('ldap_query')
            assert exc.value[0] == (
                'Cannot resolve FreeIPA server: No SRV record available')

    def test_init_connection_localhost(self):
        with mock.patch('ldap_loader.ldap.initialize') as ldap_init:
            with LogCapture(
                    'LdapDownloader', level=logging.DEBUG) as captured_log:
                self.loader._connect()
            ldap_init.assert_called_with('ldap://localhost')
            captured_log.check(
                ('LdapDownloader', 'INFO',
                 'Connecting to LDAP server ldap://localhost'),
                ('LdapDownloader', 'DEBUG', 'Initializing LDAP connection'),
                ('LdapDownloader', 'DEBUG',
                 'Enabling Kerberos (GSSAPI) authentication'),
                ('LdapDownloader', 'INFO', 'LDAP connection initialized'))

    def test_init_connection_remote(self):
        with mock.patch('ldap_loader.LdapDownloader._resolve_ldap_srv') as srv:
            srv.return_value = ['freeipa.intgdc.com']
            with mock.patch('ldap_loader.ldap.initialize') as ldap_init:
                tool.LdapDownloader('intgdc.com')
                ldap_init.assert_called_with('ldap://freeipa.intgdc.com')

    def test_init_connection_gssapi_error(self):
        mock_server = mock.Mock()
        mock_server.sasl_interactive_bind_s.side_effect = tool.ldap.LDAPError(
            'Credentials cache not found')
        with mock.patch('ldap_loader.ldap.initialize') as ldap_init:
            ldap_init.return_value = mock_server
            with pytest.raises(tool.AuthError) as exc:
                self.loader._init_connection('localhost')
            assert exc.value[0] == (
                'Error authenticating via Kerberos: '
                'Credentials cache not found')

    @mock.patch('ldap_loader.LdapDownloader._resolve_ldap_srv')
    def test_connect_noservers(self, mock_srv):
        mock_srv.return_value = []
        self.loader.domain = 'freeipa.server'
        with pytest.raises(tool.ManagerError) as exc:
            self.loader._connect()
        assert exc.value[0] == 'No FreeIPA servers available'

    @mock.patch('ldap_loader.LdapDownloader._resolve_ldap_srv')
    def test_connect_unavailable_all(self, mock_srv):
        mock_srv.return_value = ['server1', 'server2']
        self.loader.domain = 'freeipa.server'
        with mock.patch('ldap_loader.LdapDownloader._init_connection') as init:
            init.side_effect = tool.ldap.LDAPError('Timeout')
            with LogCapture() as captured_warnings:
                with pytest.raises(tool.ManagerError) as exc:
                    self.loader._connect()
            assert exc.value[0] == 'Unable to connect to any FreeIPA server'
            captured_warnings.check(
                ('LdapDownloader', 'WARNING',
                 ('Error connecting to ldap://server1, '
                  'trying next one: Timeout')),
                ('LdapDownloader', 'WARNING',
                 ('Error connecting to ldap://server2, '
                  'trying next one: Timeout')))
            assert not self.loader.connected

    @mock.patch('ldap_loader.LdapDownloader._resolve_ldap_srv')
    def test_connect_unavailable_first(self, mock_srv):
        mock_srv.return_value = ['server1', 'server2']
        self.loader.domain = 'freeipa.server'
        with mock.patch(
                'ldap_loader.LdapDownloader._init_connection', self.mock_init):
            with LogCapture() as captured_warnings:
                self.loader._connect()
            captured_warnings.check(
                ('LdapDownloader', 'WARNING',
                 ('Error connecting to ldap://server1, '
                  'trying next one: Timeout')))
            assert self.loader.connected

    def mock_init(self, server):
        if server == 'ldap://server1':
            raise tool.ldap.LDAPError('Timeout')
        self.loader.connected = True

    def test_load(self):
        self.loader.load()
        assert sorted(self.loader.entities) == [
            'HBAC rules', 'hostgroups', 'sudo rules',
            'usergroups', 'users']
        hbac_rules = self.loader.entities['HBAC rules']
        assert len(hbac_rules) == 2
        assert sorted(g.name for g in hbac_rules) == ['rule_one', 'rule_two']
        hostgroups = self.loader.entities['hostgroups']
        assert len(hostgroups) == 2
        assert sorted(g.name for g in hostgroups) == [
            'other-group', 'test-group']
        usergroups = self.loader.entities['usergroups']
        assert len(usergroups) == 2
        assert sorted(g.name for g in usergroups) == [
            'other-users', 'test-users']
        users = self.loader.entities['users']
        assert len(users) == 1
        assert sorted(u.name for u in users) == ['firstname.lastname']

    def _search_s(self, base, *args):
        if base == 'cn=hostgroups,cn=accounts,dc=localhost':
            return self._sample_hostgroups()
        elif base == 'cn=groups,cn=accounts,dc=localhost':
            return self._sample_usergroups()
        elif base == 'cn=users,cn=accounts,dc=localhost':
            return self._sample_users()
        elif base == 'cn=hbac,dc=localhost':
            return self._sample_hbac_rules()
        elif base == 'cn=sudo,dc=localhost':
            return self._sample_sudo_rules()

    def _sample_hostgroups(self):
        return [
            ('cn=test-group,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Test group']}),
            ('cn=other-group,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Another group']})]

    def _sample_usergroups(self):
        return [
            ('cn=test-users,cn=groups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Test user group']}),
            ('cn=other-users,cn=groups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Another group of users']})]

    def _sample_users(self):
        return [
            ('uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,dc=com',
             {'sn': ['Lastname'], 'givenName': ['Firstname']})]

    def _sample_hbac_rules(self):
        return [
            ('cn=rule_one,cn=hbac,dc=intgdc,dc=com',
             {'description': ['HBAC rule one'], 'cn': ['rule_one']}),
            ('cn=rule_two,cn=hbac,dc=intgdc,dc=com',
             {'description': ['HBAC rule two'], 'cn': ['rule_two']})]

    def _sample_sudo_rules(self):
        return [(
            'cn=rule_one,cn=sudo,dc=intgdc,dc=com',
            {
                'description': ['HBAC rule one'],
                'cn': ['rule_one'],
                'ipaSudoOpt': ['!authenticate'],
                'ipaSudoRunAsGroupCategory': ['all'],
                'cmdCategory': ['all']
            })]
