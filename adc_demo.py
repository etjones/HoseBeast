#! /usr/bin/env python3
import board
import busio
i2c = busio.I2C(board.SCL, board.SDA)

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

def main():
    ads = ADS.ADS1115(i2c)    
    chan = AnalogIn(ads, ADS.P0)    
    print(chan.value, chan.voltage)    

if __name__ == '__main__':
    main()

