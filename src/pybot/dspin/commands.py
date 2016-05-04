# -*- coding: utf-8 -*-

""" This modules defines a model for working with dSPIN commands
in an encapsulated way, so that higher level classes such as
:py:class:`DSPIN` or :py:class:`DaisyChain` do not have to care with
byte streams building.
"""

import defs
from defs import Register, RegisterDefinition

__author__ = 'Eric Pascual'


class OpCodes(object):
    """ An enumeration of op-codes used in dSPIN commands.
    """
    NOP = 0x00
    SET_PARAM = 0x00
    GET_PARAM = 0x20
    RUN = 0x50
    STEP_CLOCK = 0x58
    MOVE = 0x40
    GOTO = 0x60
    GOTO_DIR = 0x68
    GO_UNTIL = 0x82
    RELEASE_SW = 0x92
    GO_HOME = 0x70
    GO_MARK = 0x78
    RESET_POS = 0xD8
    RESET_DEVICE = 0xC0
    SOFT_STOP = 0xB0
    HARD_STOP = 0xB8
    SOFT_HIZ = 0xA0
    HARD_HIZ = 0xA8
    GET_STATUS = 0xD0

    _all = (
        NOP, SET_PARAM, GET_PARAM, RUN, STEP_CLOCK, MOVE, GOTO, GOTO_DIR, GO_UNTIL, RELEASE_SW, GO_HOME, GO_MARK,
        RESET_POS, RESET_DEVICE, SOFT_STOP, HARD_STOP, SOFT_HIZ, HARD_HIZ, GET_STATUS
    )

    @classmethod
    def is_valid_opcode(cls, value):
        """ Returns True if the passed value is a valid op-code, False otherwise.
        """
        return value in cls._all

    @classmethod
    def check_opcode(cls, value):
        """ Raises a ValueError exception if the passed value is not a valid op-code.
        """
        if value not in cls._all:
            raise ValueError('invalid opcode')


class Command(object):
    """ Root (abstract) class for the commands model.

    All command model classes must implement the :py:meth:`as_request` methode
    which returns SPI request to be sent for this command.
    """
    def as_request(self):
        """ Returns the SPI request for this command

        :return: the SPI request
        :rtype: list
        """
        raise NotImplementedError()


class SimpleCommand(Command):
    """ A simple parameter-less command.

    .. note::

        Since they are fixed, their usage can be optimized by pre-defining constants
        containing the equivalent SPI requests.
    """
    def __init__(self, opcode, size=1):
        """
        :param int opcode: one of the OpCodes values
        :param int size: the size of the command request (default: 1, i.e. reduced to the opcode)
        :raise: ValueError is an invalid opcode or a negative size is passed
        """
        OpCodes.check_opcode(opcode)

        # 'size' sign checking is not really needed, since the padding will be empty if negative,
        # but it can be useful to detect a bug in the parameter value elaboration
        if size < 0:
            raise ValueError('invalid size')

        self._opcode = opcode
        self._padding = [OpCodes.NOP] * (size - 1)

    def as_request(self):
        return [self._opcode] + self._padding


class Nop(SimpleCommand):
    """ The do-nothing command, used to pad daisy-chain transactions when only some of
    the devices are involved.
    """
    def __init__(self, size=1):
        """
        :param int size: the size of the desired NOP request
        """
        super(Nop, self).__init__(OpCodes.NOP, size)


#: a 1 byte long NOP
NOP_1 = Nop(size=1)
#: a 2 bytes long NOP
NOP_2 = Nop(size=2)
#: a 3 bytes long NOP
NOP_3 = Nop(size=3)
#: a 4 bytes long NOP
NOP_4 = Nop(size=4)
#: alias for the single byte NOP
NOP = NOP_1

#: GoHome command
GO_HOME = SimpleCommand(OpCodes.GO_HOME)
#: GoMark command
GO_MARK = SimpleCommand(OpCodes.GO_MARK)
#: ResetPos command
RESET_POS = SimpleCommand(OpCodes.RESET_POS)
#: ResetDevice command
RESET_DEVICE = SimpleCommand(OpCodes.RESET_DEVICE)
#: SoftStop command
SOFT_STOP = SimpleCommand(OpCodes.SOFT_STOP)
#: HardStop command
HARD_STOP = SimpleCommand(OpCodes.HARD_STOP)
#: SoftHiZ command
SOFT_HIZ = SimpleCommand(OpCodes.SOFT_HIZ)
#: HardHiZ command
HARD_HIZ = SimpleCommand(OpCodes.HARD_HIZ)
#: GetStatus command
GET_STATUS = SimpleCommand(OpCodes.GET_STATUS, size=3)

#: NOP_1 command SPI request
NOP_1_REQUEST = NOP_1.as_request()
#: NOP_2 command SPI request
NOP_2_REQUEST = NOP_2.as_request()
#: NOP_3 command SPI request
NOP_3_REQUEST = NOP_3.as_request()
#: NOP_4 command SPI request
NOP_4_REQUEST = NOP_4.as_request()
#: NOP command SPI request
NOP_REQUEST = NOP_1_REQUEST

#: GoHome command SPI request
GO_HOME_REQUEST = GO_HOME.as_request()
#: GoMark command SPI request
GO_MARK_REQUEST = GO_MARK.as_request()
#: ResetPos command SPI request
RESET_POS_REQUEST = RESET_POS.as_request()
#: ResetDevice command SPI request
RESET_DEVICE_REQUEST = RESET_DEVICE.as_request()
#: SoftStop command SPI request
SOFT_STOP_REQUEST = SOFT_STOP.as_request()
#: HARD_STOP command SPI request
HARD_STOP_REQUEST = HARD_STOP.as_request()
#: SoftHiZ command SPI request
SOFT_HIZ_REQUEST = SOFT_HIZ.as_request()
#: HARD_HIZ command SPI request
HARD_HIZ_REQUEST = HARD_HIZ.as_request()
#: GetStatus command SPI request
GET_STATUS_REQUEST = GET_STATUS.as_request()

#: An alias of Command, for marking the parametric commands classes sub-tree
ParametricCommand = Command


class RegisterCommandMixin(object):
    """ A mixin factoring common process for commands manipulating registers. """

    def __init__(self, reg):
        """
        :param RegisterDefinition reg: the register which value is read
        """
        self._reg = reg

    @property
    def register(self):
        """ The register manipulated by the command. """
        return self._reg


class SetParam(RegisterCommandMixin, ParametricCommand):
    """ The SetParam command. """

    def __init__(self, reg, value):
        """
        :param RegisterDefinition reg: the register which value is modified
        :param int value: the new value
        """
        RegisterCommandMixin.__init__(self, reg)
        self._value = value

    @property
    def value(self):
        """ The register new value """
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def as_request(self):
        return [OpCodes.SET_PARAM | self._reg.addr] + Register.value_as_bytes(self._reg, self._value)


class GetParam(RegisterCommandMixin, ParametricCommand):
    """ The GetParam command. """
    def as_request(self):
        return [OpCodes.GET_PARAM | self._reg.addr] + Register.value_as_bytes(self._reg, 0)


class DirectionCommandMixin(object):
    """ A mixin factoring common process for commands dealing with move directions. """

    #: default value for the direction, when not specified
    DEFAULT_DIRECTION = defs.Direction.FWD

    _dir = DEFAULT_DIRECTION

    def __init__(self, direction=DEFAULT_DIRECTION):
        """
        :param int direction: the direction of the move
        """
        self.direction = direction

    @property
    def direction(self):
        """ The direction of the move.

        Setting a value not in those defined by :py:class:`Direction` class
        raises a ValueError exception.
        """
        return self._dir

    @direction.setter
    def direction(self, value):
        if value not in (defs.Direction.FWD, defs.Direction.REV):
            raise ValueError('invalid direction (%s)' % value)

        self._dir = value


class SpeedCommandMixin(object):
    """ A mixin factoring common process for commands dealing with move speeds. """

    #: maximum allowed value (equals to MAX_SPEED as defined in the dSPIN datasheet)
    MAX_VALUE = 0x3fffff

    _speed = MAX_VALUE

    def __init__(self, steps_per_sec=MAX_VALUE):
        """
        :param int steps_per_sec: the speed, given in steps per sec, taking micro-stepping in consideration
        """
        self.speed = steps_per_sec

    @property
    def speed(self):
        """ The speed value in steps per sec """
        return self._speed

    @speed.setter
    def speed(self, value):
        if not 0 < value <= self.MAX_VALUE:
            raise ValueError('out of bounds speed')

        self._speed = value


class Run(ParametricCommand, DirectionCommandMixin, SpeedCommandMixin):
    """ The Run command. """

    def __init__(self, direction=DirectionCommandMixin.DEFAULT_DIRECTION, steps_per_sec=SpeedCommandMixin.MAX_VALUE):
        """
        :param int direction: the move direction (default: DirectionCommandMixin.DEFAULT_DIRECTION)
        :param int steps_per_sec: the move speed (default: MAX_SPEED)
        """
        DirectionCommandMixin.__init__(self, direction)
        SpeedCommandMixin.__init__(self, steps_per_sec)

    def as_request(self):
        return [OpCodes.RUN | self._dir] + Register.value_as_bytes(Register.SPEED, defs.spd_calc(self.speed))


class StepClock(ParametricCommand, DirectionCommandMixin):
    """ The StepClock command. """

    def __init__(self, direction=DirectionCommandMixin.DEFAULT_DIRECTION):
        """
        :param int direction: the move direction (default: forward)
        """
        DirectionCommandMixin.__init__(self, direction)

    def as_request(self):
        return [OpCodes.RUN | self.direction]


class Move(ParametricCommand, DirectionCommandMixin):
    """ The Move command. """

    def __init__(self, direction=defs.Direction.FWD, steps=1):
        """
        :param int direction: the move direction (default: DirectionCommandMixin.DEFAULT_DIRECTION)
        :param int steps: the number of steps to move (default: 1)
        """
        DirectionCommandMixin.__init__(self, direction)
        self._steps = abs(steps)

    @property
    def steps(self):
        """ The number of steps """
        return self._steps

    @steps.setter
    def steps(self, value):
        self._steps = value

    def as_request(self):
        return [OpCodes.MOVE | self.direction] + Register.value_as_bytes(Register.ABS_POS, self._steps)


class PositionCommandMixin(object):
    """ A mixin factoring common process for commands dealing with positions. """

    def __init__(self, position):
        """
        :param int position: the absolute position
        """
        self._pos = position

    @property
    def position(self):
        """ The position in steps, taking taking micro-stepping in consideration """
        return self._pos

    @position.setter
    def position(self, value):
        self._pos = value


class GoTo(ParametricCommand, PositionCommandMixin):
    """ The GoTo command. """

    def __init__(self, position):
        """
        :param int position: the absolute position
        """
        PositionCommandMixin.__init__(self, position)

    def as_request(self):
        return [OpCodes.GOTO] + Register.value_as_bytes(Register.ABS_POS, self.position)


class GoToDir(ParametricCommand, DirectionCommandMixin, PositionCommandMixin):
    """ The GoToDir command. """

    def __init__(self, direction, position):
        """
        :param int direction: the move direction
        :param int position: the absolute position
        """
        DirectionCommandMixin.__init__(self, direction)
        PositionCommandMixin.__init__(self, position)

    def as_request(self):
        return [OpCodes.GOTO_DIR | self.direction] + Register.value_as_bytes(Register.ABS_POS, self.position)


class ActionCommandMixin(object):
    """ A mixin factoring common process for commands dealing with switch edge detection actions. """

    #: default action, when not specified
    DEFAULT_ACTION = defs.GoUntilAction.COPY

    _action = DEFAULT_ACTION

    def __init__(self, action=DEFAULT_ACTION):
        """
        :param int action: the action to be performed when edge occurs (default: COPY)
        """
        self.action = action

    @property
    def action(self):
        """ The action.

        Setting a value not in those defined by :py:class:`GoUntilAction` class
        raises a ValueError exception.
        """
        return self._action

    @action.setter
    def action(self, value):
        if value not in (defs.GoUntilAction.COPY, defs.GoUntilAction.RESET):
            raise ValueError('invalid action')
        self._action = value


class GoUntil(ParametricCommand, ActionCommandMixin, DirectionCommandMixin, SpeedCommandMixin):
    """ The GoUntil command. """

    def __init__(self,
                 action=ActionCommandMixin.DEFAULT_ACTION,
                 direction=DirectionCommandMixin.DEFAULT_DIRECTION,
                 steps_per_sec=SpeedCommandMixin.MAX_VALUE
                 ):
        """
        :param int action: the action to be performed when edge occurs (default: COPY)
        :param int direction: the move direction (default: forward)
        :param int steps_per_sec: the move speed (default: MAX_SPEED)
        """
        ActionCommandMixin.__init__(self, action)
        DirectionCommandMixin.__init__(self, direction)
        SpeedCommandMixin.__init__(self, steps_per_sec)

    def as_request(self):
        return [OpCodes.GO_UNTIL | self.direction | self.action] + \
               Register.value_as_bytes(Register.SPEED, defs.spd_calc(self.speed))


class ReleaseSW(ParametricCommand, ActionCommandMixin, DirectionCommandMixin):
    """ The ReleaseSW command. """

    def __init__(self, action=ActionCommandMixin.DEFAULT_ACTION, direction=DirectionCommandMixin.DEFAULT_DIRECTION):
        """
        :param int action: the action to be performed when edge occurs (default: COPY)
        :param int direction: the move direction (default: forward)
        """
        ActionCommandMixin.__init__(self, action)
        DirectionCommandMixin.__init__(self, direction)

    def as_request(self):
        return [OpCodes.RELEASE_SW | self.direction | self.action]
