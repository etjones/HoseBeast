#! /usr/bin/env python3
import board
import busio
import time

# I had to manually enable I2C, a communication bus,
# on this RasPi 3B+. The commands were:
# sudo raspi-config
# (menus: Interfacing Options -> I2C -> Enable -> Finish)
# reboot Pi
i2c = busio.I2C(board.SCL, board.SDA)

import adafruit_ads1x15.ads1115 as ADS  # noqa: E402
from adafruit_ads1x15.analog_in import AnalogIn  # noqa: E402

# This code taken from the Adafruit ADS1x15 tutorial at:
# https://learn.adafruit.com/adafruit-4-channel-adc-breakouts/python-circuitpython
#
# Note that the pressure readings were taken with a Walfront G1/4 Pressure Transducer
# feeding the ADS1115 analog -> digital converter.
# Transducer page: https://www.amazon.com/dp/B07KJHRPLG/


def main():
    ads = ADS.ADS1115(i2c)

    measure_voltage_difference = False
    if measure_voltage_difference:
        # Measure the voltage difference between pins 0 & 1
        chan = AnalogIn(ads, ADS.P0, ADS.P1)
    else:
        # Alternately, we could measure absolute voltage on pin 0.
        # This is sensitive to low voltages; it crashed on me below ~1.5V
        chan = AnalogIn(ads, ADS.P0)

    # Gain changes sensitivity. Valid values are [2/3, 1, 2, 4, 8, 16]
    # - ETJ 13 August 2024

    # ads.gain = 2/3
    ads.gain = 4

    try:
        while True:
            # \r carriage return, plus no newline means we overwrite the
            # same line each time
            print(
                f"\rValue: {chan.value:06d},  Voltage: {chan.voltage:.3f}V    ",
                end="",
                flush=True,
            )
            time.sleep(0.3)
    except KeyboardInterrupt:
        print()
        pass


if __name__ == "__main__":
    main()
