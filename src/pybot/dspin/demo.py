# -*- coding: utf-8 -*-

import sys
import argparse
import textwrap

from pybot.core import log 

from .core import DSPIN, DSPinSpiDev, GPIO
from .defs import StepMode, OverCurrentThreshold, Configuration, max_spd_calc, min_spd_calc, fs_spd_calc

__author__ = 'Eric Pascual'


class DSPINDemo(object):
    STANDBY_PIN = 11
    BUSYN_PIN = 13

    def __init__(self, log_level=log.INFO, use_curses=False, win_size=(24, 80)):
        self.TITLE = self.__doc__.split('\n')[0].rstrip('.').strip()

        if use_curses:
            try:
                import curses

            except ImportError:
                self._curses = None

            else:
                self._curses = curses
                self._init_curses(win_size)

        else:
            self._curses = None

        root_logger = log.getLogger()
        self.curses_log_handler = None

        if use_curses:
            # route log messages to a file to avoid messages
            # "polluting" the display
            from pybot.core.log import FileHandler

            hndlr = FileHandler(self.__class__.__name__ + '.log', mode='w')
            hndlr.setFormatter(root_logger.handlers[0].formatter)
            # replaces the default handler which outputs messages on the console
            root_logger.handlers[0] = hndlr
            self.log_stream = open(hndlr.baseFilename)

            # add a handler for displaying them in curses
            hndlr = self.get_curses_log_handler()
            if hndlr:
                root_logger.addHandler(hndlr)
                self.curses_log_handler = hndlr

        root_logger.setLevel(log_level)
        root_logger.info("log level set to : %s", log.getLevelName(root_logger.getEffectiveLevel()))
        self.log = log.getLogger(self.__class__.__name__)
        self.log.info("log level set to : %s", log.getLevelName(self.log.getEffectiveLevel()))

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)

        self.spi = DSPinSpiDev(spi_bus=0, spi_dev=0)

    def _init_curses(self, win_size):
        curses = self._curses

        curses.initscr()
        curses.setupterm()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        try:
            curses.start_color()
            curses.use_default_colors()
            for i in range(0, curses.COLORS):
                curses.init_pair(i, i, -1)
        except:
            pass

        self.win_main = wnd = curses.newwin(*win_size)
        wnd.keypad(1)
        wnd.border(0)
        wnd.addstr(0, 2, " " + self.TITLE + " ")
        wnd.refresh()

    def get_curses_log_handler(self):
        """ Returns a handler for integrating log messages into the curses display
        if needed.

        :return: a log handler or None
        """
        return None

    def start(self):
        logger = log.getLogger()
        logger.info((' ' + self.TITLE + ' ').center(80, '-'))
        interrupted = False

        try:
            log.info('>>> Setting up')
            self.setup()

            log.info('>>> Running (Ctrl-C to interrupt)')
            self.run()

        except KeyboardInterrupt:
            print("\010\010  ")
            self.log.warn('--- Interrupted ---')
            interrupted = True

        except Exception as e:
            self.log.exception("Unexpected error: %s", e)

        finally:
            log.info('>>> Cleanup')
            self.cleanup(interrupted)
            if self.curses_log_handler:
                self.curses_log_handler.enabled = False

            if self._curses:
                log.info('>>> curses cleanup')
                curses = self._curses

                self.win_main.keypad(0)
                curses.nocbreak()
                curses.echo()
                curses.endwin()

            log.info('>>> All done.')

    def setup(self):
        pass

    def cleanup(self, interrupted=False):
        pass

    def run(self):
        raise NotImplementedError()

    @classmethod
    def main(cls, use_curses=False):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=textwrap.dedent(cls.__doc__ or '')
        )
        parser.add_argument('-D', '--debug', dest='debug', action='store_true', help='activates debug messages')

        args = parser.parse_args()
        demo = cls(log_level=log.DEBUG if args.debug else log.INFO, use_curses=use_curses)
        demo.start()


class CursesHandler(log.Handler):
    def __init__(self, wnd, attrs, unicode=True):
        self._unicode = unicode

        log.Handler.__init__(self)
        self.wnd = wnd
        _, self.wnd_w = wnd.getmaxyx()
        self.wnd_w -= 1
        self.attrs = attrs
        self.enabled = True

    def emit(self, record):
        if self.enabled:
            self.addstr(self.format(record))

    def addstr(self, msg):
        lines = msg.split('\n')
        self.wnd.addnstr(0, 0, lines[0].strip(), self.wnd_w, self.attrs)
        self.wnd.clrtoeol()
        self.wnd.refresh()


class SingledSPINDemo(DSPINDemo):
    def __init__(self, *args, **kwrgs):
        super(SingledSPINDemo, self).__init__(*args, **kwrgs)

        self.dspin = DSPIN(
            spi=self.spi,
            standby_pin=self.STANDBY_PIN,
            busyn_pin=self.BUSYN_PIN
        )
        if not self.dspin.initialize():
            sys.exit(1)

    def setup(self):
        super(SingledSPINDemo, self).setup()
        self.dspin.clear_status()

    def cleanup(self, interrupted=False):
        super(SingledSPINDemo, self).cleanup(interrupted)
        self.dspin.shutdown()


class MotorDemo(SingledSPINDemo):
    micro_steps = 128
    gear_ratio = 30
    steps_per_turn = 200
    max_speed = 800
    min_speed = 0
    acc = 0x4f
    dec = 0x4f
    kval_run = 0xff
    kval_acc = 0x7f
    kval_dec = 0x7f
    kval_hold = 0x0f
    fs_speed = max_speed / 2

    def setup(self):
        dspin = self.dspin

        dspin.STEP_MODE = StepMode.step_sel(self.micro_steps) | StepMode.SYNC_SEL_1
        dspin.MAX_SPEED = max_spd_calc(self.max_speed)
        dspin.MIN_SPEED = min_spd_calc(self.min_speed)
        dspin.FS_SPD = fs_spd_calc(self.fs_speed)
        dspin.ACC = self.acc
        dspin.DEC = self.dec
        dspin.OCD_TH = OverCurrentThreshold.TH_1500mA
        dspin.set_config(
            oc_sd=Configuration.OC_SD_DISABLE,
        )
        dspin.KVAL_RUN = self.kval_run
        dspin.KVAL_ACC = self.kval_acc
        dspin.KVAL_DEC = self.kval_dec
        dspin.KVAL_HOLD = self.kval_hold

        dspin.set_lspd_opt(True)


def main():
    MotorDemo.main(use_curses=True)
