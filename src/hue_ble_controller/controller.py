import asyncio
import os
from pathlib import Path
from bleak import BleakScanner
import HueBLE
from dotenv import load_dotenv

# Load .env from current directory or package directory
load_dotenv()
load_dotenv(Path(__file__).parent.parent.parent / ".env")

def get_mac_address() -> str:
    mac = os.environ.get("HUE_MAC_ADDRESS")
    if not mac:
        raise ValueError("HUE_MAC_ADDRESS not set. Create a .env file with HUE_MAC_ADDRESS=XX:XX:XX:XX:XX:XX")
    return mac

async def get_light() -> HueBLE.HueBleLight:
    mac = get_mac_address()
    device = await BleakScanner.find_device_by_address(mac)
    if not device:
        raise ConnectionError(f"Could not find device with address {mac}")
    return HueBLE.HueBleLight(device)

async def turn_on(brightness: int = 254):
    light = await get_light()
    await light.set_power(True)
    await light.set_brightness(brightness)

async def turn_off():
    light = await get_light()
    await light.set_power(False)

async def set_colour_xy(x: float, y: float):
    light = await get_light()
    await light.set_colour_xy(x, y)

async def set_colour_temp(mireds: int):
    """Set colour temperature. 153 = coolest, 500 = warmest."""
    light = await get_light()
    await light.set_colour_temp(mireds)

async def set_brightness(brightness: int):
    """Set brightness. 0-254."""
    light = await get_light()
    await light.set_brightness(brightness)

async def sunrise(duration_minutes: int = 15):
    """
    Simulate sunrise by gradually increasing brightness
    and shifting from warm to cool colour temperature.
    """
    light = await get_light()
    await light.set_power(True)

    steps = duration_minutes * 6  # update every 10 seconds
    step_delay = 10

    # Start: dim and warm (500 mireds = warmest)
    # End: bright and cooler (250 mireds = daylight-ish)
    start_brightness = 1
    end_brightness = 254
    start_temp = 500  # warm
    end_temp = 250    # cool daylight

    for i in range(steps + 1):
        progress = i / steps

        brightness = int(start_brightness + (end_brightness - start_brightness) * progress)
        temp = int(start_temp + (end_temp - start_temp) * progress)

        await light.set_brightness(brightness)
        await light.set_colour_temp(temp)

        if i < steps:
            await asyncio.sleep(step_delay)

    print("Sunrise complete!")


async def sundown(duration_minutes: int = 15):
    """
    Simulate sundown by gradually decreasing brightness
    and shifting from cool to warm colour temperature.
    """
    light = await get_light()
    await light.set_power(True)

    steps = duration_minutes * 6  # update every 10 seconds
    step_delay = 10

    # Start: bright and cool
    # End: dim and warm
    start_brightness = 254
    end_brightness = 1
    start_temp = 250  # cool daylight
    end_temp = 500    # warm

    for i in range(steps + 1):
        progress = i / steps

        brightness = int(start_brightness + (end_brightness - start_brightness) * progress)
        temp = int(start_temp + (end_temp - start_temp) * progress)

        await light.set_brightness(brightness)
        await light.set_colour_temp(temp)

        if i < steps:
            await asyncio.sleep(step_delay)

    await light.set_power(False)
    print("Sundown complete!")


async def flash(duration_minutes: float = 1, interval: float = 0.5):
    """
    Flash the light on and off for a duration.
    """
    light = await get_light()

    end_time = asyncio.get_event_loop().time() + (duration_minutes * 60)
    state = True

    await light.set_power(True)
    await light.set_brightness(254)

    while asyncio.get_event_loop().time() < end_time:
        state = not state
        await light.set_power(state)
        await asyncio.sleep(interval)

    await light.set_power(True)
    print("Flash complete!")


# Convenience presets
COLOURS = {
    "red": (0.675, 0.322),
    "green": (0.409, 0.518),
    "blue": (0.167, 0.04),
    "warm_white": (0.459, 0.41),
    "cool_white": (0.31, 0.316),
    "purple": (0.25, 0.1),
    "orange": (0.6, 0.38),
    "pink": (0.4, 0.2),
    "yellow": (0.5, 0.45),
}

async def set_colour_preset(name: str):
    if name not in COLOURS:
        raise ValueError(f"Unknown colour preset: {name}. Available: {list(COLOURS.keys())}")
    x, y = COLOURS[name]
    await set_colour_xy(x, y)