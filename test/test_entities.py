import mock
import os
import pytest
import sys


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('entities')


class TestFreeIPAEntity(object):
    def test_create_entity(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAEntity('sample.entity', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAEntity "
            "with abstract methods validation_schema")

    def test_equality(self):
        user1 = tool.FreeIPAUser('user1', {})
        user2 = tool.FreeIPAUser('user1', {})
        assert user1 == user2
        user2.name = 'user2'
        assert user1 != user2

    def test_nonequality_different_type(self):
        group1 = tool.FreeIPAUserGroup('group', {})
        group2 = tool.FreeIPAHostGroup('group', {})
        assert group1 != group2

    def test_nonequality_same_type(self):
        rule1 = tool.FreeIPASudoRule('rule-one', {})
        rule2 = tool.FreeIPASudoRule('rule-two', {})
        assert rule1 != rule2
        rule2.name = 'rule-one'
        assert rule1 == rule2


class TestFreeIPAGroup(object):
    def test_create_group(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAGroup('sample-group', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAGroup "
            "with abstract methods validation_schema")

    def test_create_usergroup_nonmeta(self):
        group = tool.FreeIPAUserGroup('sample-group-users', {})
        assert not group.is_meta

    def test_create_usergroup_meta(self):
        group = tool.FreeIPAUserGroup('sample-group', {})
        assert group.is_meta

    def test_create_usergroup_meta_not_enforced(self):
        with mock.patch('entities.FreeIPAUserGroup.meta_group_suffix', ''):
            group = tool.FreeIPAUserGroup('sample-group', {})
            assert not group.is_meta

    def test_create_hostgroup_nonmeta(self):
        group = tool.FreeIPAHostGroup('sample-group-hosts', {})
        assert not group.is_meta

    def test_create_hostgroup_meta_not_enforced(self):
        with mock.patch('entities.FreeIPAHostGroup.meta_group_suffix', ''):
            group = tool.FreeIPAHostGroup('sample-group', {})
            assert not group.is_meta

    def test_create_hostgroup_meta(self):
        group = tool.FreeIPAHostGroup('sample-group', {})
        assert group.is_meta


class TestFreeIPAHostGroup(object):
    def test_create_hostgroup_correct(self):
        data = {
            'description': 'Sample host group',
            'memberOf': {
                'hostgroups': ['group-one'],
                'hbacrules': ['rule-one'],
                'sudorules': ['rule-one']}}
        group = tool.FreeIPAHostGroup('group-one-hosts', data)
        assert group.name == 'group-one-hosts'
        assert sorted(group.data['memberof']) == [
            ('hbacrule', 'rule-one'),
            ('hostgroup', 'group-one'),
            ('sudorule', 'rule-one')]
        assert group.data['description'] == ('Sample host group',)

    def test_create_hostgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHostGroup(
                'group-one-hosts', {'extrakey': 'bad'})
        assert exc.value[0] == (
            "Error validating group-one-hosts: "
            "extra keys not allowed @ data['extrakey']")


class TestFreeIPAUser(object):
    def test_create_user_correct(self):
        data = {
            'manager': 'sample.manager',
            'memberOf': {'groups': ['group-one-users', 'group-two']}
        }
        user = tool.FreeIPAUser('archibald.jenkins', data)
        assert user.name == 'archibald.jenkins'
        assert sorted(user.data['memberof']) == [
            ('group', 'group-one-users'), ('group', 'group-two')]
        assert user.data['manager'] == ('sample.manager',)

    def test_create_user_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'archibald.jenkins', {'extrakey': 'bad'})
        assert exc.value[0] == (
            "Error validating archibald.jenkins: "
            "extra keys not allowed @ data['extrakey']")

    def test_create_user_invalid_member(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'archibald.jenkins', {'memberOf': {'invalid': ['x']}})
        assert exc.value[0] == (
            'archibald.jenkins cannot be a member '
            'of non-existent class type "invalid"')

    def test_convert(self):
        data = {
            'firstName': 'Firstname',
            'lastName': 'Lastname',
            'initials': 'FL',
            'organizationUnit': 'TEST'
        }
        user = tool.FreeIPAUser('some.name', data)
        assert user._convert(data) == {
            'givenname': ('Firstname',),
            'sn': ('Lastname',),
            'initials': ('FL',),
            'ou': ('TEST',)
        }

    def test_map_memberof(self):
        user = tool.FreeIPAUser('some.name', {})
        assert user._map_memberof({'groups': ['test-users']}) == [
            ('group', 'test-users')]


class TestFreeIPAUserGroup(object):
    def test_create_usergroup_correct(self):
        data = {
            'description': 'Sample user group',
            'memberOf': {
                'groups': ['group-one'],
                'hbacrules': ['rule-one'],
                'sudorules': ['rule-one']}}
        group = tool.FreeIPAUserGroup(
            'group-one-users', data)
        assert group.name == 'group-one-users'
        assert sorted(group.data['memberof']) == [
            ('group', 'group-one'), ('hbacrule', 'rule-one'),
            ('sudorule', 'rule-one')]
        assert group.data['description'] == ('Sample user group',)

    def test_create_usergroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUserGroup(
                'group-one-users', {'extrakey': 'bad'})
        assert exc.value[0] == (
            "Error validating group-one-users: "
            "extra keys not allowed @ data['extrakey']")


class TestFreeIPAHBACRule(object):
    def test_create_hbac_rule_correct(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'description': 'Sample HBAC rule'})
        assert rule.name == 'rule-one'
        assert rule.data == {'description': ('Sample HBAC rule',)}

    def test_create_hbac_rule_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHBACRule('rule-one', {'extrakey': 'bad'})
        assert exc.value[0] == (
            "Error validating rule-one: extra keys "
            "not allowed @ data['extrakey']")

    def test_convert(self):
        data = {
            'description': 'A sample sudo rule.',
            'memberHost': 'hosts-one',
            'memberUser': 'users-one'
        }
        user = tool.FreeIPAHBACRule('rule-one', data)
        assert user._convert(data) == {
            'description': ('A sample sudo rule.',),
            'memberhost': 'hosts-one',
            'memberuser': 'users-one'
        }


class TestFreeIPASudoRule(object):
    def test_create_sudo_rule_correct(self):
        rule = tool.FreeIPASudoRule(
            'rule-one', {'description': 'Sample sudo rule'})
        assert rule.name == 'rule-one'
        assert rule.data == {'description': ('Sample sudo rule',)}

    def test_create_sudo_rule_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPASudoRule('rule-one', {'extrakey': 'bad'})
        assert exc.value[0] == (
            "Error validating rule-one: "
            "extra keys not allowed @ data['extrakey']")
