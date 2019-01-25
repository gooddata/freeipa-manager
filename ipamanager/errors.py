#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - errors module
"""


class ManagerError(Exception):
    """General error, used mainly for derivation of other exceptions."""


class CommandError(ManagerError):
    """Error raised in case of API command execution error."""


class ConfigError(ManagerError):
    """Error raised in case of encountering an invalid configuration."""


class IntegrityError(ConfigError):
    """Error raised in case of integrity checking failure."""
