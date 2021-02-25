#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - NSCA Alerting plugin

Alerting plugin used for dispatch of messages
via Nagios Service Check Acceptor (NSCA).
"""

import logging
import socket
from subprocess import Popen, PIPE

from ipamanager.alerting import AlertingPlugin
from ipamanager.errors import ConfigError


class NscaAlertingPlugin(AlertingPlugin):
    """
    Alerting plugin used for dispatch of messages
    via Nagios Service Check Acceptor (NSCA).
    """
    def __init__(self, config):
        super(NscaAlertingPlugin, self).__init__(logging.WARNING)
        messages_config = config.get('messages', {})
        self.prefix = {
            0: messages_config.get('ok', 'freeipa-manager works OK'),
            1: messages_config.get('warn', 'freeipa-manager has warnings:'),
            2: messages_config.get('err', 'freeipa-manager has errors:')
        }
        self.command = config.get('command', '/usr/sbin/send_nsca')
        try:
            self.service = config['service']
        except KeyError:
            raise ConfigError(
                'Parameter service must be defined for %s' % self.name)

        self.nsca_hostname = config.get('nsca_hostname', socket.getfqdn())

    def _status_code(self):
        """
        Get the status code to dispatch to NSCA (0, 1 or 2) based on max_level.
        :returns: status code to dispatch (0 to 2)
        :rtype: int
        """
        if self.max_level >= logging.ERROR:
            return 2
        if self.max_level >= logging.WARNING:
            return 1
        return 0

    def _run_dispatch(self, code, message):
        data = '%s;%s;%s;%s' % (self.nsca_hostname, self.service, code, message)
        self.lg.debug('Dispatching NSCA data: %s', data)
        sp = Popen((self.command, '-d', ';'),
                   stdin=PIPE, stdout=PIPE, stderr=PIPE)
        return sp.communicate(data)

    def dispatch(self):
        """
        Dispatch the result of the check via NSCA.
        """
        status_code = self._status_code()
        msg = '%s%s' % (
            self.prefix[status_code],
            ' [%s]' % ' '.join(self.messages) if self.messages else '')
        stdout, stderr = self._run_dispatch(status_code, msg)
        if stderr:
            if self.messages:  # message was probably too long
                backup_prefix = self.messages[-1]
            else:  # another, unknown error, try re-sending
                backup_prefix = msg
            backup_message = '%s (first dispatch failed: %s)' % (
                backup_prefix, stderr)
            self._run_dispatch(code=2, message=backup_message)
            self.lg.error(
                'First NSCA dispatch failed, sent backup message: %s',
                backup_message)
            return
        self.lg.info('Dispatch to NSCA was successful')
