# -*- coding: utf-8 -*-

""" Base definitions for dSPIN library
"""

from collections import namedtuple

__author__ = 'Eric Pascual'


class RegisterDefinition(namedtuple('RegisterDefinition', 'name, addr, size, signed, reset_value, read_only')):
    """ The definition of a dSPIN register """
    __slots__ = ()

    def __new__(cls, name, addr, size, signed=False, reset_value=0, read_only=False):
        """
        :param str name: register name
        :param int addr: register address
        :param int size: register size (in bits)
        :param bool signed: True if value encoded as a two's complement signed int
        :param int reset_value: register content after chip reset
        :param boolean read_only: is the register read-only ?
        """
        return super(RegisterDefinition, cls).__new__(cls, name, addr, size, signed, reset_value, read_only)


class Register(object):
    """ The collection of dSPIN register definitions, accompanied by convenience methods.
    """
    ABS_POS = RegisterDefinition('ABS_POS', 0x01, 22, signed=True)
    EL_POS = RegisterDefinition('EL_POS', 0x02, 9)
    MARK = RegisterDefinition('MARK', 0x03, 22)
    SPEED = RegisterDefinition('SPEED', 0x04, 20, read_only=True)
    ACC = RegisterDefinition('ACC', 0x05, 12, reset_value=0x8a)
    DEC = RegisterDefinition('DEC', 0x06, 12, reset_value=0x8a)
    MAX_SPEED = RegisterDefinition('MAX_SPEED', 0x07, 10, reset_value=0x41)
    MIN_SPEED = RegisterDefinition('MIN_SPEED', 0x08, 13)
    FS_SPD = RegisterDefinition('FS_SPD', 0x15, 10, reset_value=0x27)
    KVAL_HOLD = RegisterDefinition('KVAL_HOLD', 0x09, 8, reset_value=0x29)
    KVAL_RUN = RegisterDefinition('KVAL_RUN', 0x0A, 8, reset_value=0x29)
    KVAL_ACC = RegisterDefinition('KVAL_ACC', 0x0B, 8, reset_value=0x29)
    KVAL_DEC = RegisterDefinition('KVAL_DEC', 0x0C, 8, reset_value=0x29)
    INT_SPD = RegisterDefinition('INT_SPD', 0x0D, 14, reset_value=0x408)
    ST_SLP = RegisterDefinition('ST_SLP', 0x0E, 8, reset_value=0x19)
    FN_SLP_ACC = RegisterDefinition('FN_SLP_ACC', 0x0F, 8, reset_value=0x29)
    FN_SLP_DEC = RegisterDefinition('FN_SLP_DEC', 0x10, 8, reset_value=0x29)
    K_THERM = RegisterDefinition('K_THERM', 0x11, 4)
    ADC_OUT = RegisterDefinition('ADC_OUT', 0x12, 5, read_only=True)
    OCD_TH = RegisterDefinition('OCD_TH', 0x13, 4, reset_value=0x08)
    STALL_TH = RegisterDefinition('STALL_TH', 0x14, 7, reset_value=0x40)
    STEP_MODE = RegisterDefinition('STEP_MODE', 0x16, 8, reset_value=0x07)
    ALARM_EN = RegisterDefinition('ALARM_EN', 0x17, 8, reset_value=0xff)
    CONFIG = RegisterDefinition('CONFIG', 0x18, 16, reset_value=0x2e88)
    STATUS = RegisterDefinition('STATUS', 0x19, 16, read_only=True)

    #: the complete list of registers (initialized by introspection at module level)
    ALL = None

    @classmethod
    def value_as_bytes(cls, reg, value):
        """ Returns a register value as the list of bytes corresponding to its size, ready
        to be transferred via SPI.

        The returned list is MSB first. The computation is optimized for null value.

        .. note::

            Since Python handles negative integers as two's complement, there is nothing
            special to do here.

        :param RegisterDefinition reg: the register descriptor
        :param int value: the register value
        :return: the corresponding list of bytes to be transferred
        :rtype: list
        """
        size = reg.size
        bytes_cnt = (size >> 3) + (1 if size & 7 else 0)
        result = [0] * bytes_cnt

        # optimize for value == 0
        if value == 0:
            return result

        mask = 0x0ffffffff >> (32 - size)
        value &= mask

        for i in range(bytes_cnt):
            result[bytes_cnt - i - 1] = int(value & 0x0ff)
            value >>= 8
        return result

Register.ALL = sorted([n for n in dir(Register) if n.isupper() and n is not "ALL"])


def acc_calc(steps_per_sec_per_sec):
    """ Converts an acceleration into the proper register value

    :param int steps_per_sec_per_sec: acceleration in steps/s^2
    :return: the register value
    """
    return min(int(abs(steps_per_sec_per_sec) * 0.137438), 0x0fff)

#: The deceleration formula is the same as the acceleration one
dec_calc = acc_calc


def max_spd_calc(steps_per_sec):
    """ Converts a speed into the proper value for the MAX_SPEED register

    :param int steps_per_sec: speed in steps/s
    :return: the register value
    """
    return min(int(abs(steps_per_sec) * 0.065536), 0x03ff)


def min_spd_calc(steps_per_sec):
    """ Converts a speed into the proper value for the MIN_SPEED register

    :param int steps_per_sec: speed in steps/s
    :return: the register value
    """
    return min(int(abs(steps_per_sec) * 4.1943), 0x0fff)


def fs_spd_calc(steps_per_sec):
    """ Converts a speed into the proper value for the FS_SPD register

    :param int steps_per_sec: speed in steps/s
    :return: the register value
    """
    return min(int(abs(steps_per_sec) * .065536 - 0.5), 0x03ff)


def int_spd_calc(steps_per_sec):
    """ Converts a speed into the proper value for the INT_SPD register

    :param int steps_per_sec: speed in steps/s
    :return: the register value
    """
    return min(int(abs(steps_per_sec) * 4.1943), 0x3fff)


def spd_calc(steps_per_sec):
    """ Converts a speed into the proper value for the SPEED register

    :param int steps_per_sec: speed in steps/s
    :return: the register value
    """
    return min(int(abs(steps_per_sec) * 67.106), 0x0fffff)


class Direction(object):
    """ Move Direction parameter """
    REV = 0
    FWD = 0x01
    MASK = 0x01

    @classmethod
    def invert(cls, direction):
        return cls.REV if direction == cls.FWD else cls.FWD


class GoUntilAction(object):
    """ GoUntil/ReleaseSW action parameter definition
    """
    RESET = 0
    COPY = 0x08
    MASK = 0x08


class Status(object):
    """ Status register decoding.
    """
    HiZ = 0x0001
    BUSY = 0x0002
    SW_F = 0x0004
    SW_EVN = 0x0008
    DIR = 0x0010
    MOT_STATUS = 0x0060
    NOTPERF_CMD = 0x0080
    WRONG_CMD = 0x0100
    UVLO = 0x0200
    TH_WRN = 0x0400
    TH_SD = 0x0800
    OCD = 0x1000
    STEP_LOSS_A = 0x2000
    STEP_LOSS_B = 0x4000
    STEP_LOSS = 0x6000
    SCK_MODE = 0x8000

    @classmethod
    def as_tuple(cls, value):
        """ Decodes a register value an returns it as a list of tuples giving the
        values of individual bit-fields.

        :param int value: the value to be decoded
        :return: decoded value
        :rtype: list
        """
        return (
            ('HiZ', int(value & cls.HiZ)),
            ('BUSY', int(value & cls.BUSY) >> 1),
            ('SW_F', int(value & cls.SW_F) >> 2),
            ('SW_EVN', int(value & cls.SW_EVN) >> 3),
            ('DIR', int(value & cls.DIR) >> 4),
            ('MOT_STATUS', int(value & cls.MOT_STATUS) >> 5),
            ('NOTPERF_CMD', int(value & cls.NOTPERF_CMD) >> 7),
            ('WRONG_CMD', int(value & cls.WRONG_CMD) >> 8),
            ('UVLO', int(value & cls.UVLO) >> 9),
            ('TH_WRN', int(value & cls.TH_WRN) >> 10),
            ('TH_SD', int(value & cls.TH_SD) >> 11),
            ('OCD', int(value & cls.OCD) >> 12),
            ('STEP_LOSS_A', int(value & cls.STEP_LOSS_A) >> 13),
            ('STEP_LOSS_B', int(value & cls.STEP_LOSS_B) >> 14),
            ('SCK_MOD', int(value & cls.SCK_MODE) >> 15),
        )

    @classmethod
    def as_string(cls, value):
        """ String human friendly representation of a status value.

        :param int value: the status value
        :return: its string representation
        :rtype: str
        """
        return ' '.join(("%s:%d" % (n, v) for n, v in cls.as_tuple(value)))


class MotorStatus(object):
    """ Possible motor statuses """
    STOPPED, ACCEL, DECEL, CONSTANT_SPEED = range(4)

    _all_ = ('STOPPED', 'ACCEL', 'DECEL', 'CONSTANT_SPEED')

    @classmethod
    def as_string(cls, value):
        return cls._all_[value]


class OverCurrentThreshold(object):
    """ Possible over-current thresholds """
    TH_375mA, TH_750mA, TH_1125mA, TH_1500mA, TH_1875mA, TH_2250mA, TH_2625mA, TH_3000mA, TH_3375mA, TH_3750mA, \
    TH_4125mA, TH_4500mA, TH_4875mA, TH_5250mA, TH_5625mA, TH_6000mA = range(16)

    _all_ = ('375mA', '750mA', '1125mA', '1500mA', '1875mA', '2250mA', '2625mA', '3000mA',
             '3375mA', '3750mA', '4125mA', '4500mA', '4875mA', '5250mA', '5625mA', '6000mA')

    @classmethod
    def as_string(cls, value):
        return cls._all_[value]


class StepMode(object):
    """ Possible step modes """
    STEP_SEL_1, STEP_SEL_1_2, STEP_SEL_1_4, STEP_SEL_1_8, STEP_SEL_1_16, \
    STEP_SEL_1_32, STEP_SEL_1_64, STEP_SEL_1_128 = range(8)
    STEP_SEL_MASK = 0x07

    _strs_ = ('FULL', '1/2', '1/4', '1/8', '1/16', '1/32', '1/64', '1/128')

    SYNC_EN = 0x80
    SYNC_EN_MASK = 0x80

    SYNC_SEL_1_2 = 0x00
    SYNC_SEL_1 = 0x10
    SYNC_SEL_2 = 0x20
    SYNC_SEL_4 = 0x30
    SYNC_SEL_8 = 0x40
    SYNC_SEL_16 = 0x50
    SYNC_SEL_32 = 0x60
    SYNC_SEL_64 = 0x70
    SYNC_SEL_MASK = 0x70

    @classmethod
    def as_string(cls, value):
        return cls._strs_[value & cls.STEP_SEL_MASK]

    @classmethod
    def step_sel(cls, micro_steps):
        """ Returns the StepSel field value corresponding to a given micro-step setting.
        :param int micro_steps: micro-steps count (1=full step, 2=half step,...)
        :return: the StepSel value
        :rtype: int
        """
        if micro_steps == 1:
            return cls.STEP_SEL_1
        else:
            try:
                return getattr(cls, "STEP_SEL_1_%d" % micro_steps)
            except (AttributeError, ValueError):
                raise ValueError("invalid micro_steps value (%s)" % micro_steps)


class AlarmEnable(object):
    """ Alarm enabling flags """
    OVERCURRENT = 0x01
    THERMAL_SHUTDOWN = 0x02
    THERMAL_WARNING = 0x04
    UNDER_VOLTAGE = 0x08
    STALL_DET_A = 0x10
    STALL_DET_B = 0x20
    SW_TURN_ON = 0x40
    WRONG_NPERF_CMD = 0x80

    _all_ = (
        'OVERCURRENT', 'THERMAL_SHUTDOWN', 'THERMAL_WARNING', 'UNDER_VOLTAGE', 'STALL_DET_A', 'STALL_DET_B',
        'SW_TURN_ON', 'WRONG_NPERF_CMD'
    )

    @classmethod
    def as_tuple(cls, value):
        """ Decodes the enabling settings as a tuple containing the activated alarms.

        :param int value: the register value
        :return: the list of enabled alarms
        :rtype: tuple
        """
        return tuple((f for f in cls._all_ if value & getattr(cls, f)))

    @classmethod
    def as_string(cls, value):
        return ' '.join(cls.as_tuple(value))


class Configuration(object):
    """ Configuration register model. """

    OSC_SEL_MASK = 0x000F
    OSC_SEL_INT_16MHZ = 0x0000
    OSC_SEL_INT_16MHZ_OSCOUT_2MHZ = 0x0008
    OSC_SEL_INT_16MHZ_OSCOUT_4MHZ = 0x0009
    OSC_SEL_INT_16MHZ_OSCOUT_8MHZ = 0x000A
    OSC_SEL_INT_16MHZ_OSCOUT_16MHZ = 0x000B
    OSC_SEL_EXT_8MHZ_XTAL_DRIVE = 0x0004
    OSC_SEL_EXT_16MHZ_XTAL_DRIVE = 0x0005
    OSC_SEL_EXT_24MHZ_XTAL_DRIVE = 0x0006
    OSC_SEL_EXT_32MHZ_XTAL_DRIVE = 0x0007
    OSC_SEL_EXT_8MHZ_OSCOUT_INVERT = 0x000C
    OSC_SEL_EXT_16MHZ_OSCOUT_INVERT = 0x000D
    OSC_SEL_EXT_24MHZ_OSCOUT_INVERT = 0x000E
    OSC_SEL_EXT_32MHZ_OSCOUT_INVERT = 0x000F

    SW_MODE_MASK = 0x0010
    SW_MODE_HARD_STOP = 0x0000
    SW_MODE_USER = 0x0010

    EN_VSCOMP_MASK = 0x0020
    EN_VSCOMP_DISABLE = 0x0000
    EN_VSCOMP_ENABLE = 0x0020

    OC_SD_MASK  = 0x0080
    OC_SD_DISABLE = 0x0000
    OC_SD_ENABLE = 0x0080

    POW_SR_MASK = 0x0300
    POW_SR_180V_us = 0x0000
    POW_SR_290V_us = 0x0200
    POW_SR_530V_us = 0x0300

    F_PWM_DEC_MASK = 0x07 << 10
    F_PWM_DEC_0_625 = 0x00 << 10
    F_PWM_DEC_0_75 = 0x01 << 10
    F_PWM_DEC_0_875 = 0x02 << 10
    F_PWM_DEC_1 = 0x03 << 10
    F_PWM_DEC_1_25 = 0x04 << 10
    F_PWM_DEC_1_5 = 0x05 << 10
    F_PWM_DEC_1_75 = 0x06 << 10
    F_PWM_DEC_2 = 0x07 << 10

    F_PWM_INT_MASK = 0x07 << 13
    F_PWM_INT_1 = 0x00 << 13
    F_PWM_INT_2 = 0x01 << 13
    F_PWM_INT_3 = 0x02 << 13
    F_PWM_INT_4 = 0x03 << 13
    F_PWM_INT_5 = 0x04 << 13
    F_PWM_INT_6 = 0x05 << 13
    F_PWM_INT_7 = 0x06 << 13

    @classmethod
    def as_tuple(cls, value):
        """ Decodes a register value an returns it as a list of tuples giving the
        values of individual bit-fields.

        :param int value: the value to be decoded
        :return: decoded value
        :rtype: tuple
        """
        return (
            ('OSC_SEL', int(value & cls.OSC_SEL_MASK)),
            ('SW_MODE', int(value & cls.SW_MODE_MASK) >> 4),
            ('EN_VSCOMP', int(value & cls.EN_VSCOMP_MASK) >> 5),
            ('OC_SD', int(value & cls.OC_SD_MASK) >> 7),
            ('POW_SR', int(value & cls.POW_SR_MASK) >> 8),
            ('F_PWM_DEC', int(value & cls.F_PWM_DEC_MASK) >> 10),
            ('F_PWM_INT', int(value & cls.F_PWM_INT_MASK) >> 13),
        )

    @classmethod
    def as_string(cls, value):
        """ Human friendly string representation of a configuration register value.

        :param int value: the register value
        :return: the string representation
        :rtype: str
        """
        return ' '.join(("%s:%d" % (n, v) for n, v in cls.as_tuple(value)))

    def __init__(self,
                   osc_sel=OSC_SEL_INT_16MHZ_OSCOUT_2MHZ,
                   sw_mode=SW_MODE_HARD_STOP,
                   en_vscomp=EN_VSCOMP_DISABLE,
                   oc_sd=OC_SD_ENABLE,
                   pow_sr=POW_SR_290V_us,
                   f_pwm_dec=F_PWM_DEC_1,
                   f_pwm_int=F_PWM_INT_2
                   ):
        """
        :param osc_sel: OSC_SEL field value (includes the EXT_CLK original field of the register)
        :param sw_mode: SW_MODE field value
        :param en_vscomp: EN_VSCOMP field value
        :param oc_sd:  OC_SD field value
        :param pow_sr: POW_SR field value
        :param f_pwm_dec: F_PWM_DEC field value
        :param f_pwm_int: F_PWM_INT field value
        """
        self.value = osc_sel | sw_mode | en_vscomp | oc_sd | pow_sr | f_pwm_dec | f_pwm_int

    def __str__(self):
        return self.as_string(self.value)
