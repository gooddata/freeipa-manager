import mock
import os
import pytest
import sys
import yaml


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('entities')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')
USER_CORRECT = os.path.join(CONFIG_CORRECT, 'users/archibald_jenkins.yaml')
USER_CORRECT_SEVERAL = os.path.join(CONFIG_CORRECT, 'users/several.yaml')
USER_EXTRAKEY = os.path.join(CONFIG_INVALID, 'users/extrakey.yaml')
USER_INVALID_MEMBER = os.path.join(CONFIG_INVALID, 'users/invalidmember.yaml')
GROUP_CORRECT = os.path.join(CONFIG_CORRECT, '%sgroups/group_one.yaml')
GROUP_CORRECT = os.path.join(CONFIG_CORRECT, '%sgroups/group_one.yaml')
GROUP_CORRECT_SEVERAL = os.path.join(CONFIG_CORRECT, '%sgroups/several.yaml')
GROUP_EXTRAKEY = os.path.join(CONFIG_INVALID, '%sgroups/extrakey.yaml')
GROUP_INVALID_MEMBER = os.path.join(
    CONFIG_INVALID, '%sgroups/invalidmember.yaml')
RULE_CORRECT = os.path.join(CONFIG_CORRECT, '%srules/rule_one.yaml')
RULE_CORRECT_SEVERAL = os.path.join(CONFIG_CORRECT, '%srules/several.yaml')
RULE_EXTRAKEY = os.path.join(CONFIG_INVALID, '%srules/extrakey.yaml')
DOMAIN = 'intgdc.com'


class TestFreeIPAEntityBase(object):
    def load_conf(self, path, *args):
        with open(path % args, 'r') as src:
            return yaml.safe_load(src)


class TestFreeIPAEntity(TestFreeIPAEntityBase):
    def test_create_entity(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAEntity('sample.entity', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAEntity "
            "with abstract methods config_folder, ldap_attrlist, ldap_filter, "
            "type_dn, validation_schema")


class TestFreeIPAGroup(TestFreeIPAEntityBase):
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


class TestFreeIPAHostGroup(TestFreeIPAEntityBase):
    def test_parse_hostgroup_correct(self):
        group = tool.FreeIPAHostGroup(
            'group-one-hosts',
            self.load_conf(GROUP_CORRECT, 'host')['group-one-hosts'], DOMAIN)
        assert isinstance(group, tool.FreeIPAHostGroup)
        assert group.name == 'group-one-hosts'
        assert group.dn == (
            'cn=group-one-hosts,cn=hostgroups,cn=accounts,dc=intgdc,dc=com')
        assert group.data == {'description': ['Sample host group one']}

    def test_parse_hostgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHostGroup(
                'group-one-hosts',
                self.load_conf(GROUP_EXTRAKEY, 'host')['group-one-hosts'],
                DOMAIN)
        assert (
            ("Error validating group-one-hosts: "
             "extra keys not allowed @ data['extrakey']")
            in str(exc)
        )

    def test_parse_hostgroup_invalid_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHostGroup(
                'group-invalid-member',
                self.load_conf(
                    GROUP_INVALID_MEMBER, 'host')['group-invalid-member'],
                DOMAIN)
        assert (
            ("Host group cannot be a member of usergroups "
             "for dictionary value @ data['memberOf']")
            in str(exc)
        )


class TestFreeIPAUser(TestFreeIPAEntityBase):
    def setup_method(self, method):
        self.group_dn = 'cn=groups,cn=accounts,dc=intgdc,dc=com'

    def test_parse_user_correct(self):
        data = self.load_conf(USER_CORRECT)['archibald.jenkins']
        user = tool.FreeIPAUser('archibald.jenkins', data, DOMAIN)
        assert isinstance(user, tool.FreeIPAUser)
        assert user.name == 'archibald.jenkins'
        assert user.dn == (
            'uid=archibald.jenkins,cn=users,cn=accounts,dc=intgdc,dc=com')
        assert sorted(user.data['memberOf']) == [
            'cn=group-one-users,%s' % self.group_dn,
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
            'cn=rule-one,cn=sudo,dc=intgdc,dc=com']
        assert user.data['initials'] == ['AJE']
        assert user.data['manager'] == [
            'uid=sample.manager,cn=users,cn=accounts,dc=intgdc,dc=com']

    def test_parse_user_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'extra.key', self.load_conf(USER_EXTRAKEY)['extra.key'],
                DOMAIN)
        assert (
            ("ConfigError: Error validating extra.key: "
             "extra keys not allowed @ data['invalid']")
            in str(exc)
        )

    def test_parse_user_invalid_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'invalid.member',
                self.load_conf(USER_INVALID_MEMBER)['invalid.member'], DOMAIN)
        assert (
            ("Error validating invalid.member: User cannot be a member "
             "of hostgroups for dictionary value @ data['memberOf']")
            in str(exc)
        )

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
        assert user._map_memberof({
            'usergroups': ['test-users']
        }) == [
            'cn=test-users,cn=groups,cn=accounts,dc=localhost']


class TestFreeIPAUserGroup(TestFreeIPAEntityBase):
    def test_parse_usergroup_correct(self):
        group = tool.FreeIPAUserGroup(
            'group-one-users',
            self.load_conf(GROUP_CORRECT, 'user')['group-one-users'], DOMAIN)
        assert isinstance(group, tool.FreeIPAUserGroup)
        assert group.name == 'group-one-users'
        assert group.dn == (
            'cn=group-one-users,cn=groups,cn=accounts,dc=intgdc,dc=com')
        assert group.data == {
            'description': ['Sample group one']
        }

    def test_parse_usergroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUserGroup(
                'group-one-users',
                self.load_conf(GROUP_EXTRAKEY, 'user')['group-one-users'],
                DOMAIN)
        assert (
            ("Error validating group-one-users: "
             "extra keys not allowed @ data['extrakey']")
            in str(exc)
        )

    def test_parse_usergroup_invalid_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUserGroup(
                'group-invalid-member',
                self.load_conf(
                    GROUP_INVALID_MEMBER, 'user')['group-invalid-member'],
                DOMAIN)
        assert (
            ("Error validating group-invalid-member: User group cannot be "
             "a member of hostgroups for dictionary value @ data['memberOf']")
            in str(exc)
        )

    def test_convert(self):
        data = {
            'description': 'A sample group.',
            'memberOf': {'usergroups': ['group-one']}
        }
        with mock.patch('entities.FreeIPAUserGroup._parse_data'):
            group = tool.FreeIPAUserGroup('some-group', data, 'localhost')
        assert group._convert(data) == {
            'description': ['A sample group.'],
            'memberOf': [
                'cn=group-one,cn=groups,cn=accounts,dc=localhost']}


class TestFreeIPAHBACRule(TestFreeIPAEntityBase):
    def test_parse_hbac_rule_correct(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one',
            self.load_conf(RULE_CORRECT, 'hbac')['rule-one'], DOMAIN)
        assert isinstance(rule, tool.FreeIPAHBACRule)
        assert rule.name == 'rule-one'
        assert rule.dn == ('cn=rule-one,cn=hbac,dc=intgdc,dc=com')
        assert rule.data == {
            'description': ['Sample HBAC rule one'],
            'ipaEnabledFlag': ['TRUE']}

    def test_parse_hbac_rule_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHBACRule(
                'rule-one',
                self.load_conf(RULE_EXTRAKEY, 'hbac')['rule-one'], DOMAIN)
        assert (
            ("Error validating rule-one: extra keys "
             "not allowed @ data['extrakey']")
            in str(exc)
        )


class TestFreeIPASudoRule(TestFreeIPAEntityBase):
    def test_parse_sudo_rule_correct(self):
        rule = tool.FreeIPASudoRule(
            'rule-one',
            self.load_conf(RULE_CORRECT, 'sudo')['rule-one'], DOMAIN)
        assert isinstance(rule, tool.FreeIPASudoRule)
        assert rule.name == 'rule-one'
        assert rule.dn == ('cn=rule-one,cn=sudo,dc=intgdc,dc=com')
        assert rule.data == {'description': ['Sample sudo rule one']}

    def test_parse_sudo_rule_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPASudoRule(
                'rule-one',
                self.load_conf(RULE_EXTRAKEY, 'sudo')['rule-one'], DOMAIN)
        assert (
            ("Error validating rule-one: "
             "extra keys not allowed @ data['extrakey']")
            in str(exc)
        )
