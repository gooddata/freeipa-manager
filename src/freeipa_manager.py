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
from ldap_loader import LdapDownloader


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
        """
        self.config_loader = ConfigLoader(self.args.config, self.args.domain)
        self.config_loader.load()
        self.config_loader.check_integrity()

    def _load_ldap(self):
        """
        Load configurations from given LDAP server.
        """
        self.ldap_loader = LdapDownloader(self.args.domain)
        self.ldap_loader.load()

    def run(self):
        """
        Execute the task selected by arguments (check config, upload etc).
        Currently, only configuration checking is implemented.
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
        Run repository configuration check.
        Can check local config repo, config from LDAP server, or both.
        """
        if self.args.config:
            self._load_config()
        if self.args.domain:
            self._load_ldap()

    def compare(self):
        raise NotImplementedError('Comparing not available yet.')

    def push(self):
        raise NotImplementedError('Config pushing not available yet.')

    def pull(self):
        raise NotImplementedError('Config pulling not available yet.')


if __name__ == '__main__':
    manager = FreeIPAManager()
    manager.run()
