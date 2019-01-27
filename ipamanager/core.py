#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - core class

Core utility class for other classes to inherit from.
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
