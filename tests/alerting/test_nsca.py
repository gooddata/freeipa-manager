#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import logging
import mock
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager.alerting', 'nsca')
errors = _import('ipamanager', 'errors')
modulename = 'ipamanager.alerting.nsca'


class TestAlerting(object):
    def setup_method(self, method):
        self.config = {
            'messages': {
                'ok': 'Everything OK.',
                'warn': 'Some warnings:',
                'err': 'Some errors:'
            },
            'command': '/dev/null/send_nsca',
            'service': 'ipamanager-push'
        }
        if not method.func_name.startswith('test_init'):
            self.plugin = tool.NscaAlertingPlugin(self.config)
            if method.func_name.startswith('test_dispatch'):
                self.plugin._run_dispatch = mock.Mock()

    @log_capture()
    def test_init(self, log):
        plugin = tool.NscaAlertingPlugin(self.config)
        assert plugin.name == 'NscaAlertingPlugin'
        assert plugin.prefix == {
            0: 'Everything OK.', 1: 'Some warnings:', 2: 'Some errors:'}
        assert plugin.command == '/dev/null/send_nsca'
        assert plugin.level == logging.WARNING
        log.check(
            ('NscaAlertingPlugin', 'DEBUG',
             'Alerting plugin NscaAlertingPlugin initialized'))

    def test_init_defaults(self):
        plugin = tool.NscaAlertingPlugin({'service': 'ipamanager-push'})
        assert plugin.name == 'NscaAlertingPlugin'
        assert plugin.prefix == {
            0: 'freeipa-manager works OK',
            1: 'freeipa-manager has warnings:',
            2: 'freeipa-manager has errors:'
        }
        assert plugin.command == '/usr/sbin/send_nsca'
        assert plugin.level == logging.WARNING

    def test_init_required_parameter_missing(self):
        with pytest.raises(errors.ConfigError) as exc:
            tool.NscaAlertingPlugin({})
        assert exc.value[0] == (
            'Parameter service must be defined for NscaAlertingPlugin')

    def test_status_code_critical(self):
        self.plugin.max_level = logging.CRITICAL
        assert self.plugin._status_code() == 2

    def test_status_code_error(self):
        self.plugin.max_level = logging.ERROR
        assert self.plugin._status_code() == 2

    def test_status_code_warning(self):
        self.plugin.max_level = logging.WARNING
        assert self.plugin._status_code() == 1

    def test_status_code_info(self):
        self.plugin.max_level = logging.INFO
        assert self.plugin._status_code() == 0

    def test_status_code_debug(self):
        self.plugin.max_level = logging.DEBUG
        assert self.plugin._status_code() == 0

    @log_capture()
    @mock.patch('ipamanager.alerting.nsca.Popen')
    @mock.patch('ipamanager.alerting.nsca.socket')
    def test_run_dispatch(self, mock_sock, mock_popen, log):
        mock_sock.getfqdn.return_value = 'freeipa-node'
        ret = self.plugin._run_dispatch(7, 'some msg')
        mock_popen.assert_called_with(
            ('/dev/null/send_nsca', '-d', ';'), stdin=-1, stdout=-1, stderr=-1)
        mock_popen.return_value.communicate.assert_called_with(
            'freeipa-node;ipamanager-push;7;some msg')
        assert ret == mock_popen.return_value.communicate.return_value

    @log_capture()
    def test_dispatch(self, log):
        self.plugin.messages = ['INFO: test', 'DEBUG: test2']
        self.plugin._run_dispatch.return_value = ('', '')
        self.plugin.dispatch()
        assert self.plugin._run_dispatch.call_count == 1
        self.plugin._run_dispatch.assert_called_with(
            0, 'Everything OK. [INFO: test DEBUG: test2]')
        log.check(('NscaAlertingPlugin', 'INFO',
                   'Dispatch to NSCA was successful'))

    @log_capture()
    def test_dispatch_error(self, log):
        self.plugin.messages = ['INFO: test', 'DEBUG: test2']
        self.plugin._run_dispatch.return_value = ('', 'error: too long')
        self.plugin.dispatch()
        assert self.plugin._run_dispatch.call_count == 2
        self.plugin._run_dispatch.assert_has_calls([
            mock.call(0, 'Everything OK. [INFO: test DEBUG: test2]'),
            mock.call(code=2, message=(
                'DEBUG: test2 (first dispatch failed: error: too long)'))])
        log.check(('NscaAlertingPlugin', 'ERROR',
                   ('First NSCA dispatch failed, sent backup message: '
                    'DEBUG: test2 (first dispatch failed: error: too long)')))

    @log_capture()
    def test_dispatch_error_no_messages(self, log):
        self.plugin.messages = []
        self.plugin._run_dispatch.return_value = ('', 'error: too long')
        self.plugin.dispatch()
        assert self.plugin._run_dispatch.call_count == 2
        self.plugin._run_dispatch.assert_has_calls([
            mock.call(0, 'Everything OK.'),
            mock.call(code=2, message=(
                'Everything OK. (first dispatch failed: error: too long)'))])
        log.check(
            ('NscaAlertingPlugin', 'ERROR',
             ('First NSCA dispatch failed, sent backup message: '
              'Everything OK. (first dispatch failed: error: too long)')))
