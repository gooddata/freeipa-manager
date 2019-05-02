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
from testfixtures import log_capture, LogCapture

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
        mock_config.assert_called_with('config_path', manager.settings, True)
        mock_check.assert_called_with(
            manager.config_loader.load.return_value, manager.settings)

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
        mock_conn.assert_called_with(manager.settings, {}, 10, True, False)

    def test_run_push_enable_deletion(self):
        with mock.patch('ipamanager.ipa_connector.IpaUploader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['push', 'repo_path', '-fdt', '10'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(manager.settings, {}, 10, True, True)

    def test_run_push_dry_run(self):
        with mock.patch('ipamanager.ipa_connector.IpaUploader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['push', 'config_repo'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(manager.settings, {}, 10, False, False)

    def test_run_push_dry_run_enable_deletion(self):
        with mock.patch('ipamanager.ipa_connector.IpaUploader') as mock_conn:
            with mock.patch('%s.FreeIPAManager.check' % modulename):
                manager = self._init_tool(['push', 'config_repo', '-d'])
                manager.entities = dict()
                manager.run()
        mock_conn.assert_called_with(manager.settings, {}, 10, False, True)

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


class TestUtils(object):
    @mock.patch('ipamanager.utils.sys')
    @mock.patch('ipamanager.utils.logging')
    def test_init_logging_without_alerting(self, mock_logging, mock_sys):
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
            mock_handlers.SysLogHandler.side_effect = socket.error(
                'No such file or directory')
            with LogCapture() as log:
                utils.init_logging(logging.INFO)
            log.check(
                ('root', 'DEBUG', 'Stderr handler added to root logger'),
                ('root', 'ERROR',
                 'Syslog connection failed: No such file or directory'))
