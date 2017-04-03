"""
GoodData FreeIPA tooling
Configuration parsing tool

Various utility functions for better code readability & organization.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import argparse
import logging


def init_logging(loglevel):
    fmt = '%(levelname)s:%(name)s:%(funcName)s: %(message)s'
    logging.basicConfig(level=loglevel, format=fmt)


def parse_args():
    parser = argparse.ArgumentParser(description='FreeIPA management CLI tool')
    # parser.add_argument('action', choices=['check'])  # just check for now
    parser.add_argument('path', help='Path to configuration repository')
    parser.add_argument('-t', '--types', nargs='+', choices=['users'])
    parser.add_argument(
        '-d', '--debug', dest='loglevel', action='store_const',
        const=logging.DEBUG, default=logging.INFO)
    args = parser.parse_args()
    args.types = set(args.types) if args.types else None
    return args
