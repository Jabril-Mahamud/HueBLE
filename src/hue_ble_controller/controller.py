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