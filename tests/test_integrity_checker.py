import logging
import os.path
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'integrity_checker')
testpath = os.path.dirname(os.path.abspath(__file__))


class TestIntegrityChecker(object):
    def _create_checker(self, entities):
        settings_path = os.path.join(
            testpath, 'freeipa-manager-config/integrity_config.yaml')
        self.checker = tool.IntegrityChecker(settings_path, entities)
        self.checker.errs = dict()

    def test_build_dict(self):
        self._create_checker(self._sample_entities_correct())
        entity_dict = self.checker.entity_dict
        assert sorted(entity_dict.keys()) == [
            'group', 'hbacrule', 'hostgroup', 'sudorule', 'user']
        assert isinstance(
            entity_dict['hostgroup']['group-one-hosts'],
            tool.entities.FreeIPAHostGroup)
        assert isinstance(
            entity_dict['group']['group-one-users'],
            tool.entities.FreeIPAUserGroup)
        assert isinstance(
            entity_dict['user']['firstname.lastname3'],
            tool.entities.FreeIPAUser)

    def test_load_rule_correct(self):
        self._create_checker(dict())
        assert self.checker.rules == {
            'group': {'group': None, 'user': ['member_of_nonmeta']},
            'hbacrule': {'memberHost': ['meta'], 'memberUser': ['meta']},
            'hostgroup': {'hostgroup': None},
            'sudorule': {'memberHost': ['meta'], 'memberUser': ['meta']}}

    def test_load_rule_incorrect(self):
        with pytest.raises(tool.ManagerError) as exc:
            tool.IntegrityChecker('invalid/path/~', dict())
        assert exc.value[0] == (
            "Cannot open rules file: "
            "[Errno 2] No such file or directory: 'invalid/path/~'")

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
            ('group', 'group-two'): ['memberOf non-existent group group-one'],
            ('hostgroup', 'group-one-hosts'): [
                'memberOf non-existent hostgroup group-two'],
            ('user', 'firstname.lastname2'): [
                'memberOf non-existent group group-one']}

    def test_check_rule_member_nonexistent(self):
        data = {
            'hbacrule': [
                tool.entities.FreeIPAHBACRule(
                    'rule-one', {'memberHost': ['no'], 'memberUser': ['no']},
                    'path')]}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): [
                'non-existent memberHost no',
                'non-existent memberUser no']}

    def test_check_rule_member_rule_violation(self):
        data = {
            'hbacrule': [
                tool.entities.FreeIPAHBACRule(
                    'rule-one', {
                        'memberHost': ['group-one-hosts'],
                        'memberUser': ['group-one-users']}, 'path')],
            'hostgroup': [tool.entities.FreeIPAHostGroup(
                'group-one-hosts', {}, 'path')],
            'group': [tool.entities.FreeIPAUserGroup(
                'group-one-users', {}, 'path')]}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): [
                ('group-one-hosts must be a meta group '
                 'to be a member of rule-one'),
                ('group-one-users must be a meta group '
                 'to be a member of rule-one')]}

    def test_check_rule_member_missing_attribute(self):
        data = {
            'hbacrule': [
                tool.entities.FreeIPAHBACRule('rule-one', {}, 'path')]}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): ['no memberHost', 'no memberUser']}

    def test_check_memberof_invalidtype(self):
        self._create_checker(self._sample_entities_member_invalidtype())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('user', 'firstname.lastname2'): [
                'cannot be a member of a hostgroup (group-one)']}

    def test_check_memberof_itself(self):
        self._create_checker(self._sample_entities_member_itself())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-one'): ['memberOf itself']}

    def test_check_cycle_two_nodes(self):
        self._create_checker(self._sample_entities_cycle_two_nodes())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-one'): [
                'Cyclic membership: [group group-one, group group-two]'],
            ('group', 'group-two'): [
                'Cyclic membership: [group group-two, group group-one]']}

    def test_check_cycle_three_nodes(self):
        self._create_checker(self._sample_entities_cycle_three_nodes())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-one'): [
                ('Cyclic membership: '
                 '[group group-one, group group-two, group group-three]')],
            ('group', 'group-three'): [
                ('Cyclic membership: '
                 '[group group-three, group group-one, group group-two]')],
            ('group', 'group-two'): [
                ('Cyclic membership: '
                 '[group group-two, group group-three, group group-one]')]}

    def test_check_member_rule_meta(self):
        self._create_checker(dict())
        group_one = tool.entities.FreeIPAUserGroup(
            'group-one-users', {}, 'path')
        rule_one = tool.entities.FreeIPAHBACRule('rule-one', {}, 'path')
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_rule(group_one, rule_one, 'meta')
        assert exc.value[0] == (
            'group-one-users must be a meta group to be a member of rule-one')

    def test_check_member_rule_nonmeta(self):
        self._create_checker(dict())
        hbac_member = {'memberOf': {'hbacrule': ['rule-one']}}
        group_one = tool.entities.FreeIPAUserGroup(
            'group-one', hbac_member)
        rule_one = tool.entities.FreeIPAHBACRule('rule-one', {})
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_rule(group_one, rule_one, 'nonmeta')
        assert exc.value[0] == (
            'group-one must not be a meta group to be a member of rule-one')

    def test_check_member_rule_member_of_meta(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'firstName': 'Firstname', 'lastName': 'Lastname',
             'memberOf': {'group': ['group-one-users']}})
        group_one = tool.entities.FreeIPAUserGroup(
            'group-one-users', {})
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
            {'firstName': 'Firstname', 'lastName': 'Lastname',
             'memberOf': {'group': ['group-one-users']}})
        group_one = tool.entities.FreeIPAUserGroup('group-one', {})
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
            'user': [
                tool.entities.FreeIPAUser(
                    'firstname.lastname',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path'),
                tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'group': ['group-one-users']}}, 'path'),
                tool.entities.FreeIPAUser(
                    'firstname.lastname3',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path')],
            'group': [
                tool.entities.FreeIPAUserGroup(
                    'group-one-users', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                tool.entities.FreeIPAUserGroup('group-two', {}, 'path')],
            'hostgroup': [
                tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroup': ['group-two']}}, 'path'),
                tool.entities.FreeIPAHostGroup('group-two', {}, 'path')],
            'hbacrule': [
                tool.entities.FreeIPAHBACRule(
                    'rule-one',
                    {'memberHost': ['group-two'], 'memberUser': ['group-two']},
                    'path')],
            'sudorule': [
                tool.entities.FreeIPASudoRule(
                    'rule-one',
                    {'memberHost': ['group-two'], 'memberUser': ['group-two']},
                    'path')]
        }

    def _sample_entities_member_nonexistent(self):
        return {
            'user': [
                tool.entities.FreeIPAUser(
                    'firstname.lastname',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path'),
                tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'group': ['group-one']}}, 'path'),
                tool.entities.FreeIPAUser(
                    'firstname.lastname3',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path')],
            'group': [
                tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-one']}}, 'path')],
            'hostgroup': [
                tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroup': ['group-two']}}, 'path')]
        }

    def _sample_entities_member_invalidtype(self):
        return {
            'user': [
                tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'hostgroup': ['group-one']}}, 'path')],
            'hostgroup': [
                tool.entities.FreeIPAHostGroup('group-one', {}, 'path')]
        }

    def _sample_entities_member_itself(self):
        return {
            'group': [
                tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-one']}}, 'path')]
        }

    def _sample_entities_cycle_two_nodes(self):
        return {
            'group': [
                tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-one']}}, 'path')]}

    def _sample_entities_cycle_three_nodes(self):
        return {
            'group': [
                tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-three']}}, 'path'),
                tool.entities.FreeIPAUserGroup(
                    'group-three', {
                        'memberOf': {'group': ['group-one']}}, 'path')]}
