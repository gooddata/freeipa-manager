#!/usr/bin/env python
"""
GoodData FreeIPA tooling

Main entry point of the tooling, responsible for delegating the tasks.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import logging
import sys

import utils
from core import FreeIPAManagerCore
from config_loader import ConfigLoader
from errors import ManagerError
from integrity_checker import IntegrityChecker


class FreeIPAManager(FreeIPAManagerCore):
    """
    Main runnable class responsible for coordinating module functionality.
    """
    def __init__(self):
        super(FreeIPAManager, self).__init__()
        self._parse_args()

    def _parse_args(self):
        self.args = utils.parse_args()
        utils.init_logging(logging.DEBUG if self.args.debug else logging.INFO)

    def run(self):
        """
        Execute the task selected by arguments (check config, upload etc).
        """
        try:
            {
                'check': self.check,
                'push': self.push,
                'pull': self.pull
            }[self.args.action]()
        except ManagerError as e:
            self.lg.error(e)
            sys.exit(1)

    def check(self):
        """
        Load configurations from configuration repository at the given path.
        Run integrity check on the loaded configuration.
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        """
        self.config_loader = ConfigLoader(self.args.config, self.args.ignored)
        self.config_loader.load()
        self.integrity_checker = IntegrityChecker(
            self.args.rules_file, self.config_loader.entities)
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
        self._api_connect()
        self.connector.load_remote()
        self.connector.execute_update()

    def _api_connect(self):
        """
        Initialize connection to FreeIPA API via `IpaConnector` object.
        The object is imported here to allow running configuration check
        locally on developer machines without dependency problems.
        :raises ManagerError: in case of API connection error
        """
        from ipa_connector import IpaConnector
        self.connector = IpaConnector(
            self.integrity_checker.entity_dict, self.args.threshold,
            self.args.force, self.args.enable_deletion, self.args.debug)

    def pull(self):
        raise NotImplementedError('Config pulling not available yet.')


if __name__ == '__main__':
    manager = FreeIPAManager()
    manager.run()
