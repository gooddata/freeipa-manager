import logging
import mock
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)

sys.modules['ipalib'] = mock.Mock()
tool = __import__('ipa_connector')
tool.api = mock.MagicMock()
entities = __import__('entities')


class TestIpaConnector(object):
    def teardown_method(self, _):
        try:
            tool.api.Command.__getitem__.side_effect = self._api_call
        except AttributeError:
            pass

    def _create_connector(self, **args):
        self.connector = tool.IpaConnector(
            parsed=args.get('parsed', {}),
            threshold=args.get('threshold', 0),
            force=args.get('force', False),
            enable_deletion=args.get('enable_deletion', False),
            debug=args.get('debug', False))
        self.connector.commands = dict()
        self.connector.remote_count = 0

    @log_capture('IpaConnector', level=logging.DEBUG)
    def test_load_remote(self, captured_log):
        self._create_connector()
        tool.api.Command.__getitem__.side_effect = self._api_call
        with mock.patch('entities.FreeIPAUser.ignored', ['user.one']):
            self.connector.load_remote()
        for cmd in ('group', 'hbacrule', 'hostgroup', 'sudorule', 'user'):
            tool.api.Command.__getitem__.assert_any_call(
                '%s_find' % cmd)
        msgs = [(r.levelname, r.msg % r.args) for r in captured_log.records]
        assert ('DEBUG', 'Not parsing ignored user user.one') in msgs
        assert ('INFO', 'Parsed 4 entities from FreeIPA API') in msgs

    def test_load_remote_errors(self):
        self._create_connector()
        tool.api.Command.__getitem__.side_effect = (
            self._api_call_find_fail)
        with pytest.raises(tool.ManagerError) as exc:
            self.connector.load_remote()
        assert exc.value[0] == (
            'Error loading hbacrule entities from API: Some error happened')

    def test_load_remote_unknown_command(self):
        self._create_connector()
        with mock.patch(
                'ipa_connector.entities.FreeIPAUser.entity_name', 'users'):
            with pytest.raises(tool.ManagerError) as exc:
                self.connector.load_remote()
            assert exc.value[0] == 'Undefined API command users_find'

    def test_load_remote_entities(self):
        self._create_connector()
        tool.api.Command.__getitem__.side_effect = self._api_call
        self.connector.load_remote()
        assert self.connector.remote == {
            'group': {'group-one': {'cn': ('group-one',)}},
            'hbacrule': {'rule-one': {'cn': ('rule-one',)}},
            'hostgroup': {'group-one': {'cn': ('group-one',)}},
            'sudorule': {'rule-one': {'cn': ('rule-one',)}},
            'user': {'user.one': {'uid': ('user.one',)}}}

    def test_parse_entity_diff_add(self):
        self._create_connector()
        entity = entities.FreeIPAUser(
            'test.user', {'firstName': 'Test', 'lastName': 'User'})
        self.connector.remote = {'user': dict(), 'group': dict()}
        self.connector.commands = []
        self.connector._parse_entity_diff(entity)
        assert len(self.connector.commands) == 1
        cmd = self.connector.commands[0]
        assert cmd.command == 'user_add'
        assert cmd.description == (
            'user_add test.user (givenname=Test; sn=User)')
        assert cmd.payload == {
            'givenname': u'Test', 'sn': u'User', 'uid': u'test.user'}

    def test_parse_entity_diff_mod(self):
        self._create_connector()
        entity = entities.FreeIPAUser(
            'test.user',
            {'firstName': 'Test', 'lastName': 'User',
             'githubLogin': ['gh1', 'gh2']})
        self.connector.remote = {
            'user': {
                'test.user': {
                    'mail': (u'test.user@gooddata.com',),
                    'carlicense': (u'gh1',)}},
            'group': dict()}
        self.connector.commands = []
        self.connector._parse_entity_diff(entity)
        assert len(self.connector.commands) == 1
        cmd = self.connector.commands[0]
        assert cmd.command == 'user_mod'
        assert cmd.description == (
            "user_mod test.user (carlicense=(u'gh1', u'gh2'); "
            "givenname=Test; mail=(); sn=User)")
        assert cmd.payload == {
            'carlicense': (u'gh1', u'gh2'), 'givenname': u'Test',
            'mail': (), 'sn': u'User', 'uid': u'test.user'}

    def test_parse_entity_diff_memberof_add(self):
        self._create_connector()
        self.connector.local = {
            'user': {
                'test.user': entities.FreeIPAUser(
                    'test.user',
                    {'firstName': 'Test', 'lastName': 'User',
                     'memberOf': {'group': ['group-one']}})},
            'group': {'group-one': entities.FreeIPAUserGroup('group-one', {})}}
        self.connector.remote = {
            'user': {'test.user': {
                'uid': ('test.user',),
                'givenname': (u'Test',), 'sn': (u'User',)}},
            'group': {'group-one': {'cn': ('group-one',)}}}
        self.connector.commands = []
        self.connector._parse_entity_diff(
            self.connector.local['user']['test.user'])
        assert len(self.connector.commands) == 1
        cmd = self.connector.commands[0]
        assert cmd.command == 'group_add_member'
        assert cmd.description == (
            'group_add_member group-one (user=test.user)')
        assert cmd.payload == {'cn': u'group-one', 'user': u'test.user'}

    def test_parse_entity_diff_memberof_remove(self):
        self._create_connector()
        self.connector.local = {
            'user': {'test.user': entities.FreeIPAUser(
                'test.user', {'firstName': 'Test', 'lastName': 'User'})},
            'group': {'group-one': entities.FreeIPAUserGroup('group-one', {})}}
        self.connector.remote = {
            'user': {'test.user': {
                'uid': ('test.user',),
                'givenname': (u'Test',), 'sn': (u'User',)}},
            'group': {
                'group-one': {
                    'cn': ('group-one',), 'member_user': ('test.user',)}}}
        self.connector.commands = []
        self.connector._parse_entity_diff(
            self.connector.local['user']['test.user'])
        assert len(self.connector.commands) == 1
        cmd = self.connector.commands[0]
        assert cmd.command == 'group_remove_member'
        assert cmd.description == (
            'group_remove_member group-one (user=test.user)')
        assert cmd.payload == {'cn': u'group-one', 'user': u'test.user'}

    def test_prepare_commands_same(self):
        self._create_connector()
        self.connector.local = {
            'user': {
                'test.user': entities.FreeIPAUser(
                    'test.user', {'firstName': 'Test', 'lastName': 'User',
                                  'memberOf': {'group': ['group-one']}})},
            'group': {'group-one': entities.FreeIPAUserGroup('group-one', {})}}
        self.connector.remote = {
            'user': {
                'test.user': {
                    'uid': ('test.user',),
                    'givenname': (u'Test',), 'sn': (u'User',)}},
            'group': {'group-one': {
                'cn': ('group-one',), 'member_user': ('test.user',)}}}
        self.connector._prepare_commands()
        assert len(self.connector.commands) == 0

    @log_capture('IpaConnector', level=logging.INFO)
    def test_prepare_commands_changes_addonly(self, captured_log):
        self._create_connector(force=True)
        self.connector.local = {
            'user': {
                'test.user': entities.FreeIPAUser(
                    'test.user',
                    {'firstName': 'Test', 'lastName': 'User',
                     'memberOf': {'group': ['group-one']}})},
            'group': {'group-one': entities.FreeIPAUserGroup('group-one', {})},
            'sudorule': {
                'rule-one': entities.FreeIPASudoRule(
                    'rule-one',
                    {'options': ['!test'], 'memberUser': 'group-one'})}}
        self.connector.remote = {
            'group': {'group-one': {'cn': ('group-one',)}},
            'sudorule': dict(), 'user': dict()}
        self.connector._prepare_commands()
        assert len(self.connector.commands) == 5
        assert [i.command for i in sorted(self.connector.commands)] == [
            'sudorule_add', 'user_add', 'group_add_member',
            'sudorule_add_option', 'sudorule_add_user']
        captured_log.check(('IpaConnector', 'INFO', '5 commands to execute'))

    def test_prepare_commands_changes_deletion_enabled(self):
        self._create_connector(enable_deletion=True)
        self.connector.local = {
            'user': {
                'test.user': entities.FreeIPAUser(
                    'test.user',
                    {'firstName': 'Test', 'lastName': 'User',
                     'memberOf': {'group': ['group-one']}})},
            'group': {'group-one': entities.FreeIPAUserGroup('group-one', {})},
            'sudorule': {'rule-one': entities.FreeIPASudoRule(
                'rule-one', {'options': ['!test'], 'memberUser': 'group-one'})}
        }
        self.connector.remote = {
            'group': {
                'group-one': {'cn': (u'group-one',)},
                'group-two': {'cn': (u'group-two',)}},
            'user': dict(),
            'sudorule': dict()}
        self.connector._prepare_commands()
        assert len(self.connector.commands) == 6
        assert [i.command for i in sorted(self.connector.commands)] == [
            'sudorule_add', 'user_add', 'group_add_member',
            'sudorule_add_option', 'sudorule_add_user', 'group_del']

    def test_prepare_commands_memberof_add_new_group(self):
        self._create_connector(debug=True)
        self.connector.local = {
            'user': {
                'test.user': entities.FreeIPAUser(
                    'test.user',
                    {'firstName': 'Test', 'lastName': 'User',
                     'memberOf': {'group': ['group-one']}})},
            'group': {
                'group-one': entities.FreeIPAUserGroup('group-one', {})}}
        self.connector.remote = {
            'user': {
                'test.user': {
                    'uid': ('test.user',),
                    'givenname': (u'Test',), 'sn': (u'User',)}},
            'group': dict()}
        self.connector._prepare_commands()
        assert len(self.connector.commands) == 2
        assert [i.command for i in sorted(self.connector.commands)] == [
            'group_add', 'group_add_member']

    def test_prepare_deletion_commands(self):
        self._create_connector()
        self.connector.local = dict()
        self.connector.remote = {
            'user': {
                'test.user': {'uid': ('test.user',)}
            }
        }
        self.connector.commands = []
        self.connector._prepare_deletion_commands()
        assert len(self.connector.commands) == 1
        cmd = self.connector.commands[0]
        assert cmd.command == 'user_del'
        assert cmd.description == 'user_del test.user ()'
        assert cmd.payload == {'uid': u'test.user'}

    def test_add_command(self):
        self._create_connector()
        cmd = tool.Command(
            'test_cmd', {'description': ('Test',)}, 'group1', 'cn')
        assert cmd.payload == {'cn': u'group1', 'description': u'Test'}
        for key in ('cn', 'description'):
            assert isinstance(cmd.payload[key], unicode)
        assert cmd.description == 'test_cmd group1 (description=Test)'

    def test_command_ordering(self):
        for i in ('user', 'group', 'hostgroup', 'hbacrule', 'sudorule'):
            assert tool.Command('%s_add' % i, {}, '', '') < tool.Command(
                '%s_add_whatever' % i, {}, '', '')

    @log_capture('IpaConnector', level=logging.INFO)
    def test_execute_update_dry_run(self, captured_log):
        self._create_connector()
        self.connector.execute_update()
        captured_log.check(
            ('IpaConnector', 'INFO', '0 commands to execute'),
            ('IpaConnector', 'INFO',
             'FreeIPA consistent with local config, nothing to do'))

    @log_capture('IpaConnector', level=logging.INFO)
    def test_execute_update_no_todo(self, captured_log):
        self._create_connector(force=True)
        self.connector.execute_update()
        captured_log.check(
            ('IpaConnector', 'INFO', '0 commands to execute'),
            ('IpaConnector', 'INFO',
             'FreeIPA consistent with local config, nothing to do'))
        assert self.connector.commands == []

    def test_execute_update_threshold_exceeded(self):
        self._create_connector(force=True, threshold=10)
        self.connector.remote_count = 100
        self.connector.commands = [
            tool.Command('cmd%d' % i, {}, '', '') for i in range(1, 12)]
        with mock.patch('ipa_connector.IpaConnector._prepare_commands'):
            with pytest.raises(tool.ManagerError) as exc:
                self.connector.execute_update()
        assert exc.value[0] == 'Threshold exceeded (11.00 % > 10 %), aborting'

    @log_capture('Command', level=logging.INFO)
    def test_execute_update(self, captured_log):
        self._create_connector(force=True, threshold=15)
        tool.api.Command.__getitem__.side_effect = self._api_call
        self.connector.commands = self._large_commands()
        with mock.patch('ipa_connector.IpaConnector._prepare_commands'):
            with mock.patch('ipa_connector.IpaConnector._check_threshold'):
                self.connector.execute_update()
        captured_log.check(
            ('Command', 'INFO', 'Executing group_add group1 ()'),
            ('Command', 'INFO', u'Added group "group1"'),
            ('Command', 'INFO', 'Executing group_add group2 ()'),
            ('Command', 'INFO', u'Added group "group2"'),
            ('Command', 'INFO', 'Executing hbacrule_add rule1 ()'),
            ('Command', 'INFO', u'Added hbacrule "rule1"'),
            ('Command', 'INFO', 'Executing hostgroup_add group1 ()'),
            ('Command', 'INFO', u'Added hostgroup "group1"'),
            ('Command', 'INFO', 'Executing sudorule_add rule1 ()'),
            ('Command', 'INFO', u'Added sudorule "rule1"'),
            ('Command', 'INFO', 'Executing user_add user1 ()'),
            ('Command', 'INFO', u'Added user "user1"'),
            ('Command', 'INFO', 'Executing user_add user2 ()'),
            ('Command', 'INFO', u'Added user "user2"'),
            ('Command', 'INFO',
             u'Executing group_add_member group1 (user=user1)'),
            ('Command', 'INFO',
             u'group_add_member group1 (user=user1) successful'),
            ('Command', 'INFO',
             u'Executing group_add_member group1-users (user=user2)'),
            ('Command', 'INFO',
             u'group_add_member group1-users (user=user2) successful'),
            ('Command', 'INFO',
             u'Executing group_add_member group2 (group=group1)'),
            ('Command', 'INFO',
             u'group_add_member group2 (group=group1) successful'),
            ('Command', 'INFO',
             u'Executing hbacrule_add_host rule1 (hostgroup=group1)'),
            ('Command', 'INFO',
             u'hbacrule_add_host rule1 (hostgroup=group1) successful'),
            ('Command', 'INFO',
             u'Executing hbacrule_add_user rule1 (group=group2)'),
            ('Command', 'INFO',
             u'hbacrule_add_user rule1 (group=group2) successful'),
            ('Command', 'INFO',
             u'Executing sudorule_add_host rule1 (hostgroup=group1)'),
            ('Command', 'INFO',
             u'sudorule_add_host rule1 (hostgroup=group1) successful'),
            ('Command', 'INFO',
             u'Executing sudorule_add_user rule1 (group=group2)'),
            ('Command', 'INFO',
             u'sudorule_add_user rule1 (group=group2) successful'))
        assert self.connector.errs == []

    @log_capture('Command', level=logging.ERROR)
    def test_execute_update_errors(self, captured_log):
        self._create_connector(force=True, threshold=15)
        tool.api.Command.__getitem__.side_effect = (
            self._api_call_unreliable)
        self.connector.commands = self._large_commands()
        with mock.patch('ipa_connector.IpaConnector._prepare_commands'):
            with mock.patch('ipa_connector.IpaConnector._check_threshold'):
                with pytest.raises(tool.ManagerError) as exc:
                    self.connector.execute_update()
        assert exc.value[0] == 'There were 5 errors executing update'
        assert self.connector.errs == [
            (u'group_add_member group1 (user=user1)',
             "Error executing group_add_member: [u'- test: no such attr2']"),
            (u'group_add_member group1-users (user=user2)',
             "Error executing group_add_member: [u'- test: no such attr2']"),
            (u'group_add_member group2 (group=group1)',
             "Error executing group_add_member: [u'- test: no such attr2']"),
            (u'hbacrule_add_user rule1 (group=group2)',
             "Error executing hbacrule_add_user: [u'- test: no such attr2']"),
            (u'sudorule_add_user rule1 (group=group2)',
             "Error executing sudorule_add_user: [u'- test: no such attr2']")]
        captured_log.check(
            ('Command', 'ERROR',
             u'group_add_member group1 (user=user1) failed:'),
            ('Command', 'ERROR', u'- test: no such attr2'),
            ('Command', 'ERROR',
             u'group_add_member group1-users (user=user2) failed:'),
            ('Command', 'ERROR', u'- test: no such attr2'),
            ('Command', 'ERROR',
             u'group_add_member group2 (group=group1) failed:'),
            ('Command', 'ERROR', u'- test: no such attr2'),
            ('Command', 'ERROR',
             u'hbacrule_add_user rule1 (group=group2) failed:'),
            ('Command', 'ERROR', u'- test: no such attr2'),
            ('Command', 'ERROR',
             u'sudorule_add_user rule1 (group=group2) failed:'),
            ('Command', 'ERROR', u'- test: no such attr2'))

    def test_execute_update_exceptions(self):
        self._create_connector(force=True, threshold=15)
        tool.api.Command.__getitem__.side_effect = (
            self._api_call_execute_fail)
        self.connector.commands = self._large_commands()
        with mock.patch('ipa_connector.IpaConnector._prepare_commands'):
            with mock.patch('ipa_connector.IpaConnector._check_threshold'):
                with pytest.raises(tool.ManagerError) as exc:
                    self.connector.execute_update()
        assert exc.value[0] == 'There were 3 errors executing update'
        assert self.connector.errs == [
            (u'group_add_member group1 (user=user1)',
             'Error executing group_add_member: Some error happened'),
            (u'group_add_member group1-users (user=user2)',
             'Error executing group_add_member: Some error happened'),
            (u'group_add_member group2 (group=group1)',
             'Error executing group_add_member: Some error happened')]

    def test_execute_update_invalid_command(self):
        self._create_connector(force=True, threshold=15)
        tool.api.Command.__getitem__.side_effect = self._api_call
        self.connector.commands = [tool.Command('non_existent', {}, 'x', 'cn')]
        with mock.patch('ipa_connector.IpaConnector._prepare_commands'):
            with mock.patch('ipa_connector.IpaConnector._check_threshold'):
                with pytest.raises(tool.ManagerError) as exc:
                    self.connector.execute_update()
        assert exc.value[0] == 'There were 1 errors executing update'
        assert self.connector.errs == [
            ('non_existent x ()', 'Non-existent command non_existent')]

    def _api_call(self, command):
        return {
            'group_find': self._api_group_find,
            'hbacrule_find': self._api_hbacrule_find,
            'hostgroup_find': self._api_hostgroup_find,
            'sudorule_find': self._api_sudorule_find,
            'user_find': self._api_user_find,
            'user_add': self._api_user_add,
            'group_add': self._api_add('group'),
            'hostgroup_add': self._api_add('hostgroup'),
            'hbacrule_add': self._api_add('hbacrule'),
            'sudorule_add': self._api_add('sudorule'),
            'group_add_member': self._api_nosummary,
            'hbacrule_add_user': self._api_nosummary,
            'hbacrule_add_host': self._api_nosummary,
            'sudorule_add_user': self._api_nosummary,
            'sudorule_add_host': self._api_nosummary
        }[command]

    def _api_call_unreliable(self, command):
        try:
            return {
                'group_add_member': self._api_fail,
                'hbacrule_add_user': self._api_fail,
                'sudorule_add_user': self._api_fail
            }[command]
        except KeyError:
            return self._api_call(command)

    def _api_call_find_fail(self, command):
        if command.endswith('find'):
            return self._api_exc
        return self._api_call(command)

    def _api_call_execute_fail(self, command):
        if command == 'group_add_member':
            return self._api_exc
        return self._api_call(command)

    def _api_group_find(self, **kwargs):
        return {'result': [{'cn': ('group-one',)}]}

    def _api_hbacrule_find(self, **kwargs):
        return {'result': [{'cn': ('rule-one',)}]}

    def _api_hostgroup_find(self, **kwargs):
        return {'result': [{'cn': ('group-one',)}]}

    def _api_sudorule_find(self, **kwargs):
        return {'result': [{'cn': ('rule-one',)}]}

    def _api_user_find(self, **kwargs):
        return {'result': [{'uid': ('user.one',)}]}

    def _api_user_add(self, **kwargs):
        return {'summary': u'Added user "%s"' % kwargs.get('uid')}

    def _api_add(self, name):
        def _func(**kwargs):
            return {'summary': u'Added %s "%s"' % (name, kwargs.get('cn'))}
        return _func

    def _api_nosummary(self, **kwargs):
            return {u'failed': {u'attr1': {'param1': (), 'param2': ()}}}

    def _api_fail(self, **kwargs):
            return {
                u'failed': {
                    u'attr1': {'param1': ((u'test', u'no such attr2'),)}}}

    def _api_exc(self, **kwargs):
        raise Exception('Some error happened')

    def _large_commands(self):
        return [
            tool.Command('user_add', {}, 'user1', 'uid'),
            tool.Command('user_add', {}, 'user2', 'uid'),
            tool.Command('group_add', {}, 'group1', 'cn'),
            tool.Command('group_add', {}, 'group2', 'cn'),
            tool.Command('hostgroup_add', {}, 'group1', 'cn'),
            tool.Command('hbacrule_add', {}, 'rule1', 'cn'),
            tool.Command('sudorule_add', {}, 'rule1', 'cn'),
            tool.Command(
                'group_add_member', {'user': u'user1'}, 'group1', 'cn'),
            tool.Command(
                'group_add_member', {'group': u'group1'}, 'group2', 'cn'),
            tool.Command(
                'group_add_member', {'user': u'user2'}, 'group1-users', 'cn'),
            tool.Command(
                'hbacrule_add_user', {'group': u'group2'}, 'rule1', 'cn'),
            tool.Command(
                'hbacrule_add_host', {'hostgroup': u'group1'}, 'rule1', 'cn'),
            tool.Command(
                'sudorule_add_user', {'group': u'group2'}, 'rule1', 'cn'),
            tool.Command(
                'sudorule_add_host', {'hostgroup': u'group1'}, 'rule1', 'cn')
        ]
