"""
CLI for Hue BLE Controller.
Uses controller.py for all operations.
"""
import argparse
import asyncio
import time
from datetime import datetime, timedelta
from .controller import (
    turn_on, turn_off, sunrise, sundown, flash,
    set_colour_preset, set_brightness, set_colour_temp,
    get_light, fade_in, fade_out, alarm, rgb_to_xy,
    load_schedule, COLOURS,
)


async def run_routine(steps: list[dict]):
    """Run a sequence of scheduled effects."""
    from .controller import get_light, fade_in, fade_out, alarm, COLOURS

    print(f"Running routine with {len(steps)} step(s)...")

    light = await get_light()
    effect_names = {"fade_in": "fade in", "fade_out": "fade out", "alarm": "alarm"}

    for i, step in enumerate(steps):
        effect = step.get("effect", "fade_in")
        use_time = step.get("use_time", True)

        print(f"\n[Step {i+1}/{len(steps)}] {effect_names[effect]}")

        # Wait for scheduled time
        if use_time:
            hour = step.get("hour", 7)
            minute = step.get("minute", 30)
            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if target > now:
                print(f"  Waiting until {hour:02d}:{minute:02d}...")
                while datetime.now() < target:
                    remaining = (target - datetime.now()).total_seconds()
                    mins, secs = divmod(int(remaining), 60)
                    hours_r, mins = divmod(mins, 60)
                    if hours_r > 0:
                        print(f"\r  {hours_r}h {mins}m remaining     ", end="", flush=True)
                    else:
                        print(f"\r  {mins}m {secs}s remaining     ", end="", flush=True)
                    await asyncio.sleep(1)
                print()
        else:
            delay_mins = step.get("delay_mins", 0)
            if delay_mins > 0:
                print(f"  Waiting {delay_mins} minutes...")
                end_delay = datetime.now() + timedelta(minutes=delay_mins)
                while datetime.now() < end_delay:
                    remaining = (end_delay - datetime.now()).total_seconds()
                    mins, secs = divmod(int(remaining), 60)
                    print(f"\r  {mins}m {secs}s remaining     ", end="", flush=True)
                    await asyncio.sleep(1)
                print()

        # Run the effect
        if effect == "fade_in":
            duration = step.get("duration", 15)
            print(f"  Running {duration} minute fade in...")
            await fade_in(light, duration)
            print("  ✓ Done")

        elif effect == "fade_out":
            duration = step.get("duration", 15)
            print(f"  Running {duration} minute fade out...")
            await fade_out(light, duration)
            print("  ✓ Done")

        elif effect == "alarm":
            colour = step.get("colour", "red")
            style = step.get("alarm_style", "flash")
            alarm_dur = step.get("alarm_duration", 0)

            xy = COLOURS.get(colour, COLOURS["red"])

            if alarm_dur > 0:
                print(f"  Running {colour} alarm ({style}) for {alarm_dur} min...")
                await alarm(light, xy, style, duration_minutes=alarm_dur)
                print("  ✓ Done")
            else:
                # No duration means run briefly for chained routines
                print(f"  Running {colour} alarm ({style}) for 1 min...")
                await alarm(light, xy, style, duration_minutes=1)
                print("  ✓ Done")

    print("\n✓ Routine complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Control Philips Hue Bluetooth lights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hue-ble-cli on                    Turn on at full brightness
  hue-ble-cli off                   Turn off
  hue-ble-cli preset purple         Set purple colour
  hue-ble-cli brightness 200        Set brightness to 200
  hue-ble-cli sunrise -d 15         15 minute sunrise now
  hue-ble-cli sundown -d 30         30 minute sundown now

  # Scheduled effects
  hue-ble-cli timer fade_in --at 07:30 -d 15    Sunrise at 7:30am
  hue-ble-cli timer alarm --at 07:00 -c red     Red alarm at 7am

  # Run saved schedule (set via GUI, used by systemd)
  hue-ble-cli run --saved
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # on
    on_parser = subparsers.add_parser("on", help="Turn light on")
    on_parser.add_argument("-b", "--brightness", type=int, default=254,
                          help="Brightness 1-254 (default: 254)")

    # off
    subparsers.add_parser("off", help="Turn light off")

    # sunrise
    sunrise_parser = subparsers.add_parser("sunrise", help="Sunrise fade (warm dim → cool bright)")
    sunrise_parser.add_argument("-d", "--duration", type=float, default=15,
                               help="Duration in minutes (default: 15)")

    # sundown
    sundown_parser = subparsers.add_parser("sundown", help="Sundown fade (cool bright → warm dim → off)")
    sundown_parser.add_argument("-d", "--duration", type=float, default=15,
                               help="Duration in minutes (default: 15)")

    # flash
    flash_parser = subparsers.add_parser("flash", help="Flash/alarm effect (runs until Ctrl+C)")
    flash_parser.add_argument("-s", "--style", choices=["flash", "fast", "breathing"],
                             default="flash", help="Flash style (default: flash)")
    flash_parser.add_argument("-c", "--colour", default="red",
                             help="Colour preset name (default: red)")

    # preset
    preset_parser = subparsers.add_parser("preset", help="Set colour preset")
    preset_parser.add_argument("name", choices=list(COLOURS.keys()), help="Preset name")

    # brightness
    bright_parser = subparsers.add_parser("brightness", help="Set brightness")
    bright_parser.add_argument("level", type=int, help="Brightness 1-254")

    # temp
    temp_parser = subparsers.add_parser("temp", help="Set colour temperature")
    temp_parser.add_argument("mireds", type=int, help="Temperature 153 (cool) to 500 (warm)")

    # timer - schedule an effect
    timer_parser = subparsers.add_parser("timer", help="Schedule an effect")
    timer_parser.add_argument("effect", choices=["fade_in", "fade_out", "alarm"],
                             help="Effect to run")
    timer_parser.add_argument("-d", "--duration", type=float, default=15,
                             help="Effect duration in minutes (default: 15)")
    timer_parser.add_argument("--at", type=str, default=None,
                             help="Run at specific time HH:MM (e.g. --at 07:30)")
    timer_parser.add_argument("--delay", type=float, default=0,
                             help="Delay before starting in minutes (default: 0)")
    timer_parser.add_argument("-c", "--colour", default="red",
                             help="Alarm colour preset or hex (default: red)")
    timer_parser.add_argument("-s", "--style", choices=["flash", "fast", "breathing"],
                             default="flash", help="Alarm style (default: flash)")

    # run - run saved schedule (for systemd service)
    run_parser = subparsers.add_parser("run", help="Run saved schedule from config")
    run_parser.add_argument("--saved", action="store_true",
                           help="Run the schedule saved in ~/.config/hue-ble/schedule.json")

    args = parser.parse_args()

    try:
        if args.command == "on":
            asyncio.run(turn_on(args.brightness))
            print(f"✓ Light on (brightness: {args.brightness})")

        elif args.command == "off":
            asyncio.run(turn_off())
            print("✓ Light off")

        elif args.command == "sunrise":
            print(f"Starting {args.duration} minute sunrise...")
            asyncio.run(sunrise(args.duration))

        elif args.command == "sundown":
            print(f"Starting {args.duration} minute sundown...")
            asyncio.run(sundown(args.duration))

        elif args.command == "flash":
            colour = args.colour
            if colour in COLOURS:
                xy = COLOURS[colour]
            else:
                print(f"✗ Unknown colour: {colour}")
                print(f"  Available: {', '.join(COLOURS.keys())}")
                return

            print(f"Flashing {colour} ({args.style})... Press Ctrl+C to stop")

            async def run_flash():
                light = await get_light()
                try:
                    await alarm(light, xy, args.style)
                except asyncio.CancelledError:
                    await light.set_power(True)
                    print("\n✓ Stopped")

            try:
                asyncio.run(run_flash())
            except KeyboardInterrupt:
                print("\n✓ Stopped")

        elif args.command == "preset":
            asyncio.run(set_colour_preset(args.name))
            print(f"✓ Colour: {args.name}")

        elif args.command == "brightness":
            asyncio.run(set_brightness(args.level))
            print(f"✓ Brightness: {args.level}")

        elif args.command == "temp":
            asyncio.run(set_colour_temp(args.mireds))
            warmth = "cool" if args.mireds < 300 else "warm" if args.mireds > 350 else "neutral"
            print(f"✓ Temperature: {args.mireds} ({warmth})")

        elif args.command == "timer":
            async def run_timer():
                wait_seconds = 0
                target_time_str = ""

                # Parse --at time
                if args.at:
                    import re
                    match = re.match(r"(\d{1,2}):(\d{2})", args.at)
                    if not match:
                        print(f"✗ Invalid time format: {args.at} (use HH:MM)")
                        return

                    hour, minute = int(match.group(1)), int(match.group(2))
                    if not (0 <= hour <= 23 and 0 <= minute <= 59):
                        print(f"✗ Invalid time: {args.at}")
                        return

                    now = datetime.now()
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # If time passed today, run immediately
                    if target > now:
                        wait_seconds = (target - now).total_seconds()
                        target_time_str = target.strftime("%H:%M")

                # Or use --delay
                elif args.delay > 0:
                    wait_seconds = args.delay * 60
                    target = datetime.now() + timedelta(seconds=wait_seconds)
                    target_time_str = target.strftime("%H:%M")

                # Wait if needed
                if wait_seconds > 0:
                    print(f"Scheduled {args.effect} at {target_time_str}")
                    start = time.time()
                    while time.time() - start < wait_seconds:
                        remaining = wait_seconds - (time.time() - start)
                        mins, secs = divmod(int(remaining), 60)
                        hours, mins = divmod(mins, 60)
                        if hours > 0:
                            print(f"\r  Waiting... {hours}h {mins}m     ", end="", flush=True)
                        else:
                            print(f"\r  Waiting... {mins}m {secs}s     ", end="", flush=True)
                        await asyncio.sleep(1)
                    print()

                light = await get_light()

                if args.effect == "fade_in":
                    print(f"Running {args.duration} minute fade in...")
                    await fade_in(light, args.duration)
                    print("✓ Fade in complete")

                elif args.effect == "fade_out":
                    print(f"Running {args.duration} minute fade out...")
                    await fade_out(light, args.duration)
                    print("✓ Fade out complete")

                elif args.effect == "alarm":
                    colour = args.colour
                    if colour in COLOURS:
                        xy = COLOURS[colour]
                    else:
                        xy = COLOURS.get("red", (0.68, 0.31))

                    print(f"Running alarm ({args.style})... Press Ctrl+C to stop")
                    await alarm(light, xy, args.style)

            try:
                asyncio.run(run_timer())
            except KeyboardInterrupt:
                print("\n✓ Stopped")

        elif args.command == "run":
            if not args.saved:
                print("✗ Use --saved to run the saved schedule")
                return

            config = load_schedule()
            if not config:
                print("✗ No saved schedule found")
                print("  Use the GUI to save a schedule, or run:")
                print("  hue-ble-cli timer fade_in --at 07:30 -d 15")
                return

            # Check if it's a routine
            if "routine" in config:
                try:
                    asyncio.run(run_routine(config["routine"]))
                except KeyboardInterrupt:
                    print("\n✓ Routine stopped")
                return

            async def run_saved():
                hour = config.get("hour", 7)
                minute = config.get("minute", 30)
                effect = config.get("effect", "fade_in")
                duration = config.get("duration", 15)
                colour = config.get("colour", "red")
                alarm_style = config.get("alarm_style", "flash")
                alarm_duration = config.get("alarm_duration", 0)
                use_time = config.get("use_time", True)
                delay_mins = config.get("delay_mins", 0)

                effect_names = {"fade_in": "fade in", "fade_out": "fade out", "alarm": "alarm"}

                if use_time:
                    print(f"Loaded: {effect_names[effect]} at {hour:02d}:{minute:02d}")

                    now = datetime.now()
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    if target > now:
                        print(f"Waiting until {hour:02d}:{minute:02d}...")

                        while datetime.now() < target:
                            remaining = (target - datetime.now()).total_seconds()
                            mins, secs = divmod(int(remaining), 60)
                            hours_r, mins = divmod(mins, 60)
                            if hours_r > 0:
                                print(f"\r  {hours_r}h {mins}m remaining     ", end="", flush=True)
                            else:
                                print(f"\r  {mins}m {secs}s remaining     ", end="", flush=True)
                            await asyncio.sleep(1)
                        print()
                    else:
                        print("Scheduled time passed, running now...")
                else:
                    print(f"Loaded: {effect_names[effect]} in {delay_mins}min")
                    if delay_mins > 0:
                        delay_secs = delay_mins * 60
                        end_delay = datetime.now() + timedelta(seconds=delay_secs)
                        while datetime.now() < end_delay:
                            remaining = (end_delay - datetime.now()).total_seconds()
                            mins, secs = divmod(int(remaining), 60)
                            print(f"\r  Starting in {mins}m {secs}s     ", end="", flush=True)
                            await asyncio.sleep(1)
                        print()

                light = await get_light()

                if effect == "fade_in":
                    print(f"Running {duration} minute fade in...")
                    await fade_in(light, duration)
                    print("✓ Fade in complete")

                elif effect == "fade_out":
                    print(f"Running {duration} minute fade out...")
                    await fade_out(light, duration)
                    print("✓ Fade out complete")

                elif effect == "alarm":
                    if colour in COLOURS:
                        xy = COLOURS[colour]
                    else:
                        xy = COLOURS.get("red", (0.68, 0.31))

                    if alarm_duration > 0:
                        print(f"Running alarm ({alarm_style}) for {alarm_duration} min...")
                        await alarm(light, xy, alarm_style, duration_minutes=alarm_duration)
                        print("✓ Alarm complete")
                    else:
                        print(f"Running alarm ({alarm_style})... Press Ctrl+C to stop")
                        await alarm(light, xy, alarm_style)

            try:
                asyncio.run(run_saved())
            except KeyboardInterrupt:
                print("\n✓ Stopped")

    except KeyboardInterrupt:
        print("\n✗ Cancelled")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    main()