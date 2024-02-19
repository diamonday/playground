from pulse_generator.pulse_generator import PulseGenerator as PulseGeneratorBase


class PulseGeneratorClass(PulseGeneratorBase):

    def Continuous(self, channels):
        self.setContinuous(channels)

    def Sequence(self, sequence, loop=None):
        self.setSequence(sequence, loop=True)
        # self.setSequence(sequence, loop=False)

    def Night(self):
        self.setContinuous(0x0000)

    def Light(self):
        self.setContinuous(0x0001)

    def Open(self):
        self.setContinuous(0x000F)


# @singleton
def PulseGenerator(
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
    return PulseGeneratorClass(serial=serial, channel_map=channel_map)
