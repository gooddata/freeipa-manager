#!/usr/bin/env python
"""
GoodData FreeIPA tooling

Main entry point of the tooling, responsible for delegating the tasks.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import sys

import utils
from core import FreeIPAManagerCore
from entity_loader import EntityLoader


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

    def _load_entities(self):
        """
        Load configurations from configuration repository at the given path.
        """
        self.loader = EntityLoader(self.args.path)
        self.lg.info('Processing %s', 'all entities' if not self.args.types
                     else 'only [%s]' % ', '.join(self.args.types))
        self.loader.load(self.args.types)
        if self.loader.errs:
            self.lg.error(
                'There have been errors in %d configuration files: [%s]',
                len(self.loader.errs), ', '.join(sorted(self.loader.errs)))
            sys.exit(1)

    def run(self):
        """
        Execute the task selected by arguments (check config, upload etc).
        Currently, only configuration checking is implemented.
        """
        self._load_entities()


if __name__ == '__main__':
    manager = FreeIPAManager()
    manager.run()
