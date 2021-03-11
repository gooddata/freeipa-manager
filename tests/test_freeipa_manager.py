#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import logging
import mock
import os
import pytest
import socket
import sys
from testfixtures import log_capture, LogCapture, StringComparison

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
SETTINGS_ALERTING = os.path.join(
    os.path.dirname(__file__), 'freeipa-manager-config/settings_alerting.yaml')
SETTINGS_INCLUDE = os.path.join(
    os.path.dirname(__file__), 'freeipa-manager-config/settings_include.yaml')
SETTINGS_MERGE_INCLUDE = os.path.join(
    os.path.dirname(__file__), 'freeipa-manager-config/settings_merge.yaml')
SETTINGS_INVALID = os.path.join(
    os.path.dirname(__file__), 'freeipa-manager-config/settings_invalid.yaml')


class TestFreeIPAManagerBase(object):
    def _init_tool(self, args, settings=SETTINGS):
        cmd_args = ['manager'] + args + ['-s', settings]
        with mock.patch.object(sys, 'argv', cmd_args):
            return tool.FreeIPAManager()


class TestFreeIPAManagerRun(TestFreeIPAManagerBase):
    @mock.patch('%s.importlib.import_module' % modulename)
    def test_register_alerting_no_modules(self, mock_import):
        manager = self._init_tool(['check', 'path', '-v'])
        with mock.patch('%s.logging.RootLogger.addHandler' % modulename) as ma:
            with LogCapture() as log:
                manager._register_alerting()
        mock_import.assert_not_called()
        ma.assert_not_called()
        log.check(('FreeIPAManager', 'INFO',
                   'No alerting plugins configured in settings'))

    @mock.patch('%s.logging.RootLogger.addHandler' % modulename)
    @mock.patch('%s.importlib.import_module' % modulename)
    def test_register_alerting_configured(self, mock_import, mock_add):
        manager = self._init_tool(['check', 'config_path', '-v'])
        manager.settings['alerting'] = {
            'monitoring1': {
                'module': 'monitoring1', 'class': 'TestMonitoringPlugin',
                'config': {'k1': 'v1', 'k2': 'v2'}
            },
            'dummy': {
                'module': 'test', 'class': 'DummyAlertingPlugin'
            }
        }
        with LogCapture() as log:
            manager._register_alerting()
        mock_import.assert_has_calls([
            mock.call('ipamanager.alerting.monitoring1'),
            mock.call('ipamanager.alerting.test')], any_order=True)
        plugin1 = mock_import(
            'ipamanager.alerting.monitoring1').TestMonitoringPlugin
        plugin1.assert_called_with({'k1': 'v1', 'k2': 'v2'})
        plugin2 = mock_import('ipamanager.alerting.test').DummyAlertingPlugin
        plugin2.assert_called_with({})
        instances = {p.return_value for p in (plugin1, plugin2)}
        mock_add.assert_has_calls(
            [mock.call(i) for i in instances], any_order=True)
        assert set(manager.alerting_plugins) == instances
        log.check_present(
            ('FreeIPAManager', 'DEBUG', 'Registering 2 alerting plugins'),
            ('FreeIPAManager', 'DEBUG', StringComparison(
                "Registered plugin .*TestMonitoringPlugin.*")),
            ('FreeIPAManager', 'DEBUG', StringComparison(
                "Registered plugin .*DummyAlertingPlugin.*")),
            order_matters=False)

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

    @log_capture('FreeIPAManager', level=logging.INFO)
    @mock.patch('%s.IntegrityChecker' % modulename)
    @mock.patch('%s.ConfigLoader' % modulename)
    def test_run_check(self, mock_config, mock_check, log):
        manager = self._init_tool(['check', 'config_path', '-v'])
        manager.run()
        mock_config.assert_called_with('config_path', manager.settings, True)
        mock_check.assert_called_with(
            manager.config_loader.load.return_value, manager.settings)
        log.check(('FreeIPAManager', 'INFO',
                   'No alerting plugins configured in settings'))

    @mock.patch('%s.IntegrityChecker' % modulename)
    @mock.patch('%s.ConfigLoader' % modulename)
    @mock.patch('%s.logging.RootLogger.addHandler' % modulename)
    @mock.patch('%s.importlib.import_module' % modulename)
    def test_run_check_alerting_configured(self, mock_import, mock_add,
                                           mock_config, mock_check):
        manager = self._init_tool(['check', 'config_path', '-v'])
        manager.settings['alerting'] = {
            'monitoring1': {
                'module': 'monitoring1', 'class': 'TestMonitoringPlugin',
                'config': {'k1': 'v1', 'k2': 'v2'}
            },
            'dummy': {
                'module': 'test', 'class': 'DummyAlertingPlugin',
                'config': {'key': 'value', 'k2': 42}
            }
        }
        manager.run()
        mock_config.assert_called_with('config_path', manager.settings, True)
        mock_check.assert_called_with(
            manager.config_loader.load.return_value, manager.settings)
        plugin1 = mock_import(
            'ipamanager.alerting.monitoring1').TestMonitoringPlugin()
        plugin1.dispatch.assert_called_with()
        plugin2 = mock_import('ipamanager.alerting.test').DummyAlertingPlugin()
        plugin2.dispatch.assert_called_with()

    @log_capture('FreeIPAManager', level=logging.ERROR)
    @mock.patch('%s.importlib.import_module' % modulename)
    def test_run_register_alerting_error(self, mock_import, captured_errors):
        mock_import.side_effect = ImportError('no such module')
        manager = self._init_tool(['check', 'path'])
        manager.settings['alerting'] = {'test': {'module': 'b', 'class': 'c'}}
        with pytest.raises(SystemExit) as exc:
            manager.run()
        assert exc.value[0] == 1
        captured_errors.check(
            ('FreeIPAManager', 'ERROR',
             'Could not register alerting plugin test: no such module'))

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
        with mock.patch('ipamanager.ipa_connector.IpaUploader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['push', 'config_repo', '-ft', '10'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(
            manager.settings, {}, 10, True, False, False, [])

    def test_run_push_enable_deletion(self):
        with mock.patch('ipamanager.ipa_connector.IpaUploader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['push', 'repo_path', '-fdt', '10'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(
            manager.settings, {}, 10, True, True, False, [])

    def test_run_push_dry_run(self):
        with mock.patch('ipamanager.ipa_connector.IpaUploader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['push', 'config_repo'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(
            manager.settings, {}, 10, False, False, False, [])

    def test_run_push_dry_run_enable_deletion(self):
        with mock.patch('ipamanager.ipa_connector.IpaUploader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['push', 'config_repo', '-d'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(
            manager.settings, {}, 10, False, True, False, [])

    def test_run_pull(self):
        with mock.patch('ipamanager.ipa_connector.IpaDownloader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['pull', 'dump_repo'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(manager.settings, manager.entities,
                                     'dump_repo', False, False, ['user'])
        manager.downloader.pull.assert_called_with()

    def test_run_pull_dry_run(self):
        with mock.patch('ipamanager.ipa_connector.IpaDownloader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['pull', 'dump_repo', '--dry-run'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(manager.settings, manager.entities,
                                     'dump_repo', True, False, ['user'])
        manager.downloader.pull.assert_called()

    def test_run_pull_add_only(self):
        with mock.patch('ipamanager.ipa_connector.IpaDownloader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['pull', 'dump_repo', '--add-only'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(manager.settings, manager.entities,
                                     'dump_repo', False, True, ['user'])
        manager.downloader.pull.assert_called()

    def test_run_diff(self):
        with mock.patch(
                'ipamanager.freeipa_manager.FreeIPADifference') as mock_diff:
            manager = self._init_tool(['diff', 'repo1', 'repo2'])
            manager.run()
        mock_diff.assert_called_with('repo1', 'repo2')
        mock_diff.return_value.run.assert_called_with()

    @mock.patch('ipamanager.freeipa_manager.FreeIPATemplate')
    @mock.patch('ipamanager.freeipa_manager.ConfigTemplateLoader')
    def test_run_template(self, mock_loader, mock_template):
        mock_loader.return_value.load_config.return_value = [{
            'subcluster1': {'datacenters': {'a1': 10, 'a2': 20},
                            'separate_sudo': True,
                            'separate_foreman_view': False},
            'subcluster2': {'datacenters': {'a2': 20, 'a3': 30},
                            'separate_sudo': False,
                            'separate_foreman_view': True}
        }]
        self._init_tool(['template', 'repo', 'template.file']).run()
        mock_loader.assert_called_with('template.file')
        assert all(item in mock_template.call_args_list for item in [
            mock.call('subcluster2', {'datacenters': {'a3': 30, 'a2': 20},
                                      'separate_sudo': False,
                                      'separate_foreman_view': True},
                      'repo', False),
            mock.call('subcluster1', {'datacenters': {'a1': 10, 'a2': 20},
                                      'separate_sudo': True,
                                      'separate_foreman_view': False},
                      'repo', False)])

    def _mock_load(self):
        def f(manager, *args, **kwargs):
            self.mock_load_args = (args, kwargs)
            manager.entities = {'users': {'user1': mock.Mock()}}
        return f

    def test_run_roundtrip(self):
        with mock.patch('%s.FreeIPAManager.load' % modulename,
                        self._mock_load()):
            manager = self._init_tool(['roundtrip', 'config_path', '-v'])
            manager.run()
        assert self.mock_load_args == ((), {'apply_ignored': True})
        manager.entities['users']['user1'].normalize.assert_called_with()
        manager.entities['users']['user1'].write_to_file.assert_called_with()

    def test_run_roundtrip_no_ignored(self):
        with mock.patch('%s.FreeIPAManager.load' % modulename,
                        self._mock_load()):
            manager = self._init_tool(['roundtrip', 'config_path', '-v', '-I'])
            manager.run()
        assert self.mock_load_args == ((), {'apply_ignored': False})
        manager.entities['users']['user1'].normalize.assert_called_with()
        manager.entities['users']['user1'].write_to_file.assert_called_with()

    def test_settings_default_check(self):
        with mock.patch.object(sys, 'argv', ['manager', 'check', 'repo']):
            assert utils.parse_args().settings == (
                '/opt/freeipa-manager/settings_push.yaml')

    def test_settings_default_diff(self):
        with mock.patch.object(sys, 'argv', ['manager', 'diff',
                                             'repo', 'repo2']):
            assert utils.parse_args().settings == (
                '/opt/freeipa-manager/settings_pull.yaml')

    def test_settings_default_push(self):
        with mock.patch.object(sys, 'argv', ['manager', 'push', 'repo']):
            assert utils.parse_args().settings == (
                '/opt/freeipa-manager/settings_push.yaml')

    def test_settings_default_pull(self):
        with mock.patch.object(sys, 'argv', ['manager', 'pull', 'repo']):
            assert utils.parse_args().settings == (
                '/opt/freeipa-manager/settings_pull.yaml')

    def test_load_settings(self):
        assert self._init_tool(['check', 'dump_repo']).settings == {
            'ignore': {'group': ['ipausers', 'test.*'], 'user': ['admin']},
            'user-group-pattern': '^role-.+|.+-users$', 'nesting-limit': 42}

    def test_load_settings_alerting(self):
        assert self._init_tool(
            ['check', 'dump_repo'], settings=SETTINGS_ALERTING).settings == {
                'ignore': {'group': ['ipausers', 'test.*'], 'user': ['admin']},
                'user-group-pattern': '^role-.+|.+-users$',
                'nesting-limit': 42,
                'alerting': {'plugin1': {'class': 'def',
                                         'config': {'key1': 'value1'},
                                         'module': 'abc'},
                             'plugin2': {'class': 'def2', 'module': 'abc'}}}

    def test_load_settings_not_found(self):
        with mock.patch('__builtin__.open') as mock_open:
            mock_open.side_effect = IOError('[Errno 2] No such file or dir')
            with pytest.raises(tool.ManagerError) as exc:
                self._init_tool(['check', 'dump_repo'])
        assert exc.value[0] == (
            'Error loading settings: [Errno 2] No such file or dir')

    def test_load_settings_invalid_ignore_key(self):
        with pytest.raises(tool.ManagerError) as exc:
            self._init_tool(['check', 'dump_repo'], settings=SETTINGS_INVALID)
        assert exc.value[0] == (
            "Error loading settings: extra keys "
            "not allowed @ data['ignore']['groups']")


class TestUtils(object):
    def test_check_handler_present_empty(self):
        lg = logging.getLogger('test_check_handler_present')
        assert not utils._check_handler_present(lg, logging.StreamHandler)

    def test_check_handler_present_not_present(self):
        lg = logging.getLogger('test_check_handler_present_not_present')
        lg.addHandler(logging.StreamHandler(sys.stderr))
        assert not utils._check_handler_present(lg, logging.FileHandler)

    def test_check_handler_present_present_different_attr(self):
        lg = logging.getLogger(
            'test_check_handler_present_not_present_different_attr')
        lg.addHandler(logging.StreamHandler(sys.stderr))
        assert not utils._check_handler_present(
            lg, logging.StreamHandler, ('stream', sys.stdout))

    def test_check_handler_present_present_no_attr(self):
        lg = logging.getLogger('test_check_handler_present_present_no_attr')
        lg.addHandler(logging.StreamHandler(sys.stderr))
        assert utils._check_handler_present(lg, logging.StreamHandler)

    def test_check_handler_present_present_same_attr(self):
        lg = logging.getLogger('test_check_handler_present_present_same_attr')
        lg.addHandler(logging.StreamHandler(sys.stderr))
        assert utils._check_handler_present(
            lg, logging.StreamHandler, ('stream', sys.stderr))

    @mock.patch('ipamanager.utils.sys')
    @mock.patch('ipamanager.utils.logging')
    def test_init_logging(self, mock_logging, mock_sys):
        utils.init_logging(logging.INFO)
        mock_logging.StreamHandler.assert_called_with(mock_sys.stderr)
        facility = mock_logging.handlers.SysLogHandler.LOG_LOCAL5
        mock_logging.handlers.SysLogHandler.assert_called_with(
            address='/dev/log', facility=facility)
        mock_logging.getLogger.return_value.addHandler.assert_has_calls(
            [mock.call(mock_logging.StreamHandler.return_value),
             mock.call(mock_logging.handlers.SysLogHandler.return_value)])

    def test_init_logging_no_syslog(self):
        logging.getLogger().handlers = []  # clean left-overs of previous tests
        with mock.patch('ipamanager.utils.logging.handlers') as mock_handlers:
            with mock.patch(
                    'ipamanager.utils._check_handler_present') as mock_check:
                mock_check.return_value = False
                mock_handlers.SysLogHandler.side_effect = socket.error(
                    'No such file or directory')
                with LogCapture() as log:
                    utils.init_logging(logging.INFO)
            log.check(
                ('root', 'DEBUG', 'Stderr handler added to root logger'),
                ('root', 'ERROR',
                 'Syslog connection failed: No such file or directory'))

    def test_init_logging_already_added(self):
        logging.getLogger().handlers = []  # clean left-overs of previous tests
        with mock.patch(
                'ipamanager.utils._check_handler_present') as mock_check:
            mock_check.return_value = True
            with LogCapture() as log:
                utils.init_logging(logging.INFO)
            log.check(('root', 'DEBUG', 'Stderr handler already added'),
                      ('root', 'DEBUG', 'Syslog handler already added'))

    def test_load_settings_no_include(self):
        assert utils.load_settings(SETTINGS) == {
            'ignore': {'group': ['ipausers', 'test.*'], 'user': ['admin']},
            'nesting-limit': 42, 'user-group-pattern': '^role-.+|.+-users$'}

    def test_load_settings_yes_include(self):
        assert utils.load_settings(SETTINGS_INCLUDE) == {
            'alerting': {'plugin1': {'class': 'def', 'module': 'abc',
                                     'config': {'key1': 'value1'}},
                         'plugin2': {'class': 'def2', 'module': 'abc'}},
            'ignore': {'group': ['ipausers', 'test.*'], 'user': ['admin']},
            'nesting-limit': 42, 'user-group-pattern': '^role-.+|.+-users$'}

    def test_load_settings_yes_merge_include(self):
        assert utils.load_settings(SETTINGS_MERGE_INCLUDE) == {
            'alerting': {'plugin1': {'class': 'def', 'module': 'abc',
                                     'config': {'key1': 'value1'}},
                         'plugin2': {'class': 'def2', 'module': 'abc'}},
            'ignore': {'group': ['group2', 'group3'],
                       'service': ['serviceX'], 'user': ['admin']},
            'nesting-limit': 42, 'user-group-pattern': '^role-.+|.+-users$'}
