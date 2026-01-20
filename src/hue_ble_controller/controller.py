"""
Core controller for Hue BLE lights.
All light operations and effects are defined here.
Both CLI and GUI should use these functions.
"""
import asyncio
import json
import os
from pathlib import Path
from bleak import BleakScanner
import HueBLE
from dotenv import load_dotenv

# Load .env
load_dotenv()
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Config directory
CONFIG_DIR = Path.home() / ".config" / "hue-ble"
CONFIG_FILE = CONFIG_DIR / "schedule.json"


# === CONFIG ===
def save_schedule(hour: int, minute: int, effect: str, duration: float,
                  colour: str = "red", alarm_style: str = "flash",
                  use_time: bool = True, delay_mins: float = 0,
                  alarm_duration: float = 0):
    """Save schedule to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {
        "hour": hour,
        "minute": minute,
        "effect": effect,
        "duration": duration,
        "colour": colour,
        "alarm_style": alarm_style,
        "use_time": use_time,
        "delay_mins": delay_mins,
        "alarm_duration": alarm_duration,  # 0 = run until stopped
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    return config


def save_routine(steps: list[dict]):
    """
    Save a routine (sequence of effects) to config file.

    Each step is a dict with:
        - effect: "fade_in", "fade_out", or "alarm"
        - hour, minute: when to run (24h format)
        - duration: for fades, length in minutes; for alarm, how long to flash (0 = until next step)
        - colour: for alarm
        - alarm_style: for alarm
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {"routine": steps}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    return config


def load_schedule() -> dict | None:
    """Load schedule from config file."""
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def clear_schedule():
    """Remove saved schedule."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


# === COLOUR PRESETS ===
# CIE 1931 xy coordinates - tuned for Hue bulbs
COLOURS = {
    "red": (0.68, 0.31),
    "green": (0.17, 0.70),
    "blue": (0.15, 0.06),
    "yellow": (0.44, 0.52),
    "orange": (0.58, 0.40),
    "purple": (0.27, 0.12),
    "pink": (0.50, 0.25),
    "cyan": (0.15, 0.35),
    "warm_white": (0.46, 0.41),
    "cool_white": (0.31, 0.32),
}


# === CONNECTION ===
def get_mac_address() -> str:
    mac = os.environ.get("HUE_MAC_ADDRESS")
    if not mac:
        raise ValueError(
            "HUE_MAC_ADDRESS not set. "
            "Create a .env file with HUE_MAC_ADDRESS=XX:XX:XX:XX:XX:XX"
        )
    return mac


async def get_light() -> HueBLE.HueBleLight:
    """Connect to the Hue light and return the light object."""
    mac = get_mac_address()
    device = await BleakScanner.find_device_by_address(mac, timeout=10)
    if not device:
        raise ConnectionError(f"Could not find device with address {mac}")
    return HueBLE.HueBleLight(device)


# === BASIC OPERATIONS ===
async def turn_on(brightness: int = 254):
    """Turn on the light with specified brightness."""
    light = await get_light()
    await light.set_power(True)
    await light.set_brightness(brightness)


async def turn_off():
    """Turn off the light."""
    light = await get_light()
    await light.set_power(False)


async def set_brightness(brightness: int):
    """Set brightness (1-254)."""
    light = await get_light()
    await light.set_brightness(brightness)


async def set_colour_xy(x: float, y: float):
    """Set colour using CIE xy coordinates."""
    light = await get_light()
    await light.set_colour_xy(x, y)


async def set_colour_temp(mireds: int):
    """Set colour temperature. 153 = coolest, 500 = warmest."""
    light = await get_light()
    await light.set_colour_temp(mireds)


async def set_colour_preset(name: str):
    """Set a colour preset by name."""
    if name not in COLOURS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(COLOURS.keys())}")
    x, y = COLOURS[name]
    await set_colour_xy(x, y)


# === EFFECTS ===
async def fade_in(
    light: HueBLE.HueBleLight,
    duration_minutes: float = 15,
    cancel_check=None,
    progress_callback=None,
):
    """
    Fade in from dim/warm to bright/cool (sunrise effect).

    Args:
        light: Connected HueBleLight instance
        duration_minutes: How long the fade should take
        cancel_check: Optional callable that returns True to cancel
        progress_callback: Optional callable(progress: float) for UI updates
    """
    await light.set_power(True)
    await light.set_brightness(1)
    await light.set_colour_temp(500)  # Start warm

    steps = max(int(duration_minutes * 6), 1)
    step_delay = (duration_minutes * 60) / steps

    for i in range(steps + 1):
        if cancel_check and cancel_check():
            return False

        progress = i / steps
        brightness = int(1 + 253 * progress)
        temp = int(500 - 250 * progress)  # Warm to cool

        await light.set_brightness(brightness)
        await light.set_colour_temp(temp)

        if progress_callback:
            progress_callback(progress)

        if i < steps:
            await asyncio.sleep(step_delay)

    return True


async def fade_out(
    light: HueBLE.HueBleLight,
    duration_minutes: float = 15,
    cancel_check=None,
    progress_callback=None,
):
    """
    Fade out from bright/cool to dim/warm then off (sunset effect).
    """
    await light.set_power(True)
    await light.set_brightness(254)
    await light.set_colour_temp(250)  # Start cool

    steps = max(int(duration_minutes * 6), 1)
    step_delay = (duration_minutes * 60) / steps

    for i in range(steps + 1):
        if cancel_check and cancel_check():
            return False

        progress = i / steps
        brightness = int(254 - 253 * progress)
        temp = int(250 + 250 * progress)  # Cool to warm

        await light.set_brightness(max(1, brightness))
        await light.set_colour_temp(temp)

        if progress_callback:
            progress_callback(progress)

        if i < steps:
            await asyncio.sleep(step_delay)

    await light.set_power(False)
    return True


async def alarm(
    light: HueBLE.HueBleLight,
    colour_xy: tuple[float, float] = (0.68, 0.31),  # Red default
    style: str = "flash",  # flash, fast, breathing
    cancel_check=None,
    duration_minutes: float = 0,  # 0 = run until cancelled
):
    """
    Flash/pulse the light with a colour.

    Args:
        duration_minutes: If > 0, auto-stop after this many minutes.
                         If 0, run until cancelled.

    Styles:
        - flash: Standard on/off flashing (0.5s interval)
        - fast: Rapid flashing (0.2s interval)
        - breathing: Smooth fade in/out pulse
    """
    await light.set_power(True)
    await light.set_brightness(254)
    await light.set_colour_xy(*colour_xy)

    start_time = asyncio.get_event_loop().time()
    end_time = start_time + (duration_minutes * 60) if duration_minutes > 0 else None

    def should_stop():
        if cancel_check and cancel_check():
            return True
        if end_time and asyncio.get_event_loop().time() >= end_time:
            return True
        return False

    if style == "breathing":
        while not should_stop():
            # Fade down
            for b in range(254, 20, -15):
                if should_stop():
                    break
                await light.set_brightness(b)
                await asyncio.sleep(0.05)

            if should_stop():
                break

            # Fade up
            for b in range(20, 254, 15):
                if should_stop():
                    break
                await light.set_brightness(b)
                await asyncio.sleep(0.05)
    else:
        interval = 0.2 if style == "fast" else 0.5
        state = True

        while not should_stop():
            state = not state
            await light.set_power(state)
            await asyncio.sleep(interval)

    await light.set_power(True)
    await light.set_brightness(254)
    return True


# === STANDALONE VERSIONS (for CLI) ===
async def sunrise(duration_minutes: float = 15):
    """Standalone sunrise effect."""
    light = await get_light()
    await fade_in(light, duration_minutes)
    print("Sunrise complete!")


async def sundown(duration_minutes: float = 15):
    """Standalone sunset effect."""
    light = await get_light()
    await fade_out(light, duration_minutes)
    print("Sundown complete!")


async def flash(duration_minutes: float = 1, interval: float = 0.5):
    """Standalone flash effect."""
    light = await get_light()
    await alarm(light, duration_minutes, interval=interval)
    print("Flash complete!")


# === COLOUR CONVERSION ===
def rgb_to_xy(r: int, g: int, b: int) -> tuple[float, float]:
    """Convert RGB (0-255) to CIE xy colour space."""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    r = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
    g = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
    b = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92
    X = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    Y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    Z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    total = X + Y + Z
    if total == 0:
        return (0.31271, 0.32902)
    return (X / total, Y / total)


def xy_to_rgb(x: float, y: float, brightness: float = 1.0) -> tuple[int, int, int]:
    """Convert CIE xy to approximate RGB for display."""
    z = 1.0 - x - y
    Y = brightness
    X = (Y / y) * x if y > 0 else 0
    Z = (Y / y) * z if y > 0 else 0
    r = X * 3.2404542 - Y * 1.5371385 - Z * 0.4985314
    g = -X * 0.9692660 + Y * 1.8760108 + Z * 0.0415560
    b = X * 0.0556434 - Y * 0.2040259 + Z * 1.0572252
    r = 12.92 * r if r <= 0.0031308 else 1.055 * (r ** (1 / 2.4)) - 0.055
    g = 12.92 * g if g <= 0.0031308 else 1.055 * (g ** (1 / 2.4)) - 0.055
    b = 12.92 * b if b <= 0.0031308 else 1.055 * (b ** (1 / 2.4)) - 0.055
    return (
        max(0, min(255, int(r * 255))),
        max(0, min(255, int(g * 255))),
        max(0, min(255, int(b * 255))),
    )