import asyncio
import threading
import tkinter as tk
from tkinter import colorchooser
from typing import Callable

from .controller import (
    get_light,
    sunrise,
    sundown,
    flash,
    COLOURS,
)


def rgb_to_xy(r: int, g: int, b: int) -> tuple[float, float]:
    """Convert RGB (0-255) to CIE xy colour space."""
    # Normalize RGB values
    r = r / 255.0
    g = g / 255.0
    b = b / 255.0

    # Apply gamma correction
    r = ((r + 0.055) / 1.055) ** 2.4 if r > 0.04045 else r / 12.92
    g = ((g + 0.055) / 1.055) ** 2.4 if g > 0.04045 else g / 12.92
    b = ((b + 0.055) / 1.055) ** 2.4 if b > 0.04045 else b / 12.92

    # Convert to XYZ
    X = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    Y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    Z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # Convert to xy
    total = X + Y + Z
    if total == 0:
        return (0.31271, 0.32902)  # D65 white point

    x = X / total
    y = Y / total

    return (x, y)


def run_async(coro):
    """Run an async coroutine from sync code."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class HueControllerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Hue BLE Controller")
        self.root.geometry("300x580")
        self.root.resizable(False, False)

        self.light = None
        self._setup_ui()

    def _setup_ui(self):
        # Connection frame
        conn_frame = tk.LabelFrame(self.root, text="Connection", padx=10, pady=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        self.status_label = tk.Label(conn_frame, text="Disconnected", fg="red")
        self.status_label.pack()

        tk.Button(conn_frame, text="Connect", command=self._connect).pack(pady=5)

        # Power frame
        power_frame = tk.LabelFrame(self.root, text="Power", padx=10, pady=10)
        power_frame.pack(fill="x", padx=10, pady=5)

        btn_frame = tk.Frame(power_frame)
        btn_frame.pack()
        tk.Button(btn_frame, text="On", width=10, command=self._turn_on).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Off", width=10, command=self._turn_off).pack(side="left", padx=5)

        # Brightness frame
        bright_frame = tk.LabelFrame(self.root, text="Brightness", padx=10, pady=10)
        bright_frame.pack(fill="x", padx=10, pady=5)

        self.brightness_var = tk.IntVar(value=254)
        self.brightness_slider = tk.Scale(
            bright_frame,
            from_=1,
            to=254,
            orient="horizontal",
            variable=self.brightness_var,
            command=self._on_brightness_change,
        )
        self.brightness_slider.pack(fill="x")

        # Colour presets frame
        presets_frame = tk.LabelFrame(self.root, text="Colour Presets", padx=10, pady=10)
        presets_frame.pack(fill="x", padx=10, pady=5)

        preset_grid = tk.Frame(presets_frame)
        preset_grid.pack()

        for i, (name, _) in enumerate(COLOURS.items()):
            row, col = divmod(i, 3)
            btn = tk.Button(
                preset_grid,
                text=name.replace("_", " ").title(),
                width=10,
                command=lambda n=name: self._set_preset(n),
            )
            btn.grid(row=row, column=col, padx=2, pady=2)

        # Custom colour frame
        custom_frame = tk.LabelFrame(self.root, text="Custom Colour", padx=10, pady=10)
        custom_frame.pack(fill="x", padx=10, pady=5)

        tk.Button(custom_frame, text="Pick Colour", command=self._pick_colour).pack()

        # Colour temp frame
        temp_frame = tk.LabelFrame(self.root, text="Colour Temperature", padx=10, pady=10)
        temp_frame.pack(fill="x", padx=10, pady=5)

        temp_labels = tk.Frame(temp_frame)
        temp_labels.pack(fill="x")
        tk.Label(temp_labels, text="Cool").pack(side="left")
        tk.Label(temp_labels, text="Warm").pack(side="right")

        self.temp_var = tk.IntVar(value=300)
        self.temp_slider = tk.Scale(
            temp_frame,
            from_=153,
            to=500,
            orient="horizontal",
            variable=self.temp_var,
            command=self._on_temp_change,
            showvalue=False,
        )
        self.temp_slider.pack(fill="x")

        # Effects frame
        effects_frame = tk.LabelFrame(self.root, text="Effects", padx=10, pady=10)
        effects_frame.pack(fill="x", padx=10, pady=5)

        effects_btn_frame = tk.Frame(effects_frame)
        effects_btn_frame.pack()

        self.sunrise_btn = tk.Button(effects_btn_frame, text="Sunrise", width=8, command=self._start_sunrise)
        self.sunrise_btn.pack(side="left", padx=5)

        self.sundown_btn = tk.Button(effects_btn_frame, text="Sundown", width=8, command=self._start_sundown)
        self.sundown_btn.pack(side="left", padx=5)

        self.flash_btn = tk.Button(effects_btn_frame, text="Flash", width=8, command=self._start_flash)
        self.flash_btn.pack(side="left", padx=5)

        # Duration frame
        duration_frame = tk.Frame(effects_frame)
        duration_frame.pack(pady=(10, 0))
        tk.Label(duration_frame, text="Duration (min):").pack(side="left")
        self.duration_var = tk.IntVar(value=1)
        self.duration_spinbox = tk.Spinbox(duration_frame, from_=1, to=60, width=5, textvariable=self.duration_var)
        self.duration_spinbox.pack(side="left", padx=5)

    def _connect(self):
        try:
            self.light = run_async(get_light())
            self.status_label.config(text="Connected", fg="green")
        except Exception as e:
            self.status_label.config(text=f"Error: {e}", fg="red")

    def _ensure_connected(self):
        if not self.light:
            self._connect()
        return self.light is not None

    def _turn_on(self):
        if self._ensure_connected():
            run_async(self.light.set_power(True))

    def _turn_off(self):
        if self._ensure_connected():
            run_async(self.light.set_power(False))

    def _on_brightness_change(self, value):
        if self.light:
            run_async(self.light.set_brightness(int(value)))

    def _on_temp_change(self, value):
        if self.light:
            run_async(self.light.set_colour_temp(int(value)))

    def _set_preset(self, name: str):
        if self._ensure_connected():
            x, y = COLOURS[name]
            run_async(self.light.set_colour_xy(x, y))

    def _pick_colour(self):
        if self._ensure_connected():
            colour = colorchooser.askcolor(title="Choose Colour")
            if colour[0]:
                r, g, b = [int(c) for c in colour[0]]
                x, y = rgb_to_xy(r, g, b)
                run_async(self.light.set_colour_xy(x, y))

    def _run_effect_in_thread(self, coro, btn):
        """Run an effect in a background thread to avoid blocking the GUI."""
        def run():
            btn.config(state="disabled")
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(coro)
                loop.close()
            finally:
                self.root.after(0, lambda: btn.config(state="normal"))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _start_sunrise(self):
        if self._ensure_connected():
            duration = self.duration_var.get()
            self._run_effect_in_thread(sunrise(duration), self.sunrise_btn)

    def _start_sundown(self):
        if self._ensure_connected():
            duration = self.duration_var.get()
            self._run_effect_in_thread(sundown(duration), self.sundown_btn)

    def _start_flash(self):
        if self._ensure_connected():
            duration = self.duration_var.get()
            self._run_effect_in_thread(flash(duration_minutes=duration), self.flash_btn)

    def run(self):
        self.root.mainloop()


def main():
    app = HueControllerGUI()
    app.run()


if __name__ == "__main__":
    main()