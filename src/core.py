"""
GoodData FreeIPA tooling
Configuration parsing tool

Validation schemas for FreeIPA entities configuration.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import logging


class FreeIPAManagerCore(object):
    """
    Core abstract class providing logging functionality
    and serving as a base for other modules of the app.
    """
    def __init__(self):
        self.configure_logger()
        self.errs = []

    def configure_logger(self):
        self.lg = logging.getLogger(self.__class__.__name__)
