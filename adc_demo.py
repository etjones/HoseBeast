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

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

def main():
    ads = ADS.ADS1115(i2c)    
    # chan = AnalogIn(ads, ADS.P0)
    # Measure the voltage difference between pins 0 & 1
    chan = AnalogIn(ads, ADS.P0, ADS.P1)
    ads.gain = 2
    try:
        while True:
            # print(chan.value, chan.voltage)
            print(f'\rValue: {chan.value:06d},  Voltage: {chan.voltage:.3f}V', end="", flush=True)    
            time.sleep(0.3)
    except KeyboardInterrupt:
        print()
        pass    

if __name__ == '__main__':
    main()

 