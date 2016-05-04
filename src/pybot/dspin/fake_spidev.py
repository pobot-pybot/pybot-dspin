#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pybot.core import log
_log = log.getLogger(__name__)


class SpiDev(object):
    def open(self, bus, device):
        _log.warn('open(%s, %s)', bus, device)

    def close(self):
        _log.warn('close()')

    def xfer(self, data):
        _log.warn('xfer(%s)', data)
        return [0] * len(data)

    def xfer2(self, data):
        _log.warn('xfer2(%s)', data)
        return [0] * len(data)
