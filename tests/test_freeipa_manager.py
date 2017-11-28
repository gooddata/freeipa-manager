import logging
import mock
import os
import pytest
import sys
from testfixtures import log_capture

from _utils import _import
sys.modules['ipalib'] = mock.Mock()
tool = _import('ipamanager', 'freeipa_manager')
errors = _import('ipamanager', 'errors')
entities = _import('ipamanager', 'entities')
utils = _import('ipamanager', 'utils')
ipa_connector = _import('ipamanager', 'ipa_connector')
modulename = 'ipamanager.freeipa_manager'
SETTINGS = os.path.join(
    os.path.dirname(__file__), 'freeipa-manager-config/settings.yaml')
SETTINGS_INVALID = os.path.join(
    os.path.dirname(__file__), 'freeipa-manager-config/settings_invalid.yaml')


class TestFreeIPAManagerBase(object):
    def _init_tool(self, args, settings=SETTINGS):
        cmd_args = ['manager'] + args + ['-s', settings]
        with mock.patch.object(sys, 'argv', cmd_args):
            return tool.FreeIPAManager()


class TestFreeIPAManagerRun(TestFreeIPAManagerBase):
    def test_run_threshold_bad_type(self, capsys):
        with pytest.raises(SystemExit) as exc:
            self._init_tool(['push', 'config_path', '-t', '42a'])
        assert exc.value[0] == 2
        _, err = capsys.readouterr()
        assert ("manager push: error: argument -t/--threshold: invalid "
                "literal for int() with base 10: '42a'") in err

    def test_run_threshold_bad_range(self, capsys):
        with pytest.raises(SystemExit) as exc:
            self._init_tool(['push', 'config_path', '-t', '102'])
        assert exc.value[0] == 2
        _, err = capsys.readouterr()
        assert ("manager push: error: argument -t/--threshold: "
                "must be a number in range 1-100") in err

    @mock.patch('%s.IntegrityChecker' % modulename)
    @mock.patch('%s.ConfigLoader' % modulename)
    def test_run_check(self, mock_config, mock_check):
        manager = self._init_tool(['check', 'config_path', '-v'])
        manager.run()
        mock_config.assert_called_with('config_path', manager.settings)
        mock_check.assert_called_with(
            manager.config_loader.entities, manager.settings)

    @log_capture('FreeIPAManager', level=logging.ERROR)
    def test_run_check_error(self, captured_errors):
        with mock.patch('%s.ConfigLoader.load' % modulename) as mock_load:
            mock_load.side_effect = errors.ConfigError('Error loading config')
            with pytest.raises(SystemExit) as exc:
                self._init_tool(['check', 'nonexistent']).run()
        assert exc.value[0] == 1
        captured_errors.check(
            ('FreeIPAManager', 'ERROR', 'Error loading config'))

    def test_run_push(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', 'config_repo', '-ft', '10'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with(
                    manager.settings, {}, 10, True, False)

    def test_run_push_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', 'config_repo', '-fdt', '10'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with(
                    manager.settings, {}, 10, True, True)

    def test_run_push_dry_run(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', 'config_repo'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with(
                    manager.settings, {}, 10, False, False)

    def test_run_push_dry_run_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', 'config_repo', '--deletion'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with(
                    manager.settings, {}, 10, False, True)

    def test_run_pull(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull', 'dump_repo'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with(
                manager.settings, {}, 'dump_repo', False, False)
            manager.downloader.pull.assert_called_with()

    def test_run_pull_dry_run(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull', 'dump_repo', '--dry-run'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with(
                manager.settings, {}, 'dump_repo', True, False)
            manager.downloader.pull.assert_called()

    def test_run_pull_add_only(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull', 'dump_repo', '--add-only'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with(
                manager.settings, {}, 'dump_repo', False, True)
            manager.downloader.pull.assert_called()

    def test_load_settings(self):
        assert self._init_tool(['check', 'dump_repo']).settings == {
            'ignore': {'group': ['ipausers', 'test.*'], 'user': ['admin']},
            'user-group-pattern': '^role-.+|.+-users$'}

    def test_load_settings_not_found(self):
        with mock.patch('__builtin__.open') as mock_open:
            mock_open.side_effect = IOError('[Errno 2] No such file or dir')
            with pytest.raises(tool.ManagerError) as exc:
                self._init_tool(['check', 'dump_repo'])
        assert exc.value[0] == (
            'Error reading settings file: [Errno 2] No such file or dir')

    def test_load_settings_invalid_ignore_key(self):
        with pytest.raises(tool.ManagerError) as exc:
            self._init_tool(['check', 'dump_repo'], settings=SETTINGS_INVALID)
        assert exc.value[0] == (
            "Error reading settings file: extra keys "
            "not allowed @ data['ignore']['groups']")
