import mock
import os
import pytest
import sys


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('entities')

DOMAIN = 'intgdc.com'


class TestFreeIPAEntity(object):
    def test_create_entity(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAEntity('sample.entity', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAEntity "
            "with abstract methods config_folder, ldap_attrlist, ldap_filter, "
            "type_dn, validation_schema")

    def test_equality(self):
        user1 = tool.FreeIPAUser('user1', {}, DOMAIN)
        user2 = tool.FreeIPAUser('user1', {}, DOMAIN)
        assert user1 == user2
        user2.name = 'user2'  # check that equality is based on DN, not name
        assert user1 == user2

    def test_nonequality_different_type(self):
        group1 = tool.FreeIPAUserGroup('group', {}, DOMAIN)
        group2 = tool.FreeIPAHostGroup('group', {}, DOMAIN)
        assert group1 != group2

    def test_nonequality_same_type(self):
        rule1 = tool.FreeIPASudoRule('rule-one', {}, DOMAIN)
        rule2 = tool.FreeIPASudoRule('rule-two', {}, DOMAIN)
        assert rule1 != rule2
        rule2.name = 'rule-one'  # check that equality is based on DN, not name
        assert rule1 != rule2


class TestFreeIPAGroup(object):
    def test_create_group(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAGroup('sample-group', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAGroup "
            "with abstract methods config_folder, "
            "ldap_filter, type_dn, validation_schema")

    def test_create_usergroup_nonmeta(self):
        group = tool.FreeIPAUserGroup('sample-group-users', {}, DOMAIN)
        assert not group.is_meta

    def test_create_usergroup_meta(self):
        group = tool.FreeIPAUserGroup('sample-group', {}, DOMAIN)
        assert group.is_meta

    def test_create_usergroup_meta_not_enforced(self):
        with mock.patch('entities.FreeIPAUserGroup.meta_group_suffix', ''):
            group = tool.FreeIPAUserGroup('sample-group', {}, DOMAIN)
            assert not group.is_meta

    def test_create_hostgroup_nonmeta(self):
        group = tool.FreeIPAHostGroup('sample-group-hosts', {}, DOMAIN)
        assert not group.is_meta

    def test_create_hostgroup_meta_not_enforced(self):
        with mock.patch('entities.FreeIPAHostGroup.meta_group_suffix', ''):
            group = tool.FreeIPAHostGroup('sample-group', {}, DOMAIN)
            assert not group.is_meta

    def test_create_hostgroup_meta(self):
        group = tool.FreeIPAHostGroup('sample-group', {}, DOMAIN)
        assert group.is_meta


class TestFreeIPAHostGroup(object):
    def test_create_hostgroup_correct_local(self):
        data = {
            'description': 'Sample host group',
            'memberOf': {
                'hostgroups': ['group-one'],
                'HBAC rules': ['rule-one'],
                'sudorules': ['rule-one']}}
        group = tool.FreeIPAHostGroup(
            'group-one-hosts', data, DOMAIN)
        assert group.name == 'group-one-hosts'
        assert group.dn == (
            'cn=group-one-hosts,cn=hostgroups,cn=accounts,dc=intgdc,dc=com')
        assert sorted(group.data['memberOf']) == [
            'cn=group-one,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
            'cn=rule-one,cn=sudo,dc=intgdc,dc=com']
        assert group.data['description'] == ['Sample host group']

    def test_create_hostgroup_correct_ldap(self):
        data = {
            'memberOf': [
                'cn=group-one,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
                'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
                'cn=rule-one,cn=sudo,dc=intgdc,dc=com'],
            'description': ['Sample host group']}
        group = tool.FreeIPAHostGroup(
            'cn=group-one-hosts,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
            data, DOMAIN)
        assert group.name == 'group-one-hosts'
        assert group.dn == (
            'cn=group-one-hosts,cn=hostgroups,cn=accounts,dc=intgdc,dc=com')
        assert group.data == data

    def test_create_hostgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHostGroup(
                'group-one-hosts', {'extrakey': 'bad'}, DOMAIN)
        assert (
            ("Error validating group-one-hosts: "
             "extra keys not allowed @ data['extrakey']") in str(exc))

    def test_create_hostgroup_invalid_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHostGroup(
                'group-invalid-member',
                {'memberOf': {'usergroups': ['group-one']}}, DOMAIN)
        assert (
            ("Host group cannot be a member of usergroups "
             "for dictionary value @ data['memberOf']") in str(exc))


class TestFreeIPAUser(object):
    def setup_method(self, method):
        self.acc_dn = 'cn=accounts,dc=intgdc,dc=com'

    def test_create_user_correct_local(self):
        data = {
            'manager': 'sample.manager',
            'memberOf': {
                'usergroups': ['group-one-users'],
                'HBAC rules': ['rule-one'],
                'sudorules': ['rule-one']}}
        user = tool.FreeIPAUser('archibald.jenkins', data, DOMAIN)
        assert user.name == 'archibald.jenkins'
        assert user.dn == 'uid=archibald.jenkins,cn=users,%s' % self.acc_dn
        assert sorted(user.data['memberOf']) == [
            'cn=group-one-users,cn=groups,%s' % self.acc_dn,
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
            'cn=rule-one,cn=sudo,dc=intgdc,dc=com']
        assert user.data['manager'] == [
            'uid=sample.manager,cn=users,%s' % self.acc_dn]

    def test_create_user_correct_ldap(self):
        data = {
            'memberOf': [
                'cn=group-one-users,cn=groups,%s' % self.acc_dn,
                'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
                'cn=rule-one,cn=sudo,dc=intgdc,dc=com']}
        user = tool.FreeIPAUser(
            'uid=archibald.jenkins,cn=users,%s' % self.acc_dn, data, DOMAIN)
        assert user.name == 'archibald.jenkins'
        assert user.dn == 'uid=archibald.jenkins,cn=users,%s' % self.acc_dn
        assert user.data == data

    def test_create_user_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'archibald.jenkins', {'extrakey': 'bad'}, DOMAIN)
        assert (
            ("Error validating archibald.jenkins: "
             "extra keys not allowed @ data['extrakey']") in str(exc))

    def test_create_user_invalid_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'invalid.member',
                {'memberOf': {'hostgroups': ['group-one']}}, DOMAIN)
        assert (
            ("Error validating invalid.member: User cannot be a member "
             "of hostgroups for dictionary value @ data['memberOf']")
            in str(exc))

    def test_create_user_invalid_format_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'invalid.member',
                {'memberOf': {'usergroups': [['group-one']]}}, DOMAIN)
        assert (
            ("Error validating invalid.member: memberOf values must be "
             "string entity names for dictionary value @ data['memberOf']")
            in str(exc))

    def test_convert(self):
        data = {
            'firstName': 'Firstname',
            'lastName': 'Lastname',
            'initials': 'FL',
            'organizationUnit': 'TEST'
        }
        with mock.patch('entities.FreeIPAUser._parse_data'):
            user = tool.FreeIPAUser('some.name', data, DOMAIN)
        assert user._convert(data) == {
            'givenName': ['Firstname'],
            'sn': ['Lastname'],
            'initials': ['FL'],
            'ou': ['TEST']
        }

    def test_map_memberof(self):
        with mock.patch('entities.FreeIPAUser._parse_data'):
            user = tool.FreeIPAUser('some.name', {}, 'localhost')
        assert user._map_memberof({'usergroups': ['test-users']}) == [
            'cn=test-users,cn=groups,cn=accounts,dc=localhost']


class TestFreeIPAUserGroup(object):
    def test_create_usergroup_correct_local(self):
        data = {
            'description': 'Sample user group',
            'memberOf': {
                'usergroups': ['group-one'],
                'HBAC rules': ['rule-one'],
                'sudorules': ['rule-one']}}
        group = tool.FreeIPAUserGroup(
            'group-one-users', data, DOMAIN)
        assert group.name == 'group-one-users'
        assert group.dn == (
            'cn=group-one-users,cn=groups,cn=accounts,dc=intgdc,dc=com')
        assert sorted(group.data['memberOf']) == [
            'cn=group-one,cn=groups,cn=accounts,dc=intgdc,dc=com',
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
            'cn=rule-one,cn=sudo,dc=intgdc,dc=com']
        assert group.data['description'] == ['Sample user group']

    def test_create_usergroup_correct_ldap(self):
        data = {
            'memberOf': [
                'cn=group-one,cn=groups,cn=accounts,dc=intgdc,dc=com',
                'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
                'cn=rule-one,cn=sudo,dc=intgdc,dc=com'],
            'description': ['Sample user group']}
        dn = 'cn=group-one-users,cn=groups,cn=accounts,dc=intgdc,dc=com'
        group = tool.FreeIPAUserGroup(dn, data, DOMAIN)
        assert group.name == 'group-one-users'
        assert group.dn == dn
        assert group.data == data

    def test_create_usergroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUserGroup(
                'group-one-users', {'extrakey': 'bad'}, DOMAIN)
        assert (
            ("Error validating group-one-users: "
             "extra keys not allowed @ data['extrakey']") in str(exc))

    def test_create_usergroup_invalid_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUserGroup(
                'group-invalid-member',
                {'memberOf': {'hostgroups': ['group-one']}}, DOMAIN)
        assert (
            ("User group cannot be a member of hostgroups "
             "for dictionary value @ data['memberOf']") in str(exc))


class TestFreeIPAHBACRule(object):
    def test_create_hbac_rule_correct_local(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one',
            {'description': 'Sample HBAC rule', 'enabled': 'TRUE'}, DOMAIN)
        assert rule.name == 'rule-one'
        assert rule.dn == 'cn=rule-one,cn=hbac,dc=intgdc,dc=com'
        assert rule.data == {
            'description': ['Sample HBAC rule'],
            'ipaEnabledFlag': ['TRUE']}

    def test_create_hbac_rule_correct_ldap(self):
        dn = 'cn=rule-one,cn=hbac,dc=intgdc,dc=com'
        data = {
            'description': ['Sample HBAC rule'],
            'ipaEnabledFlag': ['TRUE']}
        rule = tool.FreeIPAHBACRule(dn, data, DOMAIN)
        assert rule.name == 'rule-one'
        assert rule.dn == 'cn=rule-one,cn=hbac,dc=intgdc,dc=com'
        assert rule.data == data

    def test_create_hbac_rule_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHBACRule('rule-one', {'extrakey': 'bad'}, DOMAIN)
        assert (
            ("Error validating rule-one: extra keys "
             "not allowed @ data['extrakey']") in str(exc))


class TestFreeIPASudoRule(object):
    def test_create_sudo_rule_correct_local(self):
        rule = tool.FreeIPASudoRule(
            'rule-one', {'description': 'Sample sudo rule'}, DOMAIN)
        assert rule.name == 'rule-one'
        assert rule.dn == 'cn=rule-one,cn=sudo,dc=intgdc,dc=com'
        assert rule.data == {'description': ['Sample sudo rule']}

    def test_create_sudo_rule_correct_ldap(self):
        dn = 'cn=rule-one,cn=sudo,dc=intgdc,dc=com'
        data = {'description': ['Sample sudo rule']}
        rule = tool.FreeIPASudoRule(dn, data, DOMAIN)
        assert rule.name == 'rule-one'
        assert rule.dn == dn
        assert rule.data == data

    def test_create_sudo_rule_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPASudoRule('rule-one', {'extrakey': 'bad'}, DOMAIN)
        assert (
            ("Error validating rule-one: "
             "extra keys not allowed @ data['extrakey']") in str(exc))
