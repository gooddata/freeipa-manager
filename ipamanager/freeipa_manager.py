"""
GoodData FreeIPA tooling

Main entry point of the tooling, responsible for delegating the tasks.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import sys

from core import FreeIPAManagerCore
from config_loader import ConfigLoader
from errors import ManagerError
from github_forwarder import GitHubForwarder
from integrity_checker import IntegrityChecker
from utils import init_api_connection, init_logging, parse_args


class FreeIPAManager(FreeIPAManagerCore):
    """
    Main runnable class responsible for coordinating module functionality.
    """
    def __init__(self):
        super(FreeIPAManager, self).__init__()
        self.args = parse_args()
        init_logging(self.args.loglevel)

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
            self.args.rules, self.config_loader.entities)
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
        init_api_connection(self.args.loglevel)
        self.uploader = IpaUploader(
            self.integrity_checker.entity_dict, self.args.threshold,
            self.args.force, self.args.deletion)
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
        self.forwarder = GitHubForwarder(
            self.args.config, self.args.base, self.args.branch)
        if self.args.commit or self.args.pull_request:
            self.forwarder.checkout_base()
        self.check()
        from ipa_connector import IpaDownloader
        init_api_connection(self.args.loglevel)
        self.downloader = IpaDownloader(
            self.integrity_checker.entity_dict, self.args.config,
            self.args.dry_run, self.args.add_only)
        self.downloader.pull()
        if self.args.commit:
            self.forwarder.commit()
        if self.args.pull_request:
            self.forwarder.create_pull_request(
                self.args.owner, self.args.repo,
                self.args.user, self.args.token)


def main():
    manager = FreeIPAManager()
    manager.run()


if __name__ == '__main__':
    main()
