#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pybot.core import log

pkg_log = log.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    real_raspi = True

except ImportError:
    # import a dummy module simulating the real API so that
    # IDEs can help us
    import fake_gpio as GPIO
    pkg_log.warn("not running on a RasPi")
    real_raspi = False


if real_raspi:
    import spidev
else:
    import fake_spidev as spidev
