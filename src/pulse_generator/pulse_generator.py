import os
import struct
import time

import numpy as np

from ok import ok

BITFILE_12X8 = os.path.join(
    os.path.dirname(__file__), "PulseGenerator12x8.bit"
)  # the FPGA bitfile is assumed to be located in the same directory as the present file

BITFILE_24X4 = os.path.join(
    os.path.dirname(__file__), "PulseGenerator24x4.bit"
)  # the FPGA bitfile is assumed to be located in the same directory as the present file


class PulseGenerator:
    """
    Represents an FPGA based Pulse Generator.
    """

    command_map = {
        "RUN": 0,
        "LOAD": 1,
        "RESET_READ": 2,
        "RESET_SDRAM": 3,
        "RESET_WRITE": 4,
        "RETURN": 5,
    }
    state_map = {
        0: "IDLE",
        1: "RESET_READ",
        2: "RESET_SDRAM",
        3: "RESET_WRITE",
        4: "LOAD_0",
        5: "LOAD_1",
        6: "LOAD_2",
        7: "READ_0",
        8: "READ_1",
        9: "READ_2",
    }

    def __init__(
        self,
        serial="",
        channel_map={
            "ch0": 0,
            "ch1": 1,
            "ch2": 2,
            "ch3": 3,
            "ch4": 4,
            "ch5": 5,
            "ch6": 6,
            "ch7": 7,
            "ch8": 8,
            "ch9": 9,
            "ch10": 10,
            "ch11": 11,
            "ch12": 12,
            "ch13": 13,
            "ch14": 14,
            "ch15": 15,
            "ch16": 16,
            "ch17": 17,
            "ch18": 18,
            "ch19": 19,
            "ch20": 20,
            "ch21": 21,
            "ch22": 22,
            "ch23": 23,
        },
        core="12x8",
    ):
        self.serial = serial
        self.channel_map = channel_map
        self.xem = ok.FrontPanel()
        self.open_usb()
        self.load_core(core)
        self.setResetValue(0x00000000)
        self.reset()
        self.checkUnderflow()

    def open_usb(self):
        if self.xem.OpenBySerial(self.serial) != 0:
            raise RuntimeError("failed to open USB connection.")

    def set_frequency(self, vco):
        PLL = ok.PLL22150()
        self.xem.GetPLL22150Configuration(PLL)
        PLL.SetVCOParameters(vco, 48)
        PLL.SetOutputSource(0, 5)
        PLL.SetOutputEnable(0, 1)
        self.xem.SetPLL22150Configuration(PLL)
        self.PLL = PLL

    def flash_fpga(self, bitfile):
        ret = self.xem.ConfigureFPGA(str(bitfile))
        if ret != 0:
            raise RuntimeError("failed to upload bit file to fpga. Error code %i" % ret)

    def load_core(self, core):
        assert core in ["12x8", "24x4"]
        self.core = core
        if core == "12x8":
            self.n_channels = 12
            self.channel_width = 8
            self.dt = 1.5
            self.set_frequency(333)
            self.flash_fpga(BITFILE_12X8)
            if self.getInfo() != (12, 8):
                raise RuntimeError("FPGA core does not match.")
        elif core == "24x4":
            self.n_channels = 24
            self.channel_width = 4
            self.dt = 2.0
            self.set_frequency(250)
            self.flash_fpga(BITFILE_24X4)
            if self.getInfo() != (24, 4):
                raise RuntimeError("FPGA core does not match.")
        else:
            raise ValueError('core must be "12x8" or "24x4"')

    def getInfo(self):
        """Returns the number of channels and channel width."""
        self.xem.UpdateWireOuts()
        ret = self.xem.GetWireOutValue(0x20)
        return ret & 0xFF, ret >> 8

    def ctrlPulser(self, command):
        self.xem.ActivateTriggerIn(0x40, self.command_map[command])

    def getState(self):
        """
        Return the state of the FPGA core.

        The state is returned as a string out of the following list.

        'IDLE'
        'RESET_READ'
        'RESET_SDRAM'
        'RESET_WRITE'
        'LOAD_0'
        'LOAD_1'
        'LOAD_2'
        'READ_0'
        'READ_1'
        'READ_2'
        """
        self.xem.UpdateWireOuts()
        return self.state_map[self.xem.GetWireOutValue(0x21)]

    def checkState(self, wanted):
        """Raises a 'RuntimeError' if the FPGA state is not the 'wanted' state."""
        actual = self.getState()
        if actual != wanted:
            raise RuntimeError(
                "FPGA State Error. Expected '"
                + wanted
                + "' state but got '"
                + actual
                + "' state."
            )

    def enableTrigger(self):
        self.xem.SetWireInValue(0x00, 0xFF, 2)
        self.xem.UpdateWireIns()

    def disableTrigger(self):
        self.xem.SetWireInValue(0x00, 0x00, 2)
        self.xem.UpdateWireIns()

    def enableDecoder(self):
        self.xem.SetWireInValue(0x00, 0x00, 1)
        self.xem.UpdateWireIns()

    def disableDecoder(self):
        self.xem.SetWireInValue(0x00, 0xFF, 1)
        self.xem.UpdateWireIns()

    def run(self, triggered=False):
        self.halt()
        if triggered:
            self.enableTrigger()
        else:
            self.disableTrigger()
        self.ctrlPulser("RESET_READ")
        time.sleep(0.01)
        self.ctrlPulser("RUN")
        time.sleep(0.01)
        self.enableDecoder()

    def halt(self):
        self.disableDecoder()
        time.sleep(0.01)
        self.ctrlPulser("RETURN")
        self.checkState("IDLE")

    def loadPages(self, buf):
        if len(buf) % 1024 != 0:
            raise RuntimeError(
                "Only full SDRAM pages supported. Pad your buffer with zeros such that its length is a multiple of 1024."
            )
        self.disableDecoder()
        self.ctrlPulser("RESET_WRITE")
        time.sleep(0.01)
        self.ctrlPulser("LOAD")
        self.checkState("LOAD_0")
        bytes = self.xem.WriteToBlockPipeIn(0x80, 1024, buf)
        time.sleep(0.01)
        self.checkState("LOAD_0")
        self.ctrlPulser("RETURN")
        self.checkState("IDLE")
        return bytes

    def reset(self):
        self.disableDecoder()
        self.ctrlPulser("RESET_WRITE")
        time.sleep(0.001)
        self.ctrlPulser("RESET_READ")
        time.sleep(0.001)
        self.ctrlPulser("RESET_SDRAM")
        time.sleep(0.01)

    def setResetValue(self, bits):
        self.xem.SetWireInValue(0x01, bits, 0xFFFF)
        if self.core == "24x4":
            self.xem.SetWireInValue(0x02, bits >> 16, 0xFFFF)
        self.xem.UpdateWireIns()

    def checkUnderflow(self):
        self.xem.UpdateTriggerOuts()
        return self.xem.IsTriggered(0x60, 1)

    def createBitsFromChannels(self, channels):
        """
        Convert a list of channel names into an array of bools of length N_CHANNELS,
        that specify the state (high or low) of each available channel.
        """
        bits = np.zeros(self.n_channels, dtype=bool)
        for channel in channels:
            bits[self.channel_map[channel]] = True
        return bits

    def setBits(self, integers, start, count, bits):
        """Sets the bits in the range start:start+count in integers[i] to bits[i]."""
        # ToDo: check bit order (depending on whether least significant or most significant bit is shifted out first from serializer)
        for i in range(self.n_channels):
            if bits[i]:
                integers[i] = integers[i] | (2**count - 1) << start

    def pack(self, mult, pattern):
        # ToDo: check whether max repetitions is exceeded, split into several commands if necessary
        if self.core == "24x4":
            pattern = [
                pattern[i] | pattern[i + 1] << 4 for i in range(0, len(pattern), 2)
            ]
        s = struct.pack(">I%iB" % len(pattern), mult, *pattern[::-1])
        swap = ""
        for i in range(len(s)):
            swap += s[i - 1 if i % 2 else i + 1]
        return swap

    def convertSequenceToBinary(self, sequence, loop=True):
        """
        Converts a pulse sequence (list of tuples (channels,time) )
        into a series of pulser instructions (128 bit words),
        and returns these in a binary buffer of length N*1024
        representing N SDRAM pages.

        A pulser instruction has the form

        command (1 bit) | repetition (31 bit) | ch0 pattern (8bit/4bit), ..., chN pattern (8bit/4bit)'

        The pulse sequence is split into a suitable series of
        such low level pulse commands taking into account the
        minimal 8 bit pattern length.

        input:

            sequence    list of tuples of the form (channels, time), where channels is
                        a list of strings corresponding to channel names and time is a float
                        specifying the time in ns.

            loop        if True, repeat the sequence indefinitely, if False, run the sequence once

        returns:

            buf         binary buffer containing N SDRAM pages that represent the sequence
        """

        dt = self.dt
        N_CHANNELS, CHANNEL_WIDTH = self.n_channels, self.channel_width
        ONES = 2**CHANNEL_WIDTH - 1
        REP_MAX = 2**31
        buf = ""
        # we start with an integer zero for each channel.
        # In the following, we will start filling up the bits in each of these integers
        blank = np.zeros(
            N_CHANNELS, dtype=int
        )  # we will need this many times, so we create it once and copy from this
        pattern = blank.copy()
        index = 0
        for channels, time in sequence:
            ticks = int(
                round(time / dt)
            )  # convert the time into an integer multiple of hardware time steps
            if ticks == 0:
                continue
            bits = self.createBitsFromChannels(channels)
            if (
                index + ticks < CHANNEL_WIDTH
            ):  # if pattern does not fill current block, insert into current block and continue
                self.setBits(pattern, index, ticks, bits)
                index += ticks
                continue
            if (
                index > 0
            ):  # else fill current block with pattern, reduce ticks accordingly, write block and start a new block
                self.setBits(pattern, index, CHANNEL_WIDTH - index, bits)
                buf += self.pack(0, pattern)
                ticks -= CHANNEL_WIDTH - index
                pattern = blank.copy()
            # split possible remaining ticks into a command with repetitions and a single block for the remainder
            repetitions = ticks / CHANNEL_WIDTH  # number of full blocks
            index = (
                ticks % CHANNEL_WIDTH
            )  # remainder will make the beginning of a new block
            if repetitions > 0:
                if repetitions > REP_MAX:
                    multiplier = repetitions / REP_MAX
                    repetitions = repetitions % REP_MAX
                    buf += multiplier * self.pack(REP_MAX - 1, ONES * bits)
                buf += self.pack(
                    repetitions - 1, ONES * bits
                )  # rep=0 means the block is executed once
            if index > 0:
                pattern = blank.copy()
                self.setBits(pattern, 0, index, bits)
        if loop:  # repeat the hole sequence
            if index > 0:  # fill up incomplete block with zeros and write it
                self.setBits(
                    pattern,
                    index,
                    CHANNEL_WIDTH - index,
                    np.zeros(N_CHANNELS, dtype=bool),
                )
                buf += self.pack(0, pattern)
        else:  # stop after one execution
            if index > 0:  # fill up the incomplete block with the bits of the last step
                self.setBits(pattern, index, CHANNEL_WIDTH - index, bits)
                buf += self.pack(0, pattern)
            buf += self.pack(1 << 31, ONES * bits)
            buf += self.pack(1 << 31, ONES * bits)
        # print "buf has",len(buf)," bytes"
        buf = (
            buf + ((1024 - len(buf)) % 1024) * "\x00"
        )  # pad buffer with zeros so it matches SDRAM / FIFO page size
        # print "buf has",len(buf)," bytes"
        return buf

    def setSequence(self, sequence, loop=True, triggered=False):
        """
        Output a pulse sequence.

        Input:
            sequence      List of tuples (channels, time) specifying the pulse sequence.
                          'channels' is a list of strings specifying the channels that
                          should be high and 'time' is a float specifying the time in ns.

        Optional arguments:
            loop          bool, defaults to True, specifying whether the sequence should be
                          excecuted once or repeated indefinitely.
            triggered     bool, defaults to False, specifies whether the execution
                          should be delayed until an external trigger is received
        """
        self.halt()
        self.loadPages(self.convertSequenceToBinary(sequence, loop))
        self.run(triggered)

    def setContinuous(self, channels):
        """
        Set the outputs continuously high or low.

        Input:
            channels    can be an integer or a list of channel names (strings).
                        If 'channels' is an integer, each bit corresponds to a channel.
                        A channel is set to low/high when the bit is 0/1, respectively.
                        If 'channels' is a list of strings, the specified channels
                        are set high, while all others are set low.
        """
        try:
            iter(channels)
        except:
            self.setResetValue(channels)
        else:
            bits = 0
            for channel in channels:
                bits = bits | (1 << self.channel_map[channel])
            self.setResetValue(bits)
        self.halt()


########## TESTCODE############

if __name__ == "__main__":

    pg = PulseGenerator(core="12x8")

    all = ["ch" + str(i) for i in range(1, 12)]
    sequence = [(["ch0"], 6.0)] + 100 * [(["ch1"], 6.0), ([], 1000.0)]
    pg.setSequence(sequence)

    def test():
        while True:
            pg.setContinuous(0)
            if pg.checkUnderflow():
                print("continuous")
                break
            pg.setSequence(sequence)
            if pg.checkUnderflow():
                print(sequence)
