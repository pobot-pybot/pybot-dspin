# -*- coding: utf-8 -*-

from .core import DSPIN, bytes_as_string, values_as_string
from .defs import Register, Status
from . import commands, log

__author__ = 'Eric Pascual'


class DaisyChain(DSPIN):
    def __init__(self, chain_length, spi, standby_pin, busyn_pin):
        if chain_length <= 1:
            raise ValueError('chain length must be > 1')

        super(DaisyChain, self).__init__(spi, standby_pin, busyn_pin)

        self._chain_length = chain_length

    def __len__(self):
        return self._chain_length

    def read_register(self, reg):
        self.log.debug('DaisyChain.read_register(%s)...', reg.name)

        replies = self._xfer([commands.GetParam(reg).as_request()] * self._chain_length)

        values = [
            self.parse_register_reply(reg, r[1:])
            for r in replies
        ]
        if self.log.isEnabledFor(log.DEBUG):
            self.log.debug(' -> [%s]', bytes_as_string(values))
        return values

    def write_register(self, reg, data):
        try:
            if len(data) != self._chain_length:
                raise ValueError('data length mismatch')
        except TypeError:
            # data parameter is a scalar, so we execute a broadcast
            self.log.debug('write_register(%s, 0x%x)', reg.name, data)
            requests = [commands.SetParam(reg, data).as_request()] * self._chain_length

        else:
            if self.log.isEnabledFor(log.DEBUG):
                self.log.debug('write_register(%s, [%s])', reg.name, values_as_string(data))
            requests = [
                commands.SetParam(reg, value).as_request() if value is not None else None
                for value in data
            ]

        self._xfer(requests)

    def _xfer(self, requests):
        if len(requests) != self._chain_length:
            raise ValueError(
                'requests list length (%d) does not match chain one (%d)' % (len(requests), self._chain_length)
            )

        # find the longest request for padding them to the same size
        max_len = max((len(r) for r in requests if r))

        # remember which dSPIN has requests for them
        dist_list = [i for i, r in enumerate(requests) if r]

        # build the complete data stream, by padding the requests to the highest
        # size and adding dummy ones (all NOP) for devices not involved
        padding = [0] * max_len
        for i, r in enumerate(requests):
            if r:
                r.extend(padding[len(r):])
            else:
                requests[i] = padding

        # time to send them now, and "dispatch" the replies
        replies = zip(*[self._spi.xfer2(r) for r in zip(*requests)])

        # remove replies to dummy requests
        return [r if i in dist_list else None for i, r in enumerate(replies)]

    def check_initial_config(self):
        return all((v == Register.CONFIG.reset_value for v in self.CONFIG))

    def broadcast_request(self, request):
        requests = [request] * self._chain_length
        return zip(*[self._spi.xfer2(p) for p in zip(*requests)])

    def send_command(self, command, dist_list=None):
        """ Sends *the same command* with *same parameters* if any to a list of dSPINs.

        :param commands.Command command:
        :param list dist_list: the distribution list
        """
        command_request = command.as_request()
        if dist_list:
            nop = commands.Nop(len(command_request)).as_request()
            requests = [command_request if d in dist_list else nop for d in xrange(self._chain_length)]
            for p in zip(*requests):
                self._spi.xfer2(p)
        else:
            self.broadcast_request(command_request)

    def send_requests(self, requests, wait=True, wait_cb=None):
        """ Send individual requests to dSPINs.

        The `commands` parameter is a list of `chain_length` commands, `None` being
        used for devices not involved in the transaction.

        :param list requests: the requests for the dSPINs
        :param bool wait: True for waiting for *all* commands to be complete
        :param function wait_cb: option callback being called in the wait loop
        :return: the command results
        :rtype: list
        """
        result = self._xfer(requests)
        if wait:
            self.wait_for_move_complete(wait_cb)
        return result

    def expand_parameters(self, p_dict):
        """ Given a set of method parameters provided as a dictionary of tuples or lists,
        indexed by the motor 0 based position in the chain, returns the list of parameter vectors
        ready to be passed to one of the chain command methods.

        The number of returned vectors is equal to the size of the parameter tuples provided
        in the dictionary. The "slots" for motors not included in the parameters dictionary
        will by set to `None`.

        Example::

            Let's say that a subclass of DaisyChain implements a serial arm with a motorized
            gripper. Making the gripper close until its end switch it reached can be done with
            the following calls, supposing `MOTOR_GRIPPER` is the index of the gripper motor in
            the daisy-chain and `GRIPPER_CLOSE_SPEED` defines its rotation speed for closing.

            parms = chain.expand_parms({
                self.MOTOR_GRIPPER: (defs.GoUntilAction.COPY, defs.Direction.FWD, self.GRIPPER_CLOSE_SPEED)
            })
            chain.go_until(*parms)

        :param dict p_dict: a dictionary of tuples containing the method parameter values
        for each of the involved motors
        :return: a tuple of the n parameter vectors
        :rtype: tuple
        :raise: ValueError if the parameter tuples contained in the passed dictionary do not have the same size
        """
        self.log.debug("expand_parameters(%s)", p_dict)
        # take the size of the first parameters tuple as the reference one
        try:
            p_count = len(p_dict.values()[0])
        except TypeError:
            # accept scalars in place of single item tuples
            p_count = 1
        # initialize a all None expanded parameter list
        p_list = [[None] * p_count] * len(self)

        for m_num, p in p_dict.iteritems():
            try:
                lg = len(p)
            except TypeError:
                lg = 1
                p = (p,)
            if lg != p_count:
                raise ValueError('invalid parameters list (%s)', p_dict)
            p_list[m_num] = p
        return zip(*p_list)

    @property
    def switch_is_closed(self):
        """ Returns the closed state of the switches.
        """
        return [bool(s & Status.SW_F) for s in self.STATUS]

    def run(self, directions, speeds):
        self.log.debug('run(%s, %s)...', directions, speeds)
        requests = [
            commands.Run(d, s).as_request() if d is not None and s is not None else commands.NOP_4_REQUEST
            for d, s in zip(directions, speeds)
        ]
        self._xfer(requests)

    def step_clock(self, directions):
        requests = [
            commands.StepClock(d).as_request() if d is not None else commands.NOP_1_REQUEST
            for d in directions
        ]
        self._xfer(requests)

    def move(self, directions, steps_s, wait=True, wait_cb=None):
        self.log.debug('move(%s, %s, %s, %s)...', directions, steps_s, wait, wait_cb)
        requests = [
            commands.Move(d, s).as_request() if (d is not None and s is not None) else commands.NOP_4_REQUEST
            for d, s in zip(directions, steps_s)
        ]
        self._xfer(requests)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def goto(self, positions, wait=True, wait_cb=None):
        self.log.debug('goto(%s, %s, %s)...', positions, wait, wait_cb)
        requests = [
            commands.GoTo(p).as_request() if p is not None else commands.NOP_4_REQUEST
            for p in positions
        ]
        self._xfer(requests)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def goto_dir(self, directions, positions, wait=True, wait_cb=None):
        self.log.debug('goto_dir(%s, %s, %s, %s)...', directions, positions, wait, wait_cb)
        requests = [
            commands.GoToDir(d, p).as_request() if d is not None and p is not None else commands.NOP_4_REQUEST
            for d, p in zip(directions, positions)
        ]
        self._xfer(requests)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def go_home(self, dist_list=None, wait=True, wait_cb=None):
        self.log.debug('go_home(%s, %s, %s)...', dist_list, wait, wait_cb)
        self.send_command(commands.GO_HOME, dist_list=dist_list)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def go_mark(self, dist_list=None, wait=True, wait_cb=None):
        self.log.debug('go_mark(%s, %s, %s)...', dist_list, wait, wait_cb)
        self.send_command(commands.GO_MARK, dist_list=dist_list)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def go_until(self, actions, directions, speeds, wait=True, wait_cb=None):
        self.log.debug('go_until(%s, %s, %s, %s, %s)...', actions, directions, speeds, wait, wait_cb)
        requests = [
            commands.GoUntil(a, d, s).as_request()
            if a is not None and d is not None and s is not None else commands.NOP_4_REQUEST
            for a, d, s in zip(actions, directions, speeds)
        ]
        self._xfer(requests)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def release_sw(self, actions, directions, wait=True, wait_cb=None):
        self.log.debug('release_sw(%s, %s, %s, %s)...', actions, directions, wait, wait_cb)
        requests = [
            commands.ReleaseSW(a, d) if a is not None and d is not None else commands.NOP_4_REQUEST
            for a, d in zip(actions, directions)
        ]
        self._xfer(requests)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def clear_status(self, dist_list=None):
        self.log.debug('clear_status(%s)...', dist_list)
        self.send_command(commands.GET_STATUS, dist_list=dist_list)

    def reset_pos(self, dist_list=None):
        self.log.debug('reset_pos(%s)...', dist_list)
        self.send_command(commands.RESET_POS, dist_list=dist_list)

    def reset_device(self, dist_list=None):
        self.log.debug('reset_device(%s)...', dist_list)
        self.send_command(commands.RESET_DEVICE, dist_list=dist_list)

    def soft_stop(self, dist_list=None, wait=True, wait_cb=None):
        self.log.debug('soft_stop(%s, %s, %s)...', dist_list, wait, wait_cb)
        self.send_command(commands.SOFT_STOP, dist_list=dist_list)
        if wait:
            self.wait_for_move_complete(wait_cb)

    def hard_stop(self, dist_list=None):
        self.log.debug('hard_stop(%s)...', dist_list)
        self.send_command(commands.HARD_STOP, dist_list=dist_list)

    def hard_hi_Z(self, dist_list=None):
        self.log.debug('hard_hi_Z(%s)...', dist_list)
        self.send_command(commands.HARD_HIZ, dist_list=dist_list)

    def soft_hi_Z(self, dist_list=None, wait=True, wait_cb=None):
        self.log.debug('soft_hi_Z(%s, %s, %s)...', dist_list, wait, wait_cb)
        self.send_command(commands.SOFT_HIZ, dist_list=dist_list)
        if wait:
            self.wait_for_move_complete(wait_cb)
