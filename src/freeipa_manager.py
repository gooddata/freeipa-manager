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
        self.loader = ConfigLoader(self.args.conf)
        self.lg.info('Processing entities [%s]', ', '.join(self.args.types))
        self.loader.load(self.args.types)
        if self.loader.errs:
            raise ManagerError(
                'There have been errors in %d configuration files: [%s]' %
                (len(self.loader.errs), ', '.join(sorted(self.loader.errs))))

    def _load_ldap(self):
        """
        Load configurations from given LDAP server.
        """
        self.ldap_loader = LdapDownloader(self.args.remote)
        self.ldap_loader.load_entities(self.args.types)

    def _check_requirements(self):
        """
        Test whether requirements for the given action have been met.
        Config check requires at least config repo or LDAP server,
        all other actions require both arguments.
        """
        source_args = [self.args.conf, self.args.remote]
        if self.args.action == 'check':
            if not any(source_args):
                raise ManagerError('--conf or --remote required')
            return
        elif not all(source_args):
            raise ManagerError('Both --conf and --remote required')

    def run(self):
        """
        Execute the task selected by arguments (check config, upload etc).
        Currently, only configuration checking is implemented.
        """
        try:
            self._check_requirements()
        except ManagerError as e:
            self.lg.error('Cannot %s: %s', self.args.action, e)
            sys.exit(2)
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
        if self.args.conf:
            self.lg.info('Checking local config at %s', self.args.conf)
            self._load_config()
        if self.args.remote:
            self.lg.info('Checking config at LDAP server %s', self.args.remote)
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
