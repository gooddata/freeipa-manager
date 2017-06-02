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
entities = __import__('entities')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')


class TestLdapDownloader(object):
    def setup_method(self, method):
        with mock.patch('ldap_loader.LdapDownloader._connect'):
            self.loader = tool.LdapDownloader('localhost')
        self.loader.entities = dict()
        self.loader.server = mock.Mock()
        self.loader.server.search_s = self._search_s

    @log_capture('LdapDownloader', level=logging.DEBUG)
    def test_init_connection_localhost(self, captured_log):
        with mock.patch('ldap_loader.ldap.initialize') as ldap_init:
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
