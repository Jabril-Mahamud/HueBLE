# Hue BLE Controller

Control Philips Hue Bluetooth lights directly from your computer — no bridge required.

## Features

- 💡 On/Off control
- 🌗 Brightness adjustment
- 🌈 Full colour control (XY colour space)
- 🌡️ Colour temperature control
- 🎨 Simple GUI with colour picker
- 🐍 Python API for scripting/automation

## Requirements

- Python 3.11+
- A Philips Hue Bluetooth-enabled bulb
- Bluetooth adapter on your computer
- Linux (BlueZ), Windows 10+, or macOS

## Installation

```bash
pip install hue-ble-controller
```

Or install from source:

```bash
git clone https://github.com/Jabril-Mahamud/hue-ble-controller.git
cd hue-ble-controller
pip install -e .
```

## Setup

### 1. Find your bulb's MAC address

```python
import asyncio
from bleak import BleakScanner

async def scan():
    devices = await BleakScanner.discover(timeout=10)
    for d in devices:
        if d.name:
            print(f"{d.address} - {d.name}")

asyncio.run(scan())
```

### 2. Set the MAC address

Create a `.env` file in your project directory:

```sh
HUE_MAC_ADDRESS=XX:XX:XX:XX:XX:XX
```

Or export it directly:

```bash
export HUE_MAC_ADDRESS="XX:XX:XX:XX:XX:XX"
```

## Usage

### GUI

```bash
hue-ble
```

### CLI

```bash
# Turn on/off
hue-ble-cli on
hue-ble-cli on --brightness 150
hue-ble-cli off

# Sunrise simulation (fade in from warm to cool)
hue-ble-cli sunrise
hue-ble-cli sunrise --duration 15

# Sundown simulation (fade out from cool to warm)
hue-ble-cli sundown
hue-ble-cli sundown --duration 15

# Flash
hue-ble-cli flash
hue-ble-cli flash --duration 2 --interval 0.5

# Colour presets
hue-ble-cli preset purple
hue-ble-cli preset warm_white

# Set brightness
hue-ble-cli brightness 200
```

### Python API

```python
import asyncio
from hue_ble_controller import (
    turn_on, turn_off, set_colour_preset, set_brightness,
    sunrise, sundown, flash
)

# Turn on with max brightness
asyncio.run(turn_on(brightness=254))

# Set a colour preset
asyncio.run(set_colour_preset("purple"))

# Set custom colour (XY colour space)
from hue_ble_controller import set_colour_xy
asyncio.run(set_colour_xy(0.3, 0.3))

# Set colour temperature (153=cool, 500=warm)
from hue_ble_controller import set_colour_temp
asyncio.run(set_colour_temp(300))

# Sunrise simulation (15 minute fade in)
asyncio.run(sunrise(duration_minutes=15))

# Sundown simulation (15 minute fade out)
asyncio.run(sundown(duration_minutes=15))

# Flash for 1 minute
asyncio.run(flash(duration_minutes=1, interval=0.5))

# Turn off
asyncio.run(turn_off())
```

### Available colour presets

- `red`
- `green`
- `blue`
- `warm_white`
- `cool_white`
- `purple`
- `orange`
- `pink`
- `yellow`

## Run at startup (Linux)

Create a systemd service at `~/.config/systemd/user/hue-sunrise.service`:

```ini
[Unit]
Description=Hue sunrise light fade
After=bluetooth.target

[Service]
Type=simple
Environment="HUE_MAC_ADDRESS=XX:XX:XX:XX:XX:XX"
ExecStart=/home/YOUR_USER/.local/bin/hue-ble-cli sunrise --duration 15
Restart=no

[Install]
WantedBy=default.target
```

Enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable hue-sunrise.service
```

Test it manually:

```bash
systemctl --user start hue-sunrise.service
```

## Troubleshooting

### Bulb not found

- Make sure the bulb is powered on
- Check that your Bluetooth adapter is working: `bluetoothctl show`
- The bulb might be paired to another device — factory reset it by turning it off/on 5-6 times quickly

### Permission denied (Linux)

Add your user to the `bluetooth` group:

```bash
sudo usermod -aG bluetooth $USER
```

Then log out and back in.

## Credits

Built on top of [HueBLE](https://github.com/flip-dots/HueBLE) and [Bleak](https://github.com/hbldh/bleak).

## License

MIT