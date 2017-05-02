import os
import sys


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('utils')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')


class TestUtils(object):
    def test_ldap_parse_dn(self):
        dn = 'cn=test-group,cn=hostgroups,cn=accounts,dc=intgdc,dc=com'
        nametype, name, base = tool.ldap_parse_dn(dn)
        assert nametype == 'cn'
        assert name == 'test-group'
        assert base == 'cn=hostgroups,cn=accounts,dc=intgdc,dc=com'

    def test_ldap_parse_dn_empty(self):
        nametype, name, base = tool.ldap_parse_dn('test-group')
        assert nametype is None
        assert name is None
        assert base is None

    def test_ldap_get_dn_type(self):
        assert tool.ldap_get_dn(
            'hostgroups') == 'cn=hostgroups,cn=accounts,dc=intgdc,dc=com'
        assert tool.ldap_get_dn(
            'usergroups') == 'cn=groups,cn=accounts,dc=intgdc,dc=com'
        assert tool.ldap_get_dn(
            'users') == 'cn=users,cn=accounts,dc=intgdc,dc=com'

    def test_ldap_get_dn(self):
        assert tool.ldap_get_dn('hostgroups', 'group-one') == (
            'cn=group-one,cn=hostgroups,cn=accounts,dc=intgdc,dc=com')
        assert tool.ldap_get_dn('usergroups', 'group-users') == (
            'cn=group-users,cn=groups,cn=accounts,dc=intgdc,dc=com')
        assert tool.ldap_get_dn('users', 'user.one') == (
            'uid=user.one,cn=users,cn=accounts,dc=intgdc,dc=com')
