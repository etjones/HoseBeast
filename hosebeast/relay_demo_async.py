#! /usr/bin/env python3

import asyncio
import time

try:
    import RPi.GPIO as GPIO
except Exception:
    print("Error importing RPi.GPIO. Using Mock.GPIO instead")
    import Mock.GPIO as GPIO

"""
Demo Pinout & wiring:

RasPi 3B:
   3V3  (1) (2)  5V    
 GPIO2  (3) (4)  5V       <----  (To VCC on Relay)
 GPIO3  (5) (6)  GND      <----  (To GND on Relay)
 GPIO4  (7) (8)  GPIO14
   GND  (9) (10) GPIO15
GPIO17 (11) (12) GPIO18   <----  (To IN1 on Relay)
GPIO27 (13) (14) GND   
GPIO22 (15) (16) GPIO23   <----  (To IN2 on Relay)
   3V3 (17) (18) GPIO24
GPIO10 (19) (20) GND   
 GPIO9 (21) (22) GPIO25
GPIO11 (23) (24) GPIO8 
   GND (25) (26) GPIO7 
 GPIO0 (27) (28) GPIO1 
 GPIO5 (29) (30) GND   
 GPIO6 (31) (32) GPIO12
GPIO13 (33) (34) GND   
GPIO19 (35) (36) GPIO16
GPIO26 (37) (38) GPIO20
   GND (39) (40) GPIO21

We're interested only in the pins 
in the norh-west corner of the board:
5V, GND, GPIO18, GPIO23
,--------------------------------.
| oooooooooooooooooooo J8     +====
| 1ooooooooooooooooooo        | USB
|                             +====
| o1 RUN  Pi Model 3B  V1.2      |
| |D      +---+               +====
| |S      |SoC|               | USB
| |I      +---+               +====
| |0               C|            |
|                  S|       +======
|                  I| |A|   |   Net
| pwr      |HDMI|  0| |u|   +======
`-| |------|    |-----|x|--------'



"""

RELAY_1 = 18
RELAY_2 = 23

PIN_NAMES = {
    RELAY_1: "Relay 1",
    RELAY_2: "Relay 2",
}


def configure_relays():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(RELAY_1, GPIO.OUT)
    GPIO.setup(RELAY_2, GPIO.OUT)


async def relay_on(relay_pin: int, duration: float):
    desc = PIN_NAMES.get(relay_pin)
    if desc:
        print(f"{get_elapsed():5.2f}: {desc} ON for {duration}s")
    GPIO.output(relay_pin, GPIO.LOW)
    await asyncio.sleep(duration)
    GPIO.output(relay_pin, GPIO.HIGH)
    if desc:
        print(f"{get_elapsed():5.2f}: {desc} OFF")


async def stagger_relay_starts():
    task1 = asyncio.create_task(relay_on(RELAY_1, 2))
    await asyncio.sleep(1)  # Stagger RELAY_2 by 1 second
    task2 = asyncio.create_task(relay_on(RELAY_2, 2))
    await asyncio.gather(task1, task2)


def get_elapsed() -> float:
    return time.time() - START_TIME


async def main():
    global START_TIME
    START_TIME = time.time()
    configure_relays()
    for i in range(4):
        await stagger_relay_starts()


if __name__ == "__main__":
    asyncio.run(main())
