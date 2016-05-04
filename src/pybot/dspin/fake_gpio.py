#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pybot.core import log
_log = log.getLogger(__name__)

FAKE = True


def setwarnings(state):
    _log.warn('setwarnings(%s)', state)


def setup(channels, io_mode):
    _log.warn('setup(%s, %s)', channels, io_mode)


def setmode(numbering_mode):
    _log.warn('setmode(%s)', numbering_mode)


def cleanup():
    _log.warn('cleanup()')


def input(channel):
    result = 0
    _log.warn('input(%s) -> %s', channel, result)
    return result


def output(channels, states):
    _log.warn('output(%s, %s)', channels, states)


IN, OUT = range(2)
LOW, HIGH = range(2)

BOARD, BCM = range(2)
