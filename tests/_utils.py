#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import os.path
import sys


def _import(path, module):
    testpath = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(testpath, '..'))
    return getattr(__import__(path, fromlist=[module]), module)


def _mock_dump(write_target, original_dump):
    def f(data, **kwargs):
        kwargs['stream'] = None
        write_target[data.keys()[0]] = original_dump(data, **kwargs)
    return f
