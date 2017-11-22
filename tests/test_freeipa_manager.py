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
        mock_config.assert_called_with(
            'config_path', '/opt/freeipa-manager/ignored.yaml')
        mock_check.assert_called_with(
            '/opt/freeipa-manager/rules.yaml', manager.config_loader.entities)

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
                mock_conn.assert_called_with({}, 10, True, False)

    def test_run_push_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', 'config_repo', '-fdt', '10'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with({}, 10, True, True)

    def test_run_push_dry_run(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', 'config_repo'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with({}, 10, False, False)

    def test_run_push_dry_run_enable_deletion(self):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['push', 'config_repo', '--deletion'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaUploader') as mock_conn:
                manager.run()
                mock_conn.assert_called_with({}, 10, False, True)

    @mock.patch('%s.GitHubForwarder' % modulename)
    def test_run_pull(self, mock_fwd):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull', 'dump_repo'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with({}, 'dump_repo', False, False)
            mock_fwd.assert_called_with('dump_repo', 'master', None)
            manager.forwarder.checkout_base.assert_not_called()
            manager.downloader.pull.assert_called_with()
            assert not manager.args.commit
            manager.forwarder.commit.assert_not_called()
            assert not manager.args.pull_request
            manager.forwarder.create_pull_request.assert_not_called()

    @mock.patch('%s.GitHubForwarder' % modulename)
    def test_run_pull_dry_run(self, mock_fwd):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull', 'dump_repo', '--dry-run'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with({}, 'dump_repo', True, False)
            mock_fwd.assert_called_with('dump_repo', 'master', None)
            manager.forwarder.checkout_base.assert_not_called()
            manager.downloader.pull.assert_called()
            assert not manager.args.commit
            assert not manager.args.pull_request

    @mock.patch('%s.GitHubForwarder' % modulename)
    def test_run_pull_add_only(self, mock_fwd):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull', 'dump_repo', '--add-only'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with({}, 'dump_repo', False, True)
            mock_fwd.assert_called_with('dump_repo', 'master', None)
            manager.forwarder.checkout_base.assert_not_called()
            manager.downloader.pull.assert_called()
            assert not manager.args.commit
            assert not manager.args.pull_request

    @mock.patch('%s.GitHubForwarder' % modulename)
    def test_run_pull_commit(self, mock_fwd):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull-commit', '-vv', 'dump_repo'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with({}, 'dump_repo', False, False)
            mock_fwd.assert_called_with('dump_repo', 'master', None)
            manager.forwarder.checkout_base.assert_called_with()
            manager.downloader.pull.assert_called()
            assert manager.args.commit
            assert not manager.args.pull_request
            assert manager.args.loglevel == logging.DEBUG
            manager.forwarder.commit.assert_called_with()

    @mock.patch('%s.GitHubForwarder' % modulename)
    def test_run_pull_request(self, mock_fwd):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(['pull-request', '-v', 'dump_repo'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with({}, 'dump_repo', False, False)
            mock_fwd.assert_called_with('dump_repo', 'master', None)
            manager.forwarder.checkout_base.assert_called_with()
            manager.downloader.pull.assert_called()
            assert manager.args.commit
            assert manager.args.pull_request
            manager.forwarder.commit.assert_called_with()
            manager.forwarder.create_pull_request.assert_called_with(
                'gooddata', 'freeipa-manager-config', 'yenkins', None)

    @mock.patch('%s.GitHubForwarder' % modulename)
    def test_run_pull_request_branch(self, mock_fwd):
        with mock.patch('%s.FreeIPAManager.check' % modulename):
            manager = self._init_tool(
                ['pull-request', '-v', 'dump_repo', '-b', 'branch1'])
            manager.integrity_checker = mock.Mock()
            manager.integrity_checker.entity_dict = dict()
            with mock.patch(
                    'ipamanager.ipa_connector.IpaDownloader') as mock_conn:
                manager.run()
            mock_conn.assert_called_with({}, 'dump_repo', False, False)
            mock_fwd.assert_called_with('dump_repo', 'master', 'branch1')
            manager.forwarder.checkout_base.assert_called_with()
            manager.downloader.pull.assert_called()
            assert manager.args.commit
            assert manager.args.pull_request
            manager.forwarder.commit.assert_called_with()
            manager.forwarder.create_pull_request.assert_called_with(
                'gooddata', 'freeipa-manager-config', 'yenkins', None)
