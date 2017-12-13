import logging
import os.path
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'integrity_checker')
testpath = os.path.dirname(os.path.abspath(__file__))


class TestIntegrityChecker(object):
    def _create_checker(self, entities):
        settings = {'user-group-pattern': '^role-.+|.+-users$'}
        self.checker = tool.IntegrityChecker(entities, settings)
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

    def test_check_memberof_meta_violation(self):
        data = {
            'group': {'group-one': tool.entities.FreeIPAUserGroup(
                      'group-one', {}, 'path')},
            'user': {'user.one': tool.entities.FreeIPAUser('user.one', {
                     'firstName': 'User', 'lastName': 'One',
                     'memberOf': {'group': ['group-one']}}, 'path2')}}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('user', 'user.one'): ['group-one cannot contain users directly']}

    def test_check_rule_member_nonexistent(self):
        data = {
            'hbacrule': {'rule-one': tool.entities.FreeIPAHBACRule(
                'rule-one', {'memberHost': ['no'],
                             'memberUser': ['no']}, 'path')}}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): [
                'non-existent memberHost no',
                'non-existent memberUser no']}

    def test_check_rule_meta_violation(self):
        data = {
            'hbacrule': {
                'rule-one': tool.entities.FreeIPAHBACRule(
                    'rule-one', {
                        'memberHost': ['group-one-hosts'],
                        'memberUser': ['group-one-users']}, 'path')},
            'hostgroup': {'group-one-hosts': tool.entities.FreeIPAHostGroup(
                'group-one-hosts', {}, 'path')},
            'group': {'group-one-users': tool.entities.FreeIPAUserGroup(
                'group-one-users', {}, 'path')}}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): ['group-one-users can contain users']}

    def test_check_rule_member_missing_attribute(self):
        data = {
            'hbacrule': {'rule-one': tool.entities.FreeIPAHBACRule(
                         'rule-one', {}, 'path')}}
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
                "group-one can only have members of type ['hostgroup']"]}

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

    def test_check_member_type_ok(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'firstName': 'Firstname', 'lastName': 'Lastname',
             'memberOf': {'group': ['group-one-users']}})
        group_one = tool.entities.FreeIPAUserGroup('group-one', {})
        self.checker._check_member_type(user_one, group_one)

    def test_check_member_type_wrong_target_type(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'firstName': 'Firstname', 'lastName': 'Lastname',
             'memberOf': {'group': ['group-one-users']}})
        rule_one = tool.entities.FreeIPAHBACRule('rule-one', {})
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_type(user_one, rule_one)
        assert exc.value[0] == 'rule-one not group, cannot have members'

    def test_check_member_type_wrong_member_type(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAHostGroup('hostgroup-one', {})
        group_one = tool.entities.FreeIPAUserGroup('group-one', {})
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_type(user_one, group_one)
        assert exc.value[0] == (
            "group-one can only have members of type ['user', 'group']")

    def _sample_entities_correct(self):
        return {
            'user': {
                'firstname.lastname': tool.entities.FreeIPAUser(
                    'firstname.lastname',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path'),
                'firstname.lastname2': tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'group': ['group-one-users']}}, 'path'),
                'firstname.lastname3': tool.entities.FreeIPAUser(
                    'firstname.lastname3',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path')},
            'group': {
                'group-one-users': tool.entities.FreeIPAUserGroup(
                    'group-one-users', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {}, 'path')},
            'hostgroup': {
                'group-one-hosts': tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroup': ['group-two']}}, 'path'),
                'group-two': tool.entities.FreeIPAHostGroup(
                    'group-two', {}, 'path')},
            'hbacrule': {
                'rule-one': tool.entities.FreeIPAHBACRule(
                    'rule-one',
                    {'memberHost': ['group-two'], 'memberUser': ['group-two']},
                    'path')},
            'sudorule': {
                'rule-one': tool.entities.FreeIPASudoRule(
                    'rule-one',
                    {'memberHost': ['group-two'], 'memberUser': ['group-two']},
                    'path')}}

    def _sample_entities_member_nonexistent(self):
        return {
            'user': {
                'firstname.lastname': tool.entities.FreeIPAUser(
                    'firstname.lastname',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path'),
                'firstname.lastname2': tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'group': ['group-one']}}, 'path'),
                'firstname.lastname3': tool.entities.FreeIPAUser(
                    'firstname.lastname3',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path')},
            'group': {
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-one']}}, 'path')},
            'hostgroup': {
                'group-one-hosts': tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroup': ['group-two']}}, 'path')}}

    def _sample_entities_member_invalidtype(self):
        return {
            'user': {
                'firstname.lastname2': tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'hostgroup': ['group-one']}}, 'path')},
            'hostgroup': {'group-one': tool.entities.FreeIPAHostGroup(
                          'group-one', {}, 'path')}}

    def _sample_entities_member_itself(self):
        return {
            'group': {
                'group-one': tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-one']}}, 'path')}}

    def _sample_entities_cycle_two_nodes(self):
        return {
            'group': {
                'group-one': tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-one']}}, 'path')}}

    def _sample_entities_cycle_three_nodes(self):
        return {
            'group': {
                'group-one': tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-three']}}, 'path'),
                'group-three': tool.entities.FreeIPAUserGroup(
                    'group-three', {
                        'memberOf': {'group': ['group-one']}}, 'path')}}
