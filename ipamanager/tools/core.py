#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager Tools - core class

Core utility class for tool classes to inherit from.
"""

import logging

from ipamanager.utils import init_logging


class FreeIPAManagerToolCore(object):
    """
    Core abstract class providing logging functionality
    and serving as a base for other modules of the app.

    Unlike the core class in the top-level ipamanager package,
    logging initialization is called here because the tool modules
    are meant to be used as separate executable applications.
    """

    def __init__(self, loglevel):
        init_logging(loglevel)
        self.lg = logging.getLogger(self.__class__.__name__)
