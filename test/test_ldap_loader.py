import logging
import mock
import os
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
sys.modules['ldap'] = mock.Mock()
tool = __import__('ldap_loader')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')


class TestLdapDownloader(object):
    def setup_method(self, method):
        with mock.patch('ldap_loader.ldap.initialize'):
            self.loader = tool.LdapDownloader()

    @log_capture('LdapDownloader', level=logging.DEBUG)
    def test_init_connection(self, captured_log):
        with mock.patch('ldap_loader.ldap.initialize') as ldap_init:
            self.loader._init_connection()
            ldap_init.assert_called_with('ldap://localhost')
        captured_log.check(
            ('LdapDownloader', 'DEBUG',
             'Initializing LDAP connection to ldap://localhost'),
            ('LdapDownloader', 'DEBUG',
             'Binding GSSAPI to LDAP connection for Kerberos auth'),
            ('LdapDownloader', 'INFO', 'LDAP connection initialized'))

    # TODO test LDAP GSSAPI bind error raising

    def test_search_entities_hostgroups(self):
        self.loader.entities = dict()
        self.loader.server = mock.MagicMock()
        self.loader.server.search_s.return_value = [
            ('cn=test-group,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Test group']}),
            ('cn=other-group,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Another group']})]
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
        self.loader.server.search_s.return_value = [
            ('cn=test-users,cn=groups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Test user group']}),
            ('cn=other-users,cn=groups,cn=accounts,dc=intgdc,dc=com',
             {'description': ['Another group of users']})]
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
        self.loader.server.search_s.return_value = [
            ('uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,dc=com',
             {'sn': ['Lastname'], 'givenName': ['Firstname']})]
        self.loader._search_entities('users')
        users = self.loader.entities['users']
        assert len(users) == 1
        assert users[0].dn == (
            'uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,dc=com')
        assert users[0].name == 'firstname.lastname'
        assert users[0].data == {
            'sn': ['Lastname'], 'givenName': ['Firstname']}
