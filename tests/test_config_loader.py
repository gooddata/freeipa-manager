import logging
import mock
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(testpath, '..'))
modulename = 'ipamanager.config_loader'

import ipamanager.config_loader as tool
import ipamanager.entities as entities
import ipamanager.utils as utils

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')
IGNORED_CORRECT = os.path.join(CONFIG_CORRECT, 'ignored.yaml')
IGNORED_INVALID = os.path.join(CONFIG_INVALID, 'ignored.yaml')


class TestConfigLoader(object):
    def setup_method(self, method):
        self.loader = tool.ConfigLoader(CONFIG_CORRECT, IGNORED_CORRECT)
        self.expected_hostgroups = [
            CONFIG_CORRECT + '/hostgroups/%s.yaml' % group
            for group in ['group_one', 'several']]
        self.expected_users = [
            CONFIG_CORRECT + '/users/%s.yaml' % user
            for user in ['archibald_jenkins', 'several']]
        self.expected_groups = [
            CONFIG_CORRECT + '/groups/%s.yaml' % group
            for group in ['group_one', 'several']]
        self.expected_hbac_rules = [
            CONFIG_CORRECT + '/hbacrules/%s.yaml' % rule
            for rule in ['rule_one', 'several']]
        self.expected_sudo_rules = [
            CONFIG_CORRECT + '/sudorules/%s.yaml' % rule
            for rule in ['rule_one', 'several']]
        for cls in utils.ENTITY_CLASSES:
            cls.ignored = []

    def test_retrieve_paths(self):
        paths = self.loader._retrieve_paths()
        assert sorted(paths.keys()) == [
            'group', 'hbacrule', 'hostgroup', 'sudorule', 'user']
        assert sorted(paths['hostgroup']) == self.expected_hostgroups
        assert sorted(paths['user']) == self.expected_users
        assert sorted(paths['group']) == self.expected_groups
        assert sorted(paths['hbacrule']) == self.expected_hbac_rules
        assert sorted(paths['sudorule']) == self.expected_sudo_rules

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_retrieve_paths_empty(self, captured_warnings):
        self.loader.basepath = '/dev/null'
        paths = self.loader._retrieve_paths()
        assert paths.keys() == []
        assert set(i.msg % i.args for i in captured_warnings.records) == set([
            'No hbacrule files found',
            'No hostgroup files found',
            'No sudorule files found',
            'No group files found',
            'No user files found'])

    @log_capture('ConfigLoader', level=logging.DEBUG)
    def test_run_yamllint_check_ok(self, captured_log):
        data = '---\ntest-group:\n  description: A test group.\n'
        self.loader._run_yamllint_check(data, 'groups/test_group.yaml')
        captured_log.check(
            ('ConfigLoader', 'DEBUG',
             'groups/test_group.yaml yamllint check passed successfully'))

    def test_run_yamllint_check_error(self):
        data = 'test-group:\n  description: A test group.\n  description: test'
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._run_yamllint_check(data, 'groups/test_group.yaml')
        assert exc.value[0] == (
            'yamllint errors: [1:1: missing document start "---" '
            '(document-start), 3:3: duplication of key "description" '
            'in mapping (key-duplicates), 3:20: no new line character '
            'at the end of file (new-line-at-end-of-file)]')

    def test_parse(self):
        self.loader.entities = {'user': []}
        data = {
            'archibald.jenkins': {'firstName': 'first', 'lastName': 'last'}}
        self.loader._parse(
            data, entities.FreeIPAUser, 'users/archibald_jenkins.yaml')

    def test_parse_empty(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                {}, entities.FreeIPAUser, 'users/archibald_jenkins.yaml')
        assert exc.value[0] == 'Config must be a non-empty dictionary'

    def test_parse_bad_data_format(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                [{'archibald.jenkins': {}}],
                entities.FreeIPAUser, 'users/archibald_jenkins.yaml')
        assert exc.value[0] == 'Config must be a non-empty dictionary'

    def test_parse_duplicit_entities(self):
        data = {
            'archibald.jenkins': {'firstName': 'first', 'lastName': 'last'}}
        self.loader.entities = {
            'user': [
                entities.FreeIPAUser(
                    'archibald.jenkins',
                    {'firstName': 'first', 'lastName': 'last'})]}
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                data, entities.FreeIPAUser, 'users/archibald_jenkins.yaml')
        assert exc.value[0] == 'Duplicit definition of archibald.jenkins'

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_parse_ignored(self, captured_warnings):
        data = {
            'archibald.jenkins': {'firstName': 'first', 'lastName': 'last'}}
        self.loader.entities['user'] = []
        with mock.patch(
                'ipamanager.entities.FreeIPAUser.ignored',
                ['archibald.jenkins']):
            self.loader._parse(
                data, entities.FreeIPAUser, 'users/archibald_jenkins.yaml')
        assert self.loader.entities['user'] == []
        captured_warnings.check(('ConfigLoader', 'WARNING',
                                ('Not creating ignored user archibald.jenkins '
                                 'from users/archibald_jenkins.yaml')))

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_load(self, captured_warnings):
        self.loader.basepath = CONFIG_CORRECT
        self.loader.load()
        hostgroups = self.loader.entities['hostgroup']
        assert len(hostgroups) == 3
        assert set(g.name for g in hostgroups) == set([
            'group-one-hosts', 'group-two', 'group-three-hosts'])
        users = self.loader.entities['user']
        assert len(users) == 3
        assert sorted(u.name for u in users) == [
            'archibald.jenkins', 'firstname.lastname', 'firstname.lastname2']
        groups = self.loader.entities['group']
        assert len(groups) == 3
        assert set(g.name for g in groups) == set([
            'group-one-users', 'group-two', 'group-three-users'])
        assert set(i.msg % i.args for i in captured_warnings.records) == set([
            'More than one entity parsed from hbacrules/several.yaml (2)',
            'More than one entity parsed from hostgroups/several.yaml (2)',
            'More than one entity parsed from sudorules/several.yaml (2)',
            'More than one entity parsed from groups/several.yaml (2)',
            'More than one entity parsed from users/several.yaml (2)'])

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_load_empty(self, captured_warnings):
        self.loader.basepath = '/dev/null'
        self.loader.load()
        assert self.loader.entities == dict()
        assert set(i.msg % i.args for i in captured_warnings.records) == set([
            'No hbacrule files found',
            'No hostgroup files found',
            'No sudorule files found',
            'No group files found',
            'No user files found'])

    def test_load_invalid(self):
        self.loader.basepath = CONFIG_INVALID
        with pytest.raises(tool.ConfigError) as exc:
            self.loader.load()
        err = exc.value[0]
        for i in [
                'hbacrules/extrakey.yaml', 'hostgroups/extrakey.yaml',
                'sudorules/extrakey.yaml', 'groups/extrakey.yaml',
                'users/extrakey.yaml']:
            assert i in err
        assert ('users/duplicit.yaml' in err or
                'users/duplicit2.yaml' in err)

    @log_capture('ConfigLoader', level=logging.DEBUG)
    def test_load_ignored_no_file(self, captured_log):
        loader = tool.ConfigLoader(None, None)
        loader.load_ignored()
        captured_log.check(
            ('ConfigLoader', 'DEBUG', 'No ignored entities file configured.'))

    def test_load_ignored_correct(self):
        assert entities.FreeIPAUser.ignored == []
        assert entities.FreeIPAUserGroup.ignored == []
        assert entities.FreeIPAHostGroup.ignored == []
        assert entities.FreeIPAHBACRule.ignored == []
        assert entities.FreeIPASudoRule.ignored == []
        self.loader.ignored_file = IGNORED_CORRECT
        self.loader.load_ignored()
        assert entities.FreeIPAUser.ignored == ['admin']
        assert entities.FreeIPAUserGroup.ignored == ['ipausers', 'testgroup']
        assert entities.FreeIPAHostGroup.ignored == ['some-hosts']
        assert entities.FreeIPAHBACRule.ignored == ['rule1']
        assert entities.FreeIPASudoRule.ignored == []

    def test_load_ignored_error(self):
        self.loader.ignored_file = 'some/path'
        with mock.patch('__builtin__.open') as mock_open:
            mock_open.side_effect = IOError('[Errno 2] No such file or dir')
            with pytest.raises(tool.ManagerError) as exc:
                self.loader.load_ignored()
        assert exc.value[0] == (
            'Error opening ignored entities file: '
            '[Errno 2] No such file or dir')

    def test_load_ignored_invalid(self):
        self.loader.ignored_file = IGNORED_INVALID
        with pytest.raises(tool.ManagerError) as exc:
            self.loader.load_ignored()
        assert exc.value[0] == (
            'Ignored entities file error: values must be name lists')
        with mock.patch('%s.yaml.safe_load' % modulename) as mock_load:
            mock_load.return_value = ['entity1', 'entity2']
            with pytest.raises(tool.ManagerError) as exc:
                self.loader.load_ignored()
            assert exc.value[0] == (
                'Ignored entities file error: must be a dict')
            mock_load.return_value = {'invalid': ['entity1']}
            with pytest.raises(tool.ManagerError) as exc:
                self.loader.load_ignored()
            assert exc.value[0] == (
                'Invalid type in ignored entities file: invalid')
