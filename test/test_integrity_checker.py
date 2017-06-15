import logging
import mock
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
        self.checker = tool.IntegrityChecker(entities)
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
        with mock.patch(
                'integrity_checker.IntegrityChecker._check_single') as mock_s:
            self.checker.check()
        mock_s.assert_not_called()
        captured_warnings.check((
            'IntegrityChecker', 'WARNING',
            'No entities to check for integrity'))

    def test_check_memberof_meta_users_valid(self):
        self._create_checker(dict())
        assert self.checker._check_memberof_meta(
            self.sample_user,
            tool.entities.FreeIPAUserGroup(
                'test-group-users', {}, DOMAIN))
        assert not self.checker._check_memberof_meta(
            self.sample_user, tool.entities.FreeIPAUserGroup(
                'test-group', {}, DOMAIN))

    def test_check_correct(self):
        self._create_checker(self._sample_entities_correct())
        self.checker.check()
        assert not self.checker.errs

    def test_check_memberof_nonexistent(self):
        self._create_checker(self._sample_entities_member_nonexistent())
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker.check()
        assert exc.value[0] == 'There were 3 integrity errors in 3 entities'
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

    def test_check_memberof_itself(self):
        self._create_checker(self._sample_entities_member_itself())
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker.check()
        assert exc.value[0] == 'There were 1 integrity errors in 1 entities'
        assert self.checker.errs == {
            'cn=group-one,cn=groups,%s' % ACCOUNTS_BASE: ['memberOf itself']}

    def test_check_memberof_meta(self):
        self._create_checker(self._sample_entities_member_meta())
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker.check()
        assert exc.value[0] == 'There were 1 integrity errors in 1 entities'
        assert self.checker.errs == {
            'uid=firstname.lastname2,cn=users,%s' % ACCOUNTS_BASE: [
                'memberOf meta group group-one']}

    def test_check_cycle_two_nodes(self):
        self._create_checker(self._sample_entities_cycle_two_nodes())
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker.check()
        assert exc.value[0] == (
            'Cyclic membership of usergroups [group-one, group-two]')

    def test_check_cycle_three_nodes(self):
        self._create_checker(self._sample_entities_cycle_three_nodes())
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker.check()
        assert exc.value[0] == (
            'Cyclic membership of usergroups '
            '[group-one, group-two, group-three]')

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
                tool.entities.FreeIPAHostGroup('group-two', {}, DOMAIN)]
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

    def _sample_entities_member_itself(self):
        return {
            'usergroups': [
                tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'usergroups': ['group-one']}}, DOMAIN)]
        }

    def _sample_entities_member_meta(self):
        return {
            'users': [
                tool.entities.FreeIPAUser('firstname.lastname', {}, DOMAIN),
                tool.entities.FreeIPAUser(
                    'firstname.lastname2', {
                        'memberOf': {'usergroups': ['group-one']}}, DOMAIN),
                tool.entities.FreeIPAUser('firstname.lastname3', {}, DOMAIN)],
            'usergroups': [
                tool.entities.FreeIPAUserGroup('group-one', {}, DOMAIN)]
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
