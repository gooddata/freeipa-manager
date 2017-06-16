import logging
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('integrity_checker')

ACCOUNTS_BASE = 'cn=accounts,dc=intgdc,dc=com'
DOMAIN = 'intgdc.com'


class TestIntegrityChecker(object):
    def _create_checker(self, entities):
        settings_path = os.path.join(
            testpath, 'freeipa-manager-config/integrity_config.yaml')
        self.checker = tool.IntegrityChecker(settings_path, entities)
        self.checker.errs = dict()
        self.sample_user = tool.entities.FreeIPAUser(
            'sample.user', {}, DOMAIN)

    def test_build_dict(self):
        self._create_checker(self._sample_entities_correct())
        entity_dict = self.checker.entity_dict
        assert sorted(entity_dict.keys()) == [
            'cn=group-one-hosts,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
            'cn=group-one-users,cn=groups,cn=accounts,dc=intgdc,dc=com',
            'cn=group-two,cn=groups,cn=accounts,dc=intgdc,dc=com',
            'cn=group-two,cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com',
            'cn=rule-one,cn=sudo,dc=intgdc,dc=com',
            'uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,dc=com',
            'uid=firstname.lastname2,cn=users,cn=accounts,dc=intgdc,dc=com',
            'uid=firstname.lastname3,cn=users,cn=accounts,dc=intgdc,dc=com']
        assert isinstance(
            entity_dict['cn=group-one-hosts,cn=hostgroups,%s' % ACCOUNTS_BASE],
            tool.entities.FreeIPAHostGroup)
        assert isinstance(
            entity_dict['cn=group-one-users,cn=groups,%s' % ACCOUNTS_BASE],
            tool.entities.FreeIPAUserGroup)
        assert isinstance(
            entity_dict['uid=firstname.lastname,cn=users,%s' % ACCOUNTS_BASE],
            tool.entities.FreeIPAUser)

    @log_capture('IntegrityChecker', level=logging.WARNING)
    def test_check_empty(self, captured_warnings):
        self._create_checker(dict())
        self.checker.check()
        captured_warnings.check((
            'IntegrityChecker', 'WARNING',
            'No entities to check for integrity'))

    def test_check_correct(self):
        self._create_checker(self._sample_entities_correct())
        self.checker.check()
        assert not self.checker.errs

    def test_check_memberof_nonexistent(self):
        self._create_checker(self._sample_entities_member_nonexistent())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'cn=group-one-hosts,cn=hostgroups,%s' % ACCOUNTS_BASE: [
                ('memberOf non-existent entity '
                 'cn=group-two,cn=hostgroups,cn=accounts,dc=intgdc,dc=com')],
            'cn=group-two,cn=groups,%s' % ACCOUNTS_BASE: [
                ('memberOf non-existent entity '
                 'cn=group-one,cn=groups,cn=accounts,dc=intgdc,dc=com')],
            'uid=firstname.lastname2,cn=users,%s' % ACCOUNTS_BASE: [
                ('memberOf non-existent entity '
                 'cn=group-one,cn=groups,cn=accounts,dc=intgdc,dc=com')]}

    def test_check_rule_member_nonexistent(self):
        data = {
            'HBAC rules': [
                tool.entities.FreeIPAHBACRule(
                    'rule-one', {'memberHost': 'no', 'memberUser': 'no'},
                    DOMAIN)]}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com': [
                ('non-existent memberHost '
                 'cn=no,cn=hostgroups,cn=accounts,dc=intgdc,dc=com'),
                ('non-existent memberUser '
                 'cn=no,cn=groups,cn=accounts,dc=intgdc,dc=com')]}

    def test_check_rule_member_rule_violation(self):
        data = {
            'HBAC rules': [
                tool.entities.FreeIPAHBACRule(
                    'rule-one', {
                        'memberHost': 'group-one-hosts',
                        'memberUser': 'group-one-users'}, DOMAIN)],
            'hostgroups': [tool.entities.FreeIPAHostGroup(
                'group-one-hosts', {}, DOMAIN)],
            'usergroups': [tool.entities.FreeIPAUserGroup(
                'group-one-users', {}, DOMAIN)]}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com': [
                ('group-one-hosts must be a meta group '
                 'to be a member of rule-one'),
                ('group-one-users must be a meta group '
                 'to be a member of rule-one')]}

    def test_check_rule_member_missing_attribute(self):
        data = {
            'HBAC rules': [
                tool.entities.FreeIPAHBACRule(
                    'rule-one', {}, DOMAIN)]}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com': [
                'no memberHost', 'no memberUser']}

    def test_check_memberof_invalidtype(self):
        self._create_checker(self._sample_entities_member_invalidtype())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'uid=firstname.lastname2,cn=users,%s' % ACCOUNTS_BASE: [
                'cannot be a member of hostgroups (group-one)']}

    def test_check_memberof_itself(self):
        self._create_checker(self._sample_entities_member_itself())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'cn=group-one,cn=groups,%s' % ACCOUNTS_BASE: ['memberOf itself']}

    def test_check_cycle_two_nodes(self):
        self._create_checker(self._sample_entities_cycle_two_nodes())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'cn=group-one,cn=groups,%s' % ACCOUNTS_BASE: [
                'Cyclic membership of usergroups: [group-one, group-two]'],
            'cn=group-two,cn=groups,%s' % ACCOUNTS_BASE: [
                'Cyclic membership of usergroups: [group-two, group-one]']}

    def test_check_cycle_three_nodes(self):
        self._create_checker(self._sample_entities_cycle_three_nodes())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            'cn=group-one,cn=groups,%s' % ACCOUNTS_BASE: [
                ('Cyclic membership of usergroups: '
                 '[group-one, group-two, group-three]')],
            'cn=group-three,cn=groups,%s' % ACCOUNTS_BASE: [
                ('Cyclic membership of usergroups: '
                 '[group-three, group-one, group-two]')],
            'cn=group-two,cn=groups,%s' % ACCOUNTS_BASE: [
                ('Cyclic membership of usergroups: '
                 '[group-two, group-three, group-one]')]}

    def test_check_member_rule_meta(self):
        self._create_checker(dict())
        group_one = tool.entities.FreeIPAUserGroup(
            'group-one-users', {}, DOMAIN)
        rule_one = tool.entities.FreeIPAHBACRule('rule-one', {}, DOMAIN)
        self.checker.entity_dict = {
            'cn=group-one-users,cn=groups,%s' % ACCOUNTS_BASE: group_one,
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com': rule_one}
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_rule(group_one, rule_one, 'meta')
        assert exc.value[0] == (
            'group-one-users must be a meta group to be a member of rule-one')

    def test_check_member_rule_nonmeta(self):
        self._create_checker(dict())
        hbac_member = {'memberOf': {'HBAC rules': ['rule-one']}}
        group_one = tool.entities.FreeIPAUserGroup(
            'group-one', hbac_member, DOMAIN)
        rule_one = tool.entities.FreeIPAHBACRule('rule-one', {}, DOMAIN)
        self.checker.entity_dict = {
            'cn=group-one,cn=groups,%s' % ACCOUNTS_BASE: group_one,
            'cn=rule-one,cn=hbac,dc=intgdc,dc=com': rule_one}
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_rule(group_one, rule_one, 'nonmeta')
        assert exc.value[0] == (
            'group-one must not be a meta group to be a member of rule-one')

    def test_check_member_rule_member_of_meta(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'memberOf': {'usergroups': ['group-one-users']}}, DOMAIN)
        group_one = tool.entities.FreeIPAUserGroup(
            'group-one-users', {}, DOMAIN)
        self.checker.entity_dict = {
            'uid=firstname.lastname,cn=users,%s' % ACCOUNTS_BASE: user_one,
            'cn=group-one-users,cn=groups,%s' % ACCOUNTS_BASE: group_one}
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_rule(
                user_one, group_one, 'member_of_meta')
        assert exc.value[0] == (
            'group-one-users must be a meta group '
            'to have firstname.lastname as a member')

    def test_check_member_rule_member_of_nonmeta(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'memberOf': {'usergroups': ['group-one-users']}}, DOMAIN)
        group_one = tool.entities.FreeIPAUserGroup('group-one', {}, DOMAIN)
        self.checker.entity_dict = {
            'uid=firstname.lastname,cn=users,%s' % ACCOUNTS_BASE: user_one,
            'cn=group-one-users,cn=groups,%s' % ACCOUNTS_BASE: group_one}
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_rule(
                user_one, group_one, 'member_of_nonmeta')
        assert exc.value[0] == (
            'group-one must not be a meta group '
            'to have firstname.lastname as a member')

    def test_check_member_rule_invalid(self):
        self._create_checker(dict())
        with pytest.raises(tool.ManagerError) as exc:
            self.checker._check_member_rule(None, None, 'invalid-rule')
        assert exc.value[0] == 'Undefined rule: invalid-rule'

    def _sample_entities_correct(self):
        return {
            'users': [
                tool.entities.FreeIPAUser('firstname.lastname', {}, DOMAIN),
                tool.entities.FreeIPAUser(
                    'firstname.lastname2', {
                        'memberOf': {'usergroups': ['group-one-users']}},
                    DOMAIN),
                tool.entities.FreeIPAUser('firstname.lastname3', {}, DOMAIN)],
            'usergroups': [
                tool.entities.FreeIPAUserGroup(
                    'group-one-users', {
                        'memberOf': {'usergroups': ['group-two']}}, DOMAIN),
                tool.entities.FreeIPAUserGroup('group-two', {}, DOMAIN)],
            'hostgroups': [
                tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroups': ['group-two']}}, DOMAIN),
                tool.entities.FreeIPAHostGroup('group-two', {}, DOMAIN)],
            'HBAC rules': [
                tool.entities.FreeIPAHBACRule(
                    'rule-one',
                    {'memberHost': 'group-two', 'memberUser': 'group-two'},
                    DOMAIN)],
            'sudo rules': [
                tool.entities.FreeIPASudoRule(
                    'rule-one',
                    {'memberHost': 'group-two', 'memberUser': 'group-two'},
                    DOMAIN)]
        }

    def _sample_entities_member_nonexistent(self):
        return {
            'users': [
                tool.entities.FreeIPAUser(
                    'firstname.lastname', {}, DOMAIN),
                tool.entities.FreeIPAUser(
                    'firstname.lastname2', {
                        'memberOf': {'usergroups': ['group-one']}}, DOMAIN),
                tool.entities.FreeIPAUser(
                    'firstname.lastname3', {}, DOMAIN)],
            'usergroups': [
                tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'usergroups': ['group-one']}}, DOMAIN)],
            'hostgroups': [
                tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroups': ['group-two']}}, DOMAIN)]
        }

    def _sample_entities_member_invalidtype(self):
        return {
            'users': [
                tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'memberOf': {'hostgroups': ['group-one']}}, DOMAIN)],
            'hostgroups': [
                tool.entities.FreeIPAHostGroup('group-one', {}, DOMAIN)]
        }

    def _sample_entities_member_itself(self):
        return {
            'usergroups': [
                tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'usergroups': ['group-one']}}, DOMAIN)]
        }

    def _sample_entities_cycle_two_nodes(self):
        return {
            'usergroups': [
                tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'usergroups': ['group-two']}}, DOMAIN),
                tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'usergroups': ['group-one']}}, DOMAIN)]}

    def _sample_entities_cycle_three_nodes(self):
        return {
            'usergroups': [
                tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'usergroups': ['group-two']}}, DOMAIN),
                tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'usergroups': ['group-three']}}, DOMAIN),
                tool.entities.FreeIPAUserGroup(
                    'group-three', {
                        'memberOf': {'usergroups': ['group-one']}}, DOMAIN)]}
