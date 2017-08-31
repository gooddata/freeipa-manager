import logging
import mock
import pytest
import sys
from testfixtures import log_capture

from _utils import _import
sys.modules['ipalib'] = mock.Mock()
tool = _import('ipamanager', 'freeipa_manager')
errors = _import('ipamanager', 'errors')
ipa_connector = _import('ipamanager', 'ipa_connector')
modulename = 'ipamanager.freeipa_manager'


class TestFreeIPAManagerBase(object):
    def _init_tool(self, args):
        with mock.patch.object(sys, 'argv', ['manager'] + args):
            return tool.FreeIPAManager()


class TestFreeIPAManagerRun(TestFreeIPAManagerBase):
    def test_run_threshold_bad_type(self, capsys):
        with pytest.raises(SystemExit) as exc:
            self._init_tool(['check', 'config_path', '-t', '42a'])
        assert exc.value[0] == 2
        _, err = capsys.readouterr()
        assert ("manager: error: argument -t/--threshold: invalid literal "
                "for int() with base 10: '42a'") in err

    def test_run_threshold_bad_range(self, capsys):
        with pytest.raises(SystemExit) as exc:
            self._init_tool(['check', 'config_path', '-t', '102'])
        assert exc.value[0] == 2
        _, err = capsys.readouterr()
        assert ("manager: error: argument -t/--threshold: "
                "must be a number in range 1-100") in err

    @mock.patch('%s.IntegrityChecker' % modulename)
    @mock.patch('%s.ConfigLoader' % modulename)
    def test_run_check(self, mock_config, mock_check):
        manager = self._init_tool(['check', 'config_path', '-r', 'rules_path'])
        manager.run()
        mock_config.assert_called_with('config_path', None)
        mock_check.assert_called_with(
            'rules_path', manager.config_loader.entities)

    @log_capture('FreeIPAManager', level=logging.ERROR)
    def test_run_check_error(self, captured_errors):
        with mock.patch('%s.ConfigLoader.load' % modulename) as mock_load:
            mock_load.side_effect = errors.ConfigError('Error loading config')
            with pytest.raises(SystemExit) as exc:
                self._init_tool(['check', 'nonexistent_config_path']).run()
        assert exc.value[0] == 1
        captured_errors.check(
            ('FreeIPAManager', 'ERROR', 'Error loading config'))

    def test_run_push(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(
                ['push', '--force', '-t', '10', '-v'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with({}, 10, True, False)

    def test_run_push_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(
                ['push', '--force', '--enable-deletion', '-t', '10', '-v'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with({}, 10, True, True)

    def test_run_push_dry_run(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with({}, 20, False, False)

    def test_run_push_dry_run_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', '--enable-deletion'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with({}, 20, False, True)

    def test_run_pull(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull', '--force', '-v'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with(
                {}, '/opt/freeipa-manager/entities', True, False)
            manager.downloader.pull.assert_called()
