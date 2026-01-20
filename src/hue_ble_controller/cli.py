import argparse
import asyncio
from .controller import turn_on, turn_off, sunrise, sundown, flash, set_colour_preset, set_brightness


def main():
    parser = argparse.ArgumentParser(description="Control Hue BLE lights")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # on
    on_parser = subparsers.add_parser("on", help="Turn light on")
    on_parser.add_argument("-b", "--brightness", type=int, default=254, help="Brightness (1-254)")

    # off
    subparsers.add_parser("off", help="Turn light off")

    # sunrise
    sunrise_parser = subparsers.add_parser("sunrise", help="Sunrise fade simulation")
    sunrise_parser.add_argument(
        "-d", "--duration", type=int, default=15, help="Duration in minutes (default: 15)"
    )

    # sundown
    sundown_parser = subparsers.add_parser("sundown", help="Sundown fade simulation")
    sundown_parser.add_argument(
        "-d", "--duration", type=int, default=15, help="Duration in minutes (default: 15)"
    )

    # flash
    flash_parser = subparsers.add_parser("flash", help="Flash the light")
    flash_parser.add_argument(
        "-d", "--duration", type=float, default=1, help="Duration in minutes (default: 1)"
    )
    flash_parser.add_argument(
        "-i", "--interval", type=float, default=0.5, help="Flash interval in seconds (default: 0.5)"
    )

    # preset
    preset_parser = subparsers.add_parser("preset", help="Set colour preset")
    preset_parser.add_argument(
        "name",
        choices=["red", "green", "blue", "warm_white", "cool_white", "purple", "orange", "pink", "yellow"],
        help="Preset name",
    )

    # brightness
    bright_parser = subparsers.add_parser("brightness", help="Set brightness")
    bright_parser.add_argument("level", type=int, help="Brightness level (1-254)")

    args = parser.parse_args()

    if args.command == "on":
        asyncio.run(turn_on(args.brightness))
        print("Light on")
    elif args.command == "off":
        asyncio.run(turn_off())
        print("Light off")
    elif args.command == "sunrise":
        print(f"Starting {args.duration} minute sunrise...")
        asyncio.run(sunrise(args.duration))
    elif args.command == "sundown":
        print(f"Starting {args.duration} minute sundown...")
        asyncio.run(sundown(args.duration))
    elif args.command == "flash":
        print(f"Flashing for {args.duration} minute(s)...")
        asyncio.run(flash(args.duration, args.interval))
    elif args.command == "preset":
        asyncio.run(set_colour_preset(args.name))
        print(f"Set preset: {args.name}")
    elif args.command == "brightness":
        asyncio.run(set_brightness(args.level))
        print(f"Brightness set to {args.level}")


if __name__ == "__main__":
    main()