import logging
import mock
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(testpath, '..'))

import ipamanager.freeipa_manager as tool
import ipamanager.errors as errors
sys.modules['ipalib'] = mock.Mock()
ipa_connector = __import__('ipamanager.ipa_connector')
modulename = 'ipamanager.freeipa_manager'


class TestFreeIPAManagerBase(object):
    def _init_tool(self, args):
        with mock.patch.object(sys, 'argv', ['manager'] + args):
            return tool.FreeIPAManager()


class TestFreeIPAManagerRun(TestFreeIPAManagerBase):
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
                    'ipamanager.ipa_connector.IpaConnector') as mock_conn:
                manager.run()
                # entities, threshold, force, enable deletion, debug
                mock_conn.assert_called_with({}, 10, True, False, True)

    def test_run_push_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(
                ['push', '--force', '--enable-deletion', '-t', '10', '-v'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaConnector') as mock_conn:
                manager.run()
                # entities, threshold, force, enable deletion, debug
                mock_conn.assert_called_with({}, 10, True, True, True)

    def test_run_push_dry_run(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaConnector') as mock_conn:
                manager.run()
                # entities, threshold, force, enable deletion, debug
                mock_conn.assert_called_with({}, 20, False, False, False)

    def test_run_push_dry_run_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', '--enable-deletion'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaConnector') as mock_conn:
                manager.run()
                # entities, threshold, force, enable deletion, debug
                mock_conn.assert_called_with({}, 20, False, True, False)

    def test_run_pull(self):
        manager = self._init_tool(['pull'])
        with pytest.raises(NotImplementedError) as exc:
            manager.run()
        assert exc.value[0] == 'Config pulling not available yet.'
