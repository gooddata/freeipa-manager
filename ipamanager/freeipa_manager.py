#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

"""
FreeIPA Manager - top level script

Main entry point of the tooling, responsible for delegating the tasks.
"""

import importlib
import logging
import sys

import utils
from core import FreeIPAManagerCore
from config_loader import ConfigLoader
from okta_loader import OktaLoader
from difference import FreeIPADifference
from errors import ManagerError
from integrity_checker import IntegrityChecker
from template import FreeIPATemplate, ConfigTemplateLoader


class FreeIPAManager(FreeIPAManagerCore):
    """
    Main runnable class responsible for coordinating module functionality.
    """
    def __init__(self):
        # parse_args is called by argcomplete; must be as fast as possible
        self.args = utils.parse_args()
        super(FreeIPAManager, self).__init__()
        utils.init_logging(self.args.loglevel)
        self._load_settings()
        # Find if users should be pushed from Okta
        self.okta_users = self.settings.get('okta', dict()).get(
            'enabled', False)

    def run(self):
        """
        Execute the task selected by arguments (check config, upload etc).
        """
        try:
            self._register_alerting()
            {
                'check': self.check,
                'push': self.push,
                'pull': self.pull,
                'diff': self.diff,
                'template': self.template,
                'roundtrip': self.roundtrip
            }[self.args.action]()
        except ManagerError as e:
            self.lg.error(e)
            sys.exit(1)
        finally:
            for plugin in self.alerting_plugins:
                plugin.dispatch()

    def _register_alerting(self):
        """
        For each alerting plugin listed in settings:
        1. Instantiate the plugin based on config.
        2. Add the plugin as a root logging handler.
        3. Add the plugin to the `alerting_plugins` list attribute,
           so that it dispatches the results in the end of the run.
        """
        self.alerting_plugins = []
        plugins_config = self.settings.get('alerting')
        if not plugins_config:
            self.lg.info('No alerting plugins configured in settings')
            return
        self.lg.debug('Registering %d alerting plugins', len(plugins_config))
        root_logger = logging.getLogger()
        for name, config in plugins_config.iteritems():
            try:
                module_path = 'ipamanager.alerting.%s' % (config['module'])
                module = importlib.import_module(module_path)
                plugin_config = config.get('config', {})
                plugin = getattr(module, config['class'])(plugin_config)
                root_logger.addHandler(plugin)
                self.alerting_plugins.append(plugin)
                self.lg.debug('Registered plugin %s', plugin)
            except (AttributeError, ImportError, ManagerError) as e:
                raise ManagerError(
                    'Could not register alerting plugin %s: %s' % (name, e))
        self.lg.debug('Registered %d alerting plugins',
                      len(self.alerting_plugins))

    def load(self, apply_ignored=True):
        """
        Load configurations from configuration repository at the given path.
        :param bool apply_ignored: whether 'ignored' settings
                                   should be taken into account
        """
        self.config_loader = ConfigLoader(
            self.args.config, self.settings, apply_ignored)
        self.entities = self.config_loader.load()

        if self.okta_users:
            if self.args.action == 'check':
                self.lg.info('Okta user loading not supported in test')
                self.entities['user'] = {}
                self.okta_groups = []
                return

            # only groups defined both in IPA & Okta are taken for Okta users
            ipa_groups = self.entities.get('group', []).keys()
            self.okta_loader = OktaLoader(self.settings, ipa_groups)
            if self.entities.get('user'):
                self.lg.warning(
                    '%d users parsed from Git but will be overwritten by Okta',
                    len(self.entities['user']))
            self.entities['user'] = self.okta_loader.load()
            # parse Okta groups to use for constructing diff
            self.okta_groups = self.okta_loader.load_groups()

    def check(self):
        """
        Run integrity check on the loaded configuration.
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        """
        self.load()
        self.integrity_checker = IntegrityChecker(self.entities, self.settings)
        self.integrity_checker.check()

    def push(self):
        """
        Run upload of configuration to FreeIPA via API.
        This can only be run locally on FreeIPA nodes.
        Arguments to the IpaConnector instance
        are passed from `self.args` in the `_api_connect` method.
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        :raises ManagerError: in case of API connection error or update error
        """
        self.check()
        from ipa_connector import IpaUploader
        utils.init_api_connection(self.args.loglevel)
        self.uploader = IpaUploader(
            self.settings, self.entities, self.args.threshold,
            self.args.force, self.args.deletion, self.okta_users,
            self.okta_groups if self.okta_users else [])
        self.uploader.push()

    def pull(self):
        """
        Run upload of configuration to FreeIPA via API.
        This can only be run locally on FreeIPA nodes.
        Arguments to the IpaConnector instance
        are passed from `self.args` in the `_api_connect` method.
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        :raises ManagerError: in case of API connection error or update error
        """
        self.load()
        from ipa_connector import IpaDownloader
        utils.init_api_connection(self.args.loglevel)
        self.downloader = IpaDownloader(
            self.settings, self.entities, self.args.config,
            self.args.dry_run, self.args.add_only, self.args.pull_types)
        self.downloader.pull()

    def diff(self):
        """
        Makes set-like difference between 2 dirs. Arguments to the diff are
        passed from `self.args` in the `_api_connect` method.
        :raises IntegrityError: in case the difference is not empty
        """
        diff = FreeIPADifference(self.args.config, self.args.sub_path)
        diff.run()

    def template(self):
        """
        Creates groups, hostgroups, and rules for a given subcluster according
        to config defined in template.
        :raises ConfigError: in case of wrong template file
        """
        data = ConfigTemplateLoader(self.args.template).load_config()
        for template in data:
            for name, values in template.iteritems():
                FreeIPATemplate(
                    name, values, self.args.config, self.args.dry_run).create()

    def roundtrip(self):
        """
        Run load, then save the configuration back into config files.
        This is done to ensure a "normal" formatting when config files
        are syntactically & logically correct but have a non-standard format
        (e.g., unsorted membership list, larger or smaller indents etc).
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        """
        if self.args.no_ignored:
            self.lg.info('Loading ALL entities because of --no-ignored flag')
        self.load(apply_ignored=not self.args.no_ignored)
        for entity_type, entity_list in self.entities.iteritems():
            self.lg.info('Re-writing %s entities to file', entity_type)
            for e in entity_list.itervalues():
                e.normalize()
                e.write_to_file()
        self.lg.info('Entity round-trip complete')

    def _load_settings(self):
        """
        Load the settings file. The file contains integrity check settings,
        ignored entities configuration and other useful settings.
        """
        self.lg.debug('Loading settings file from %s', self.args.settings)
        try:
            self.settings = utils.load_settings(self.args.settings)
        except Exception as e:
            raise ManagerError('Error loading settings: %s' % e)
        self.lg.debug('Settings parsed: %s', self.settings)


def main():
    manager = FreeIPAManager()
    manager.run()


if __name__ == '__main__':
    main()
