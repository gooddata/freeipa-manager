import mock
import os
import pytest
import sys


testpath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(testpath, '..'))

import ipamanager.entities as tool

modulename = 'ipamanager.entities'


class TestFreeIPAEntity(object):
    def test_create_entity(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAEntity('sample.entity', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAEntity "
            "with abstract methods managed_attributes, validation_schema")

    def test_equality(self):
        user1 = tool.FreeIPAUser(
            'user1', {'firstName': 'Some', 'lastName': 'Name'})
        user2 = tool.FreeIPAUser(
            'user1', {'firstName': 'Some', 'lastName': 'Name'})
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
        with mock.patch(
                '%s.FreeIPAUserGroup.meta_group_suffix' % modulename, ''):
            group = tool.FreeIPAUserGroup('sample-group', {})
            assert not group.is_meta

    def test_create_hostgroup_nonmeta(self):
        group = tool.FreeIPAHostGroup('sample-group-hosts', {})
        assert not group.is_meta

    def test_create_hostgroup_meta_not_enforced(self):
        with mock.patch(
                '%s.FreeIPAHostGroup.meta_group_suffix' % modulename, ''):
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
                'hostgroup': ['group-one'],
                'hbacrule': ['rule-one'],
                'sudorule': ['rule-one']}}
        group = tool.FreeIPAHostGroup('group-one-hosts', data)
        assert group.name == 'group-one-hosts'
        assert group.data['memberOf'] == data['memberOf']
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
            'firstName': 'Some',
            'lastName': 'Name',
            'manager': 'sample.manager',
            'memberOf': {'group': ['group-one-users', 'group-two']}
        }
        user = tool.FreeIPAUser('archibald.jenkins', data)
        assert user.name == 'archibald.jenkins'
        assert user.data['memberOf'] == data['memberOf']
        assert user.data['manager'] == ('sample.manager',)

    def test_create_user_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'archibald.jenkins', {'extrakey': 'bad'})
        assert exc.value[0] == (
            "Error validating archibald.jenkins: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert(self):
        data = {
            'firstName': 'Firstname',
            'lastName': 'Lastname',
            'initials': 'FL',
            'organizationUnit': 'TEST'
        }
        user = tool.FreeIPAUser('some.name', data)
        assert user._convert(data) == {
            'givenName': ('Firstname',),
            'sn': ('Lastname',),
            'initials': ('FL',),
            'ou': ('TEST',)
        }


class TestFreeIPAUserGroup(object):
    def test_create_usergroup_correct(self):
        data = {
            'description': 'Sample user group',
            'memberOf': {
                'group': ['group-one'],
                'hbacrule': ['rule-one'],
                'sudorule': ['rule-one']}}
        group = tool.FreeIPAUserGroup(
            'group-one-users', data)
        assert group.name == 'group-one-users'
        assert group.data['memberOf'] == data['memberOf']
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
            'memberHost': ('hosts-one',),
            'memberUser': ('users-one',)
        }

    def test_create_commands_member_same(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'memberHost': 'group-one', 'memberUser': 'group-one'})
        remote_rule = {
            'cn': ('rule-one',), 'memberuser_group': ('group-one',),
            'memberhost_hostgroup': ('group-one',)}
        assert not rule.create_commands(remote_rule)

    def test_create_commands_member_add(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'memberHost': 'group-one', 'memberUser': 'group-one'})
        remote_rule = {'cn': ('rule-one',)}
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 2
        assert [i.command for i in commands] == [
            'hbacrule_add_host', 'hbacrule_add_user']
        assert [i.description for i in commands] == [
            u'hbacrule_add_host rule-one (hostgroup=group-one)',
            u'hbacrule_add_user rule-one (group=group-one)']
        assert [i.payload for i in commands] == [
            {'cn': u'rule-one', 'hostgroup': u'group-one'},
            {'cn': u'rule-one', 'group': u'group-one'}]

    def test_create_commands_member_remove(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'memberHost': 'group-one', 'memberUser': 'group-one'})
        rule.data = dict()  # rule must have members when created
        remote_rule = {
            'cn': ('rule-one',), 'memberuser_group': ('group-one',),
            'memberhost_hostgroup': ('group-one',)}
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 2
        assert [i.command for i in commands] == [
            'hbacrule_remove_host', 'hbacrule_remove_user']
        assert [i.description for i in commands] == [
            u'hbacrule_remove_host rule-one (hostgroup=group-one)',
            u'hbacrule_remove_user rule-one (group=group-one)']
        assert [i.payload for i in commands] == [
            {'cn': u'rule-one', 'hostgroup': u'group-one'},
            {'cn': u'rule-one', 'group': u'group-one'}]


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

    def test_create_commands_option_add(self):
        rule = tool.FreeIPASudoRule(
            'rule-one', {'options': ['!test', '!test2']})
        remote_rule = {'cn': (u'rule-one',)}
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 2
        assert all(i.command == 'sudorule_add_option' for i in commands)
        assert sorted([(i.description, i.payload) for i in commands]) == [
            (u'sudorule_add_option rule-one (ipasudoopt=!test)',
             {'cn': u'rule-one', 'ipasudoopt': u'!test'}),
            (u'sudorule_add_option rule-one (ipasudoopt=!test2)',
             {'cn': u'rule-one', 'ipasudoopt': u'!test2'})]

    def test_create_commands_option_remove(self):
        rule = tool.FreeIPASudoRule('rule-one', {'options': ['!test']})
        remote_rule = {'cn': (u'rule-one',),
                       'ipasudoopt': (u'!test', u'!test2')}
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 1
        assert commands[0].command == 'sudorule_remove_option'
        assert commands[0].description == (
            'sudorule_remove_option rule-one (ipasudoopt=!test2)')
        assert commands[0].payload == {
            'cn': u'rule-one', 'ipasudoopt': u'!test2'}
