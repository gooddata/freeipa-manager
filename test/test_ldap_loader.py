import logging
import mock
import os
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
for module in ['ldap', 'dns', 'dns.resolver']:
    sys.modules[module] = mock.Mock()
tool = __import__('ldap_loader')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')


class TestLdapDownloader(object):
    def setup_method(self, method):
        with mock.patch('ldap_loader.LdapDownloader._init_connection'):
            self.loader = tool.LdapDownloader('localhost')

    @log_capture('LdapDownloader', level=logging.DEBUG)
    def test_init_connection_localhost(self, captured_log):
        with mock.patch('ldap_loader.ldap.initialize') as ldap_init:
            self.loader._init_connection()
            ldap_init.assert_called_with('ldap://localhost')
        captured_log.check(
            ('LdapDownloader', 'INFO',
             'Connecting to LDAP server ldap://localhost'),
            ('LdapDownloader', 'DEBUG', 'Initializing LDAP connection'),
            ('LdapDownloader', 'DEBUG',
             'Binding GSSAPI to LDAP connection for Kerberos auth'),
            ('LdapDownloader', 'INFO', 'LDAP connection initialized'))

    def test_init_connection_remote(self):
        with mock.patch('ldap_loader.LdapDownloader._resolve_ldap_srv') as srv:
            srv.return_value = 'freeipa.intgdc.com'
            with mock.patch('ldap_loader.ldap.initialize') as ldap_init:
                tool.LdapDownloader('intgdc.com')
                ldap_init.assert_called_with('ldap://freeipa.intgdc.com')

    def test_search_entities_hostgroups(self):
        self.loader.entities = dict()
        self.loader.server = mock.MagicMock()
        self.loader.server.search_s.return_value = self._sample_hostgroups()
        self.loader._search_entities('hostgroups')
        hostgroups = self.loader.entities['hostgroups']
        assert len(hostgroups) == 2
        assert [i.dn for i in hostgroups] == [
            'cn=test-group,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
            'cn=other-group,cn=hostgroups,cn=accounts,dc=intgdc,dc=com']
        assert [i.name for i in hostgroups] == ['test-group', 'other-group']

    def test_search_entities_usergroups(self):
        self.loader.entities = dict()
        self.loader.server = mock.MagicMock()
        self.loader.server.search_s.return_value = self._sample_usergroups()
        self.loader._search_entities('usergroups')
        usergroups = self.loader.entities['usergroups']
        assert len(usergroups) == 2
        assert [i.dn for i in usergroups] == [
            'cn=test-users,cn=groups,cn=accounts,dc=intgdc,dc=com',
            'cn=other-users,cn=groups,cn=accounts,dc=intgdc,dc=com']
        assert [i.name for i in usergroups] == ['test-users', 'other-users']

    def test_search_entities_users(self):
        self.loader.entities = dict()
        self.loader.server = mock.MagicMock()
        self.loader.server.search_s.return_value = self._sample_users()
        self.loader._search_entities('users')
        users = self.loader.entities['users']
        assert len(users) == 1
        assert users[0].dn == (
            'uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,dc=com')
        assert users[0].name == 'firstname.lastname'
        assert users[0].data == {
            'sn': ['Lastname'], 'givenName': ['Firstname']}

    def test_load_entities(self):
        self.loader.server = mock.Mock()
        self.loader.server.search_s = self._search_s
        print self.loader.server.search_s
        self.loader.load_entities()
        assert sorted(self.loader.entities.keys()) == [
            'hostgroups', 'usergroups', 'users']
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
        if base == 'cn=hostgroups,cn=accounts,dc=intgdc,dc=com':
            return self._sample_hostgroups()
        elif base == 'cn=groups,cn=accounts,dc=intgdc,dc=com':
            return self._sample_usergroups()
        elif base == 'cn=users,cn=accounts,dc=intgdc,dc=com':
            return self._sample_users()

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
