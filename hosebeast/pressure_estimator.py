#! /usr/bin/env python3

import time
from datetime import datetime
from math import sin, pi
from typing import TypeAlias

# I had to manually enable I2C, a communication bus,
# on this RasPi 3B+. The commands were:
# sudo raspi-config
# (menus: Interfacing Options -> I2C -> Enable -> Finish)
# reboot Pi
MOCK = False
try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS  # noqa: E402
    from adafruit_ads1x15.analog_in import AnalogIn  # noqa: E402

    # SomeADCWrapper: TypeAlias = "ADCWrapper"
except (ImportError, NotImplementedError):
    print("Couldn't import I2C; using mock ADC data")
    MOCK = True
SomeADCWrapper: TypeAlias = "MockADCWrapper | ADCWrapper"

# This code taken from the Adafruit ADS1x15 tutorial at:
# https://learn.adafruit.com/adafruit-4-channel-adc-breakouts/python-circuitpython
#
# Note that the pressure readings were taken with a Walfront G1/4 Pressure Transducer
# feeding the ADS1115 analog -> digital converter.
# Transducer page: https://www.amazon.com/dp/B07KJHRPLG/

VALID_GAINS = [2 / 3, 1.0, 2.0, 4.0, 8.0, 16.0]


def get_adc_channel(
    pin_0: int, pin_1: int | None = None, gain: float = 1.0
) -> SomeADCWrapper:
    """
    Return an ADCWrapper object for the given pins and gain.
    If there's a live I2C connection, use that. Otherwise, use a mock ADC.
    """
    if MOCK:
        chan = MockADCWrapper(pin_0, pin_1, gain)
    else:
        chan = ADCWrapper(pin_0, pin_1, gain)
    return chan


class MockADCWrapper:
    period_minutes = 20

    def __init__(self, pin_0: int, pin_1: int | None = None, gain: float = 1.0):
        self._gain = gain or VALID_GAINS[0]

    @property
    def gain(self) -> float:
        return self._gain

    @gain.setter
    def gain(self, gain: float):
        if float(gain) not in VALID_GAINS:
            raise ValueError(f"Gain must be one of {VALID_GAINS}")
        self._gain = gain

    @property
    def value(self) -> int:
        # We want to return a value between 0 and 32767 (15 bits)
        # that varies enough to show that it's working, but not so much
        # that it's annoying. Let's use a sine wave between 16k & 32k
        # every self.period_minutes.

        now = datetime.now()
        seconds = now.hour * 3600 + now.minute * 60 + now.second
        return sine_wave(seconds, self.period_minutes * 60)

    @property
    def voltage(self) -> float:
        return self.value / 32767 * self.gain


class ADCWrapper:
    """Wrapper around the ADS1115 analog to digital converter."""

    def __init__(self, pin_0: int, pin_1: int | None = None, gain: float = 1.0):
        self.pin_0 = pin_0
        self.pin_1 = pin_1
        self.ads = ADS.ADS1115(busio.I2C(board.SCL, board.SDA))
        self.ads.gain = gain

        if pin_1 is not None:
            self.chan = AnalogIn(self.ads, pin_0, pin_1)
        else:
            self.chan = AnalogIn(self.ads, pin_0)

    @property
    def value(self) -> int:
        return self.chan.value

    @property
    def voltage(self) -> float:
        return self.chan.voltage

    @property
    def gain(self) -> float:
        return self.ads.gain

    @gain.setter
    def gain(self, gain: float):
        if float(gain) not in VALID_GAINS:
            raise ValueError(f"Gain must be one of {VALID_GAINS}")
        self.ads.gain = gain


def sine_wave(seconds: int, period_seconds: int) -> int:
    v = seconds % period_seconds / period_seconds
    value = 16383 + int(8192 * (1 + sin(v * 2 * pi)))
    return value


def main():
    # chan = get_adc_channel(ADS.P0, ADS.P1)
    chan = get_adc_channel(0, 1)
    # # I had to manually enable I2C, a communication bus,
    # # on RasPis. The commands were:
    # # sudo raspi-config
    # # (menus: Interfacing Options -> I2C -> Enable -> Finish)
    # # reboot Pi
    # i2c = busio.I2C(board.SCL, board.SDA)
    # ads = ADS.ADS1115(i2c)

    # measure_voltage_difference = False
    # if measure_voltage_difference:
    #     # Measure the voltage difference between pins 0 & 1
    #     chan = AnalogIn(ads, ADS.P0, ADS.P1)
    # else:
    #     # Alternately, we could measure absolute voltage on pin 0.
    #     # This is sensitive to low voltages; it crashed on me below ~1.5V
    #     chan = AnalogIn(ads, ADS.P0)

    # Gain changes sensitivity. Valid values are [2/3, 1, 2, 4, 8, 16]
    # - ETJ 13 August 2024

    # ads.gain = 2/3
    chan.gain = 4

    try:
        while True:
            # \r carriage return, plus no newline means we overwrite the
            # same line each time
            print(
                f"\rValue: {chan.value:-6d},  Voltage: {chan.voltage:.3f}V",
                end="",
                flush=True,
            )
            time.sleep(0.3)
    except KeyboardInterrupt:
        print()
        pass


if __name__ == "__main__":
    main()
