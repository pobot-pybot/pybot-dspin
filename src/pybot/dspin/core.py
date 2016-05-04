# -*- coding: utf-8 -*-

import time

from pybot.core import log

from . import commands, pkg_log, GPIO, spidev
from .defs import Register, Status, Configuration, Direction, GoUntilAction

__author__ = 'Eric Pascual'


class DSPinSpiDev(spidev.SpiDev):
    """ A customized SPI device class, which fixes some settings such as the mode,
    according the dSPIN specificity.
    """
    log = pkg_log.getChild('spi')

    def __init__(self, spi_bus=0, spi_dev=0, max_speed_hz=500000):
        """
        :param int spi_bus: the SPI bus id (0 or 1, default:0)
        :param int spi_dev: the SPI device id (0 or 1, default:0)
        :param int max_speed_hz: the maximum clock speed (default: 500kHz)
        """
        super(DSPinSpiDev, self).__init__()

        self._bus = spi_bus
        self._dev = spi_dev
        self._max_speed = max_speed_hz

    def open(self):
        """ Opens the SPI device, using the settings provided at instantiation time.
        """
        super(DSPinSpiDev, self).open(self._bus, self._dev)

        self.mode = 3
        self.max_speed_hz = self._max_speed

        self.log.debug("SPI open done (bus=%d device=%d)", self._bus, self._dev)

    def xfer(self, values=None):
        """ Send data, toggling CS for each byte.

        Unlike stated in the documentation, the CS line is held during the whole transfer,
        whatever method (xfer or xfer2) is used.
        We thus cannot use a single call to send the message and instead need
        to loop and send bytes one at a time.

        :param iterable values: the bytes to be sent
        :return: the received bytes
        :rtype: list
        """
        result = []
        for b in values:
            result.extend(super(DSPinSpiDev, self).xfer([b]))

        if self.log.getEffectiveLevel() == log.DEBUG:
            self.log.debug('_xfer(%s) -> %s', bytes_as_string(values), bytes_as_string(result))

        return result

    def xfer2(self, values=None):
        """ Send data, toggling CS only before and after the message.

        :param iterable values: the bytes to be sent
        :return: the received bytes
        :rtype: list
        """
        result = super(DSPinSpiDev, self).xfer(list(values))

        if self.log.getEffectiveLevel() == log.DEBUG:
            self.log.debug('_xfer2(%s) -> %s', bytes_as_string(values), bytes_as_string(result))

        return result


class DSPIN(object):
    """ Model of the dSPIN module.
    """
    def __init__(self, spi, standby_pin, busyn_pin, switch_pin=None):
        """
        :param DSPinSpiDev spi: the SPI device instance, which can be shared by several dSPINs
        :param int standby_pin: GPIO number of the standby signal
        :param int busyn_pin: GPIO number of the busy signal
        :param int switch_pin: GPIO number of the switch input signal
        """
        if not spi:
            raise ValueError('spi parameter missing')

        self._spi = spi
        self._standby_pin = standby_pin
        self._busyn_pin = busyn_pin
        self._switch_pin = switch_pin
        self.log = pkg_log.getChild(self.__class__.__name__)

    def power_on_reset(self):
        """ Performs initializations which are supposed to be done
        once for all the devices.
        """
        GPIO.setup(self._standby_pin, GPIO.OUT)
        self.log.debug('GPIO.OUT reset setup ok')
        GPIO.setup(self._busyn_pin, GPIO.IN)
        self.log.debug('GPIO.IN busy setup ok')
        if self._switch_pin is not None:
            GPIO.setup(self._switch_pin, GPIO.IN)
            self.log.debug('GPIO.IN switch setup ok')

        self._spi.open()

        # reset the chip by switching to standby mode and then waking up back
        self.awake()
        self.standby()
        time.sleep(0.001)
        self.awake()

    def check_initial_config(self):
        config = self.CONFIG
        self.log.debug('config: 0x%x', config)
        return config == Register.CONFIG.reset_value

    def prepare(self):
        """ Performs the initializations and checking specific for each
        device.
        """
        # check that the initialization went well by comparing the configuration
        # with the default one after reset
        # Note that the access to the CONFIG register being made using GetStatus
        # function, it will reset the error flags at the same time, UVO among others.
        if not self.check_initial_config():
            self.log.error('reset sequence failed')
            return False

        # ensure HiZ, since configuration is not modifiable otherwise
        self.hard_hi_Z()

        # clear UVLO flag (forced high on POR)
        self.clear_status()

        self.log.info('reset sequence complete')
        return True

    def initialize(self):
        """ Makes the instance ready to work, by opening the SPI device and
        resetting the dSPIN chip.

        The state of the chip is checked by comparing the configuration register
        content with the value after reset provided in the datasheet.

        :return: True if initialisation ok
        """
        self.power_on_reset()
        return self.prepare()

    def shutdown(self):
        """ Shutdowns the device by stopping any ongoing action, putting the
        drivers in HiZ and then switching to standby mode.
        """
        self.clear_status()
        self.hard_hi_Z()
        self.standby()

    def standby(self):
        """ Goes standby
        """
        GPIO.output(self._standby_pin, GPIO.LOW)

    def awake(self):
        """ Awakes and wait enough for everybody ready (min: 45us + 650us)
        """
        GPIO.output(self._standby_pin, GPIO.HIGH)
        time.sleep(0.001)

    def _xfer(self, data):
        """ Low level data transfer.

        The default version transfers the data on the associated SPI bus.
        The process has been isolated in a specific method so that it can be
        altered by derived classes (e.g. daisy chain).

        :param list data: the list of bytes to be sent
        :return: the data returned by the dSPIN
        :rtype: list
        """
        return self._spi.xfer(data)

    def read_register(self, reg):
        """ Reads a register and returns its value.

        :param reg: the register to be read, as one of the Register.XXXX predefined values.
        :return: the register value
        """
        if self.log.getEffectiveLevel() == log.DEBUG:
            self.log.debug('DSPIN.read_register(%s)...', reg.name)
        value_bytes = self._xfer(commands.GetParam(reg).as_request())[1:]
        result = self.parse_register_reply(reg, value_bytes)
        if self.log.getEffectiveLevel() == log.DEBUG:
            self.log.debug(' -> 0x%x', result)
        return result

    def parse_register_reply(self, reg, value_bytes):
        mask = 0xffffffff >> (32 - reg.size)
        raw_value = reduce(lambda a, b: (a << 8) | b, value_bytes) & mask
        if reg.signed:
            if raw_value & (1 << (reg.size - 1)):
                return raw_value - (1 << reg.size)
        return raw_value

    def write_register(self, reg, value):
        """ Changes a register value.

        Care is taken to format the SPI request according to the register properties
        (address, size,...)

        :param reg: the register to be written, as one of the Register.XXXX predefined values.
        :param int value: the value to be written
        """
        if self.log.getEffectiveLevel() == log.DEBUG:
            self.log.debug('write_register(%s, 0x%x)', reg.name, value)
        self._xfer(commands.SetParam(reg, value).as_request())

    @staticmethod
    def _register_as_property(reg):
        def getter(self):
            return self.read_register(reg)

        def setter(self, value):
            return self.write_register(reg, value)

        return property(fget=getter, fset=None if reg.read_only else setter)

    ABS_POS = _register_as_property.__func__(Register.ABS_POS)
    EL_POS = _register_as_property.__func__(Register.EL_POS)
    MARK = _register_as_property.__func__(Register.MARK)
    SPEED = _register_as_property.__func__(Register.SPEED)
    ACC = _register_as_property.__func__(Register.ACC)
    DEC = _register_as_property.__func__(Register.DEC)
    MAX_SPEED = _register_as_property.__func__(Register.MAX_SPEED)
    MIN_SPEED = _register_as_property.__func__(Register.MIN_SPEED)
    FS_SPD = _register_as_property.__func__(Register.FS_SPD)
    KVAL_HOLD = _register_as_property.__func__(Register.KVAL_HOLD)
    KVAL_RUN = _register_as_property.__func__(Register.KVAL_RUN)
    KVAL_ACC = _register_as_property.__func__(Register.KVAL_ACC)
    KVAL_DEC = _register_as_property.__func__(Register.KVAL_DEC)
    INT_SPD = _register_as_property.__func__(Register.INT_SPD)
    ST_SLP = _register_as_property.__func__(Register.ST_SLP)
    FN_SLP_ACC = _register_as_property.__func__(Register.FN_SLP_ACC)
    FN_SLP_DEC = _register_as_property.__func__(Register.FN_SLP_DEC)
    K_THERM = _register_as_property.__func__(Register.K_THERM)
    ADC_OUT = _register_as_property.__func__(Register.ADC_OUT)
    OCD_TH = _register_as_property.__func__(Register.OCD_TH)
    STALL_TH = _register_as_property.__func__(Register.STALL_TH)
    STEP_MODE = _register_as_property.__func__(Register.STEP_MODE)
    ALARM_EN = _register_as_property.__func__(Register.ALARM_EN)
    STATUS = _register_as_property.__func__(Register.STATUS)
    CONFIG = _register_as_property.__func__(Register.CONFIG)

    @property
    def switch_is_closed(self):
        """ Tells if the switch is closed.
        """
        return bool(self.STATUS & Status.SW_F)

    def set_lspd_opt(self, enable):
        """ Configures the low speed optimization option.

        :param boolean enable: should it be enabled or not
        """
        self.MIN_SPEED = 0x1000 if enable else 0

    def set_config(self,
                   osc_sel=Configuration.OSC_SEL_INT_16MHZ_OSCOUT_2MHZ,
                   sw_mode=Configuration.SW_MODE_HARD_STOP,
                   en_vscomp=Configuration.EN_VSCOMP_DISABLE,
                   oc_sd=Configuration.OC_SD_ENABLE,
                   pow_sr=Configuration.POW_SR_290V_us,
                   f_pwm_dec=Configuration.F_PWM_DEC_1,
                   f_pwm_int=Configuration.F_PWM_INT_2
                   ):
        """ Convenience method for setting the CONFIG register value,
        by providing defaults for fields based on the configuration after reset.

        :param osc_sel: OSC_SEL field value (includes the EXT_CLK original field of the register)
        :param sw_mode: SW_MODE field value
        :param en_vscomp: EN_VSCOMP field value
        :param oc_sd:  OC_SD field value
        :param pow_sr: POW_SR field value
        :param f_pwm_dec: F_PWM_DEC field value
        :param f_pwm_int: F_PWM_INT field value
        """
        config = Configuration(osc_sel, sw_mode, en_vscomp, oc_sd, pow_sr, f_pwm_dec, f_pwm_int)
        self.log.debug('set_config(0x%x) %s', config.value, config)
        self.CONFIG = config.value

    def get_status(self):
        """ Reads the STATUS register content and clear its error flags.

        .. note::

            For code readability's sake, this method should not be used for the
            following reasons :

            - If what is needed is the content of the register, using the `STATUS` property
            is more straight forward.

            - If what is needed is clearing the flags, using :py:meth:`clear_status` is
            more self-explanatory.

        :return: the register value
        """
        data = self._xfer(commands.GET_STATUS_REQUEST)[1:]
        return (data[0] << 8) | data[1]

    def clear_status(self):
        """ Clears the status flags by issuing the GetStatus command.

        This is basically the same as :py:meth:`get_status`, but we don't care
        about the result here and the name of the method is more relevant when
        what is needed by the caller is to clear the flags and not reading the
        register.
        """
        self._xfer(commands.GET_STATUS_REQUEST)

    def run(self, direction, steps_per_sec):
        """ Starts the motor in a given direction and at a given speed.

        :param int direction: one of :py:class:`Direction` predefined values
        :param int steps_per_sec: speed in steps/s (accounting micro-stepping)
        """
        self._xfer(commands.Run(direction, steps_per_sec).as_request())

    def step_clock(self, direction):
        """ Moves one step in the given direction.

        :param int direction: one of :py:class:`Direction` predefined values
        """
        self._spi.xfer(commands.StepClock(direction).as_request())

    def move(self, direction, steps, wait=True, wait_cb=None):
        """ Moves a given number of steps from the current position, in the given direction.

        :param int direction: one of :py:class:`Direction` predefined values
        :param int steps: number of steps (accounting micro-stepping)
        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.Move(direction, steps).as_request())
        if wait:
            self.wait_for_move_complete(wait_cb)

    def goto(self, position, wait=True, wait_cb=None):
        """ Moves to a given absolute position, optimizing the direction.

        :param int position: the target position (accounting micro-stepping)
        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.GoTo(position).as_request())
        if wait:
            self.wait_for_move_complete(wait_cb)

    def goto_dir(self, direction, position, wait=True, wait_cb=None):
        """ Same as :py:meth:`goto`, but imposing the diection.

        :param int direction: one of :py:class:`Direction` predefined values
        :param int position: the target position (accounting micro-stepping)
        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.GoToDir(direction, position).as_request())
        if wait:
            self.wait_for_move_complete(wait_cb)

    def go_home(self, wait=True, wait_cb=None):
        """ Returns to home position (abs pos = 0), using the shortest path.

        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.GO_HOME_REQUEST)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def go_mark(self, wait=True, wait_cb=None):
        """ Returns to a previously marked position, using the shortest path.

        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.GO_MARK_REQUEST)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def go_until(self, action, direction, steps_per_sec, wait=True, wait_cb=None):
        """ Runs in the given direction, until the switch is closed.

        Once there, performs the indicated action.

        :param int action: one of :py:class:`GoUntilAction` predefined actions
        :param int direction: one of :py:class:`Direction` predefined values
        :param int steps_per_sec: speed in steps/s (accounting micro-stepping)
        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.GoUntil(action, direction, steps_per_sec).as_request())
        if wait:
            self.wait_for_move_complete(wait_cb)

    def release_sw(self, action, direction, wait=True, wait_cb=None):
        """ Runs in the given direction, until the switch is released.

        Once there, performs the indicated action. The move is performed at the currently
        set minimum speed.

        :param int action: one of :py:class:`GoUntilAction` predefined actions
        :param int direction: one of :py:class:`Direction` predefined values
        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.ReleaseSW(action, direction).as_request())
        if wait:
            self.wait_for_move_complete(wait_cb)

    def reset_pos(self):
        """ Resets the absolute position indicator.
        """
        self._xfer(commands.RESET_POS_REQUEST)

    def reset_device(self):
        """ Resets the device in initial conditions (same effect as standby/awake cycle).
        """
        self._xfer(commands.RESET_DEVICE_REQUEST)

    def soft_stop(self, wait=True, wait_cb=None):
        """ Performs a soft stop.

        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.SOFT_STOP_REQUEST)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def hard_stop(self):
        """ Performs a hard stop.
        """
        self._xfer(commands.HARD_STOP_REQUEST)

    def soft_hi_Z(self, wait=True, wait_cb=None):
        """ Performs a soft stop and puts the bridge in HiZ state.

        :param bool wait: wait until the move is finished before returning
        :param wait_cb: an optional callback to be called while waiting
        """
        self._xfer(commands.SOFT_HIZ_REQUEST)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def hard_hi_Z(self):
        """ Performs a hard stop and puts the bridge in HiZ state.
        """
        self._xfer(commands.HARD_HIZ_REQUEST)

    def is_moving(self):
        """ Tells if the motor is moving, by checking the busy signal.

        :rtype: bool
        """
        return GPIO.input(self._busyn_pin) == GPIO.LOW

    def wait_for_move_complete(self, callback=None):
        """ Waits until the current move is complete.

        If provided, the callback will be invoked while executing
        the in the monitoring loop, with the dSPIN instance as argument.

        :param callback: the callback to invoke while waiting
        """
        if hasattr(GPIO, 'FAKE'):
            self.log.warn('not on a real RasPi => bypassing wait_for_move_complete')
            return

        # use 2 distinct loops for avoiding testing for the callback
        # on each iteration and impacting performances
        self.log.debug('wait_for_move_complete...')
        if callback:
            while GPIO.input(self._busyn_pin) == GPIO.LOW:
                callback(self)
                time.sleep(0.1)
        else:
            while GPIO.input(self._busyn_pin) == GPIO.LOW:
                time.sleep(0.1)

    def get_all_registers(self):
        """ Returns the current content of all the registers as a list of tuples (name, value).

        :rtype: list
        """
        return [(n, getattr(self, n)) for n in Register.ALL]


def bytes_as_string(data):
    return ', '.join(('0x%0x' % b for b in data))


def values_as_string(values):
    return ', '.join(('0x%0x' % v if v is not None else 'None' for v in values))
