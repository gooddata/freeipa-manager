#!/usr/bin/env python
"""
GoodData FreeIPA tooling

Main entry point of the tooling, responsible for delegating the tasks.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

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
        utils.init_logging(self.args.loglevel)

    def _load_config(self):
        """
        Load configurations from configuration repository at the given path.
        Run integrity check on the loaded configuration.
        """
        self.config_loader = ConfigLoader(self.args.config, self.args.domain)
        self.config_loader.load()
        self.integrity_checker = IntegrityChecker(
            self.args.rules_file, self.config_loader.entities)
        self.integrity_checker.check()

    def run(self):
        """
        Execute the task selected by arguments (check config, upload etc).
        """
        try:
            {
                'check': self.check,
                'compare': self.compare,
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
        """
        self.config_loader = ConfigLoader(self.args.config)
        self.config_loader.load()
        self.integrity_checker = IntegrityChecker(
            self.args.rules_file, self.config_loader.entities)
        self.integrity_checker.check()

    def push(self):
        raise NotImplementedError('Config pushing not available yet.')

    def pull(self):
        raise NotImplementedError('Config pulling not available yet.')


if __name__ == '__main__':
    manager = FreeIPAManager()
    manager.run()
