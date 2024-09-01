# Hosebeast, An irrigation control system

This project is overkill for a home irrigation system, but I guess I did it.

## Current features, September 2024:
- Host a website on a RasPi 4, based on [Reflex](https://reflex.dev)
- Control 2 irrigation valves with buttons on the website
- Schedule irrigation sessions with the website
- Measure and display water level in a water tank with a [Walfront G1/4" pressure transducer](https://www.amazon.com/dp/B07KJHRPLG/) and Analog -> Digital Converter (ADC) ([ADS1115](https://www.amazon.com/gp/product/B0CNV9G4K1), Adafruit docs [here](https://learn.adafruit.com/adafruit-4-channel-adc-breakouts/overview))
- Record and display historical water level data

## System requirements:
- RasPi 4 running Raspbian ARM 64-bit OS. (Others should work, but I only test on RPi 4)
- This repository, currently [here](https://github.com/etjones/hosebeast)
    - `git clone https://github.com/etjones/hosebeast.git`
- `uv` Python package manager ([Installation](https://docs.astral.sh/uv/getting-started/installation/))
 - `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `tmux` for running the app in the background
 - `sudo apt-get install tmux`
- Enable I2C on the RasPi 4:
    ```shell
    sudo raspi-config
    # (menus: Interfacing Options -> I2C -> Enable -> Finish)
    # reboot Pi: `sudo reboot now`
    ```
- Create `uv` virtual environment:
    ```shell
    cd hosebeast
    uv venv
    source .venv/bin/activate
    ```
- Install dependencies:
    ```shell
    uv pip install .
    ```

- Run the app:
    `reflex run` (development mode)
    or
    `./start_hosebeast.sh` (production mode)


Evan Jones<evan_t_jones@mac.com>