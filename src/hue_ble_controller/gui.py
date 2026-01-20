"""
Hue BLE Controller GUI.
Uses controller.py for all light operations.
"""
import asyncio
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from .controller import (
    get_light,
    fade_in,
    fade_out,
    alarm,
    rgb_to_xy,
    xy_to_rgb,
    save_schedule,
    load_schedule,
    save_routine,
    COLOURS,
)

# Theme
THEME = {
    "bg": "#0d0d0d",
    "bg_secondary": "#1a1a1a",
    "bg_input": "#151515",
    "border": "#2a2a2a",
    "text": "#e0e0e0",
    "text_dim": "#666666",
    "accent": "#00d9a0",
    "accent_dim": "#00a87a",
    "error": "#ff4757",
    "warning": "#ffa502",
}

# Alarm colour presets (subset of main colours)
ALARM_COLOURS = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink"]


class AsyncHandler:
    def __init__(self):
        self._loop = None
        self._thread = None
        self._started = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._started.wait()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    def run_async(self, coro, callback=None):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        if callback:
            future.add_done_callback(lambda f: callback(f.exception()))
        return future

    def stop(self):
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)


class HueControllerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("hue-ble")
        self.root.geometry("420x750")
        self.root.minsize(380, 650)
        self.root.configure(bg=THEME["bg"])

        self.light = None
        self._async = AsyncHandler()
        self._async.start()
        self._debounce_ids = {}
        self._timer_cancel = False
        self._timer_running = False
        self._power_state = False
        self._alarm_colour = "red"

        self._setup_styles()
        self._setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._timer_cancel = True
        self._async.stop()
        self.root.destroy()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=THEME["bg"])
        style.configure("Dark.TLabel", background=THEME["bg"], foreground=THEME["text"],
                       font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=THEME["bg"], foreground=THEME["accent"],
                       font=("Segoe UI", 10, "bold"))
        style.configure("Dim.TLabel", background=THEME["bg"], foreground=THEME["text_dim"],
                       font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=THEME["bg"], foreground=THEME["text_dim"],
                       font=("Segoe UI", 9))
        style.configure("Accent.Horizontal.TScale", background=THEME["bg"],
                       troughcolor=THEME["border"], sliderthickness=16)
        style.configure("Dark.TRadiobutton", background=THEME["bg"],
                       foreground=THEME["text"], font=("Segoe UI", 10))
        style.map("Dark.TRadiobutton",
                 background=[("active", THEME["bg"])],
                 foreground=[("active", THEME["accent"])])

    def _create_section(self, parent, title):
        frame = ttk.Frame(parent, style="Dark.TFrame")
        frame.pack(fill="x", padx=15, pady=(12, 4))

        header = ttk.Frame(frame, style="Dark.TFrame")
        header.pack(fill="x")

        ttk.Label(header, text=title, style="Header.TLabel").pack(side="left")

        sep = ttk.Frame(header, height=1)
        sep.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=8)
        sep.configure(style="Dark.TFrame")

        canvas = tk.Canvas(sep, height=1, bg=THEME["border"], highlightthickness=0)
        canvas.pack(fill="x")

        content = ttk.Frame(frame, style="Dark.TFrame")
        content.pack(fill="x", pady=(4, 0))

        return content

    def _create_button(self, parent, text, command, accent=False):
        bg = THEME["accent"] if accent else THEME["bg_secondary"]
        fg = THEME["bg"] if accent else THEME["text"]

        btn = tk.Button(parent, text=text, command=command,
                       bg=bg, fg=fg, activebackground=THEME["accent_dim"],
                       activeforeground=fg, relief="flat", font=("Segoe UI", 10),
                       cursor="hand2", padx=20, pady=8)

        def on_enter(e):
            btn.configure(bg=THEME["accent_dim"] if accent else "#252525")
        def on_leave(e):
            btn.configure(bg=bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

        return btn

    def _create_colour_btn(self, parent, name, command):
        """Create a colour preset button with actual colour."""
        xy = COLOURS[name]
        r, g, b = xy_to_rgb(*xy, brightness=0.9)
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        display = name.replace("_", " ").title()

        frame = tk.Frame(parent, bg=THEME["bg_secondary"], padx=8, pady=6, cursor="hand2")

        dot = tk.Canvas(frame, width=14, height=14, bg=THEME["bg_secondary"], highlightthickness=0)
        dot.pack(side="left", padx=(0, 6))
        dot.create_oval(1, 1, 13, 13, fill=hex_color, outline="")

        label = tk.Label(frame, text=display, bg=THEME["bg_secondary"], fg=THEME["text"],
                        font=("Segoe UI", 9), cursor="hand2")
        label.pack(side="left")

        def on_click(e):
            command()
        def on_enter(e):
            frame.configure(bg=THEME["border"])
            dot.configure(bg=THEME["border"])
            label.configure(bg=THEME["border"])
        def on_leave(e):
            frame.configure(bg=THEME["bg_secondary"])
            dot.configure(bg=THEME["bg_secondary"])
            label.configure(bg=THEME["bg_secondary"])

        for widget in [frame, dot, label]:
            widget.bind("<Button-1>", on_click)
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)

        return frame

    def _create_colour_dot(self, parent, name, size=24, selected=False):
        """Create a clickable colour dot for alarm colour selection."""
        xy = COLOURS[name]
        r, g, b = xy_to_rgb(*xy, brightness=0.9)
        hex_color = f"#{r:02x}{g:02x}{b:02x}"

        canvas = tk.Canvas(parent, width=size+4, height=size+4, bg=THEME["bg"],
                          highlightthickness=0, cursor="hand2")

        def draw(sel=False):
            canvas.delete("all")
            outline = THEME["accent"] if sel else THEME["bg"]
            canvas.create_oval(2, 2, size+2, size+2, fill=hex_color, outline=outline, width=2)

        draw(selected)
        canvas._name = name
        canvas._draw = draw

        return canvas

    def _setup_ui(self):
        main = ttk.Frame(self.root, style="Dark.TFrame")
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        # Title
        title_frame = ttk.Frame(main, style="Dark.TFrame")
        title_frame.pack(fill="x", padx=15, pady=(15, 5))
        tk.Label(title_frame, text="💡 hue-ble", bg=THEME["bg"], fg=THEME["accent"],
                font=("Segoe UI", 16, "bold")).pack(side="left")

        # === CONNECTION ===
        conn = self._create_section(main, "connection")
        conn_row = ttk.Frame(conn, style="Dark.TFrame")
        conn_row.pack(fill="x")

        self.status_dot = tk.Canvas(conn_row, width=10, height=10, bg=THEME["bg"], highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 8), pady=4)
        self._draw_status(False)

        self.status_label = ttk.Label(conn_row, text="disconnected", style="Status.TLabel")
        self.status_label.pack(side="left")

        self._create_button(conn_row, "connect", self._connect).pack(side="right")

        # === POWER ===
        power = self._create_section(main, "power")
        self.power_btn = self._create_button(power, "⏻  turn on", self._toggle_power, accent=True)
        self.power_btn.pack(fill="x")

        # === BRIGHTNESS ===
        bright = self._create_section(main, "brightness")
        bright_row = ttk.Frame(bright, style="Dark.TFrame")
        bright_row.pack(fill="x")

        self.brightness_var = tk.IntVar(value=254)
        self.brightness_scale = ttk.Scale(bright_row, from_=1, to=254, orient="horizontal",
                                          variable=self.brightness_var, command=self._on_brightness,
                                          style="Accent.Horizontal.TScale")
        self.brightness_scale.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.brightness_label = ttk.Label(bright_row, text="254", style="Dark.TLabel", width=4)
        self.brightness_label.pack(side="right")

        # === COLOUR ===
        colour = self._create_section(main, "colour")

        presets_frame = ttk.Frame(colour, style="Dark.TFrame")
        presets_frame.pack(fill="x")

        # Use new colour order
        colour_order = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink", "warm_white", "cool_white"]
        row_frame = None
        for i, name in enumerate(colour_order):
            if i % 5 == 0:
                row_frame = ttk.Frame(presets_frame, style="Dark.TFrame")
                row_frame.pack(fill="x", pady=2)

            btn = self._create_colour_btn(row_frame, name, lambda n=name: self._set_preset(n))
            btn.pack(side="left", padx=2, pady=2)

        # Temperature
        temp_frame = ttk.Frame(colour, style="Dark.TFrame")
        temp_frame.pack(fill="x", pady=(15, 0))

        ttk.Label(temp_frame, text="temperature", style="Dim.TLabel").pack(anchor="w")

        temp_labels = ttk.Frame(temp_frame, style="Dark.TFrame")
        temp_labels.pack(fill="x")
        ttk.Label(temp_labels, text="cool", style="Dim.TLabel").pack(side="left")
        ttk.Label(temp_labels, text="warm", style="Dim.TLabel").pack(side="right")

        self.temp_var = tk.IntVar(value=300)
        self.temp_scale = ttk.Scale(temp_frame, from_=153, to=500, orient="horizontal",
                                    variable=self.temp_var, command=self._on_temp,
                                    style="Accent.Horizontal.TScale")
        self.temp_scale.pack(fill="x")

        # === SCHEDULE ===
        sched = self._create_section(main, "schedule")

        # Effect selection
        effect_frame = ttk.Frame(sched, style="Dark.TFrame")
        effect_frame.pack(fill="x", pady=(0, 10))

        self.effect_var = tk.StringVar(value="fade_in")

        effects_row = ttk.Frame(effect_frame, style="Dark.TFrame")
        effects_row.pack(fill="x")

        for text, value in [("☀ fade in", "fade_in"), ("🌙 fade out", "fade_out"), ("⚡ alarm", "alarm")]:
            rb = ttk.Radiobutton(effects_row, text=text, value=value,
                                variable=self.effect_var, style="Dark.TRadiobutton",
                                command=self._on_effect_change)
            rb.pack(side="left", padx=(0, 15))

        # When to run (for fade in/out)
        self.when_frame = ttk.Frame(sched, style="Dark.TFrame")
        self.when_frame.pack(fill="x", pady=(5, 0))

        self.when_var = tk.StringVar(value="time")

        time_row = ttk.Frame(self.when_frame, style="Dark.TFrame")
        time_row.pack(fill="x", pady=3)

        ttk.Radiobutton(time_row, text="at", value="time", variable=self.when_var,
                       style="Dark.TRadiobutton").pack(side="left")

        self.time_hour_var = tk.StringVar(value="07")
        self.time_min_var = tk.StringVar(value="30")

        tk.Entry(time_row, textvariable=self.time_hour_var, width=3,
                bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["accent"],
                relief="flat", font=("Segoe UI", 11), justify="center").pack(side="left", padx=(10, 0))

        ttk.Label(time_row, text=":", style="Dark.TLabel").pack(side="left")

        tk.Entry(time_row, textvariable=self.time_min_var, width=3,
                bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["accent"],
                relief="flat", font=("Segoe UI", 11), justify="center").pack(side="left")

        delay_row = ttk.Frame(self.when_frame, style="Dark.TFrame")
        delay_row.pack(fill="x", pady=3)

        ttk.Radiobutton(delay_row, text="in", value="delay", variable=self.when_var,
                       style="Dark.TRadiobutton").pack(side="left")

        self.delay_var = tk.StringVar(value="15")
        tk.Entry(delay_row, textvariable=self.delay_var, width=5,
                bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["accent"],
                relief="flat", font=("Segoe UI", 11), justify="center").pack(side="left", padx=(10, 0))

        ttk.Label(delay_row, text="minutes", style="Dim.TLabel").pack(side="left", padx=(8, 0))

        # Duration (for fade in/out only)
        self.dur_frame = ttk.Frame(sched, style="Dark.TFrame")
        self.dur_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(self.dur_frame, text="duration", style="Dim.TLabel").pack(side="left")

        self.duration_var = tk.StringVar(value="15")
        tk.Entry(self.dur_frame, textvariable=self.duration_var, width=5,
                bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["accent"],
                relief="flat", font=("Segoe UI", 11), justify="center").pack(side="left", padx=10)

        ttk.Label(self.dur_frame, text="minutes", style="Dim.TLabel").pack(side="left")

        # Alarm options (hidden by default)
        self.alarm_frame = ttk.Frame(sched, style="Dark.TFrame")

        # Alarm colour - dot buttons
        colour_label = ttk.Frame(self.alarm_frame, style="Dark.TFrame")
        colour_label.pack(fill="x", pady=(5, 5))
        ttk.Label(colour_label, text="colour", style="Dim.TLabel").pack(side="left")

        self.alarm_colour_frame = ttk.Frame(self.alarm_frame, style="Dark.TFrame")
        self.alarm_colour_frame.pack(fill="x", pady=(0, 10))

        self._alarm_dots = []
        for name in ALARM_COLOURS:
            dot = self._create_colour_dot(self.alarm_colour_frame, name, size=28,
                                         selected=(name == self._alarm_colour))
            dot.pack(side="left", padx=3)
            dot.bind("<Button-1>", lambda e, n=name: self._select_alarm_colour(n))
            self._alarm_dots.append(dot)

        # Alarm style
        style_row = ttk.Frame(self.alarm_frame, style="Dark.TFrame")
        style_row.pack(fill="x", pady=5)

        ttk.Label(style_row, text="style", style="Dim.TLabel").pack(side="left")

        self.alarm_style_var = tk.StringVar(value="flash")

        for text, value in [("flash", "flash"), ("fast", "fast"), ("breathing", "breathing")]:
            ttk.Radiobutton(style_row, text=text, value=value, variable=self.alarm_style_var,
                           style="Dark.TRadiobutton").pack(side="left", padx=(10, 5))

        # Alarm duration (for automation - 0 = manual stop)
        alarm_dur_row = ttk.Frame(self.alarm_frame, style="Dark.TFrame")
        alarm_dur_row.pack(fill="x", pady=(10, 0))

        ttk.Label(alarm_dur_row, text="auto-stop after", style="Dim.TLabel").pack(side="left")

        self.alarm_duration_var = tk.StringVar(value="0")
        tk.Entry(alarm_dur_row, textvariable=self.alarm_duration_var, width=4,
                bg=THEME["bg_input"], fg=THEME["text"], insertbackground=THEME["accent"],
                relief="flat", font=("Segoe UI", 11), justify="center").pack(side="left", padx=8)

        ttk.Label(alarm_dur_row, text="min (0 = manual)", style="Dim.TLabel").pack(side="left")

        # Buttons frame - save reference for pack ordering
        self.btn_frame = ttk.Frame(sched, style="Dark.TFrame")
        self.btn_frame.pack(fill="x", pady=(15, 0))

        self.save_btn = self._create_button(self.btn_frame, "💾  save for startup", self._save_schedule, accent=True)
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.run_btn = self._create_button(self.btn_frame, "▶  run now", self._run_now)
        self.run_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # === ROUTINE BUILDER ===
        routine = self._create_section(main, "routine (chain effects)")

        # Routine steps display
        self.routine_list_frame = ttk.Frame(routine, style="Dark.TFrame")
        self.routine_list_frame.pack(fill="x", pady=(0, 10))

        self._routine_steps = []
        self.routine_list_label = ttk.Label(self.routine_list_frame, text="no steps added",
                                            style="Dim.TLabel")
        self.routine_list_label.pack(anchor="w")

        # Routine buttons
        routine_btns = ttk.Frame(routine, style="Dark.TFrame")
        routine_btns.pack(fill="x")

        self.add_step_btn = self._create_button(routine_btns, "+ add current as step", self._add_routine_step)
        self.add_step_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.clear_routine_btn = self._create_button(routine_btns, "✕ clear", self._clear_routine)
        self.clear_routine_btn.pack(side="left", padx=(5, 5))

        self.save_routine_btn = self._create_button(routine_btns, "💾 save", self._save_routine, accent=True)
        self.save_routine_btn.pack(side="left", padx=(5, 0))

        # Cancel button (hidden)
        self.cancel_btn = self._create_button(sched, "■  stop", self._cancel_timer)

        # Status
        self.timer_status = ttk.Label(sched, text="", style="Status.TLabel")
        self.timer_status.pack(anchor="w", pady=(10, 0))

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(sched, variable=self.progress_var, maximum=100)

        # Load saved schedule
        self._load_saved_schedule()

    def _draw_status(self, connected: bool):
        self.status_dot.delete("all")
        color = THEME["accent"] if connected else THEME["error"]
        self.status_dot.create_oval(1, 1, 9, 9, fill=color, outline="")

    def _update_power_btn(self):
        text = "⏻  turn off" if self._power_state else "⏻  turn on"
        self.power_btn.configure(text=text)

    def _select_alarm_colour(self, name):
        """Select an alarm colour and update UI."""
        self._alarm_colour = name
        for dot in self._alarm_dots:
            dot._draw(dot._name == name)

    def _on_effect_change(self):
        effect = self.effect_var.get()
        if effect == "alarm":
            # Show time options, hide duration, show alarm options
            self.dur_frame.pack_forget()
            self.alarm_frame.pack_forget()
            self.when_frame.pack(fill="x", pady=(5, 0), before=self.btn_frame)
            self.alarm_frame.pack(fill="x", pady=(10, 0), before=self.btn_frame)
        else:
            # Show time and duration, hide alarm options
            self.alarm_frame.pack_forget()
            self.when_frame.pack_forget()
            self.dur_frame.pack_forget()
            self.when_frame.pack(fill="x", pady=(5, 0), before=self.btn_frame)
            self.dur_frame.pack(fill="x", pady=(10, 0), before=self.btn_frame)

    def _show_running_state(self, running: bool):
        if running:
            self.cancel_btn.pack(fill="x", pady=(10, 0))
            if self.effect_var.get() != "alarm":
                self.progress_bar.pack(fill="x", pady=(5, 0))
        else:
            self.cancel_btn.pack_forget()
            self.progress_bar.pack_forget()

    # === ACTIONS ===

    def _connect(self):
        self.status_label.configure(text="connecting...", foreground=THEME["warning"])
        self.root.update()

        try:
            self.light = self._async.run(get_light())
            self.status_label.configure(text="connected", foreground=THEME["accent"])
            self._draw_status(True)
        except Exception as e:
            msg = str(e)[:30] + "..." if len(str(e)) > 30 else str(e)
            self.status_label.configure(text=msg, foreground=THEME["error"])
            self._draw_status(False)
            self.light = None

    def _ensure_connected(self) -> bool:
        if not self.light:
            self._connect()
        return self.light is not None

    def _toggle_power(self):
        if self._ensure_connected():
            try:
                self._power_state = not self._power_state
                self._async.run(self.light.set_power(self._power_state))
                self._update_power_btn()
            except Exception:
                pass

    def _debounce(self, key, delay, func, *args):
        if key in self._debounce_ids:
            self.root.after_cancel(self._debounce_ids[key])
        self._debounce_ids[key] = self.root.after(delay, lambda: func(*args))

    def _on_brightness(self, value):
        val = int(float(value))
        self.brightness_label.configure(text=str(val))
        self._debounce("brightness", 50, self._set_brightness, val)

    def _set_brightness(self, value: int):
        if self.light:
            try:
                self._async.run(self.light.set_brightness(value))
            except Exception:
                pass

    def _on_temp(self, value):
        self._debounce("temp", 50, self._set_temp, int(float(value)))

    def _set_temp(self, value: int):
        if self.light:
            try:
                self._async.run(self.light.set_colour_temp(value))
            except Exception:
                pass

    def _set_preset(self, name: str):
        if self._ensure_connected():
            x, y = COLOURS[name]
            try:
                self._async.run(self.light.set_colour_xy(x, y))
            except Exception:
                pass

    # === SCHEDULE ===

    def _get_wait_seconds(self) -> float:
        if self.when_var.get() == "time":
            try:
                hour = int(self.time_hour_var.get())
                minute = int(self.time_min_var.get())
            except ValueError:
                return -1

            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return -1

            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if target <= now:
                return 0

            return (target - now).total_seconds()
        else:
            try:
                mins = float(self.delay_var.get())
                return mins * 60
            except ValueError:
                return -1

    def _run_now(self):
        if not self._ensure_connected():
            return

        if self._timer_running:
            self.timer_status.configure(text="already running", foreground=THEME["warning"])
            return

        effect = self.effect_var.get()

        # Get wait time (applies to all effects)
        wait_seconds = self._get_wait_seconds()
        if wait_seconds < 0:
            self.timer_status.configure(text="invalid time", foreground=THEME["error"])
            return

        # For alarm - schedule with time but no duration
        if effect == "alarm":
            self._timer_cancel = False
            self._timer_running = True
            self._show_running_state(True)

            async def run_alarm():
                try:
                    # Wait until scheduled time
                    if wait_seconds > 0:
                        end_wait = datetime.now() + timedelta(seconds=wait_seconds)
                        while datetime.now() < end_wait:
                            if self._timer_cancel:
                                self.root.after(0, self._on_timer_done)
                                return
                            remaining = (end_wait - datetime.now()).total_seconds()
                            mins, secs = divmod(int(remaining), 60)
                            hours, mins = divmod(mins, 60)
                            if hours > 0:
                                time_str = f"{hours}h {mins}m"
                            else:
                                time_str = f"{mins}m {secs}s"
                            self.root.after(0, lambda t=time_str:
                                           self.timer_status.configure(
                                               text=f"alarm starts in {t}",
                                               foreground=THEME["accent"]))
                            await asyncio.sleep(1)

                    if self._timer_cancel:
                        self.root.after(0, self._on_timer_done)
                        return

                    self.root.after(0, lambda: self.timer_status.configure(
                        text="alarm running... click stop to end",
                        foreground=THEME["warning"]))

                    xy = COLOURS[self._alarm_colour]
                    style = self.alarm_style_var.get()

                    def cancel_check():
                        return self._timer_cancel

                    await alarm(self.light, xy, style, cancel_check)

                    self.root.after(0, lambda: setattr(self, '_power_state', True) or self._update_power_btn())
                    self.root.after(0, lambda: self.timer_status.configure(
                        text="stopped", foreground=THEME["text_dim"]))
                except Exception as e:
                    self.root.after(0, lambda: self.timer_status.configure(
                        text=f"error: {e}", foreground=THEME["error"]))
                finally:
                    self.root.after(0, self._on_timer_done)

            # Show initial status
            if wait_seconds > 0:
                if self.when_var.get() == "time":
                    time_str = f"{self.time_hour_var.get()}:{self.time_min_var.get()}"
                    self.timer_status.configure(text=f"alarm scheduled for {time_str}",
                                               foreground=THEME["accent"])
                else:
                    self.timer_status.configure(text=f"alarm in {self.delay_var.get()} min",
                                               foreground=THEME["accent"])
            else:
                self.timer_status.configure(text="alarm running... click stop to end",
                                           foreground=THEME["warning"])

            self._async.run_async(run_alarm())
            return

        # For fade in/out, also need duration
        try:
            duration = float(self.duration_var.get())
            if duration <= 0:
                raise ValueError()
        except ValueError:
            self.timer_status.configure(text="invalid duration", foreground=THEME["error"])
            return

        self._timer_cancel = False
        self._timer_running = True
        effect_names = {"fade_in": "fade in", "fade_out": "fade out"}

        self.progress_var.set(0)
        self._show_running_state(True)

        async def run_effect():
            try:
                if wait_seconds > 0:
                    end_wait = datetime.now() + timedelta(seconds=wait_seconds)
                    while datetime.now() < end_wait:
                        if self._timer_cancel:
                            self.root.after(0, self._on_timer_done)
                            return
                        remaining = (end_wait - datetime.now()).total_seconds()
                        mins, secs = divmod(int(remaining), 60)
                        hours, mins = divmod(mins, 60)
                        if hours > 0:
                            time_str = f"{hours}h {mins}m"
                        else:
                            time_str = f"{mins}m {secs}s"
                        self.root.after(0, lambda t=time_str:
                                       self.timer_status.configure(
                                           text=f"starting {effect_names[effect]} in {t}",
                                           foreground=THEME["accent"]))
                        await asyncio.sleep(1)

                if self._timer_cancel:
                    self.root.after(0, self._on_timer_done)
                    return

                self.root.after(0, lambda: self.timer_status.configure(
                    text=f"running {effect_names[effect]}...", foreground=THEME["accent"]))

                def progress_cb(p):
                    self.root.after(0, lambda: self.progress_var.set(p * 100))

                def cancel_check():
                    return self._timer_cancel

                if effect == "fade_in":
                    result = await fade_in(self.light, duration, cancel_check, progress_cb)
                    if result:
                        self.root.after(0, lambda: setattr(self, '_power_state', True) or self._update_power_btn())
                else:
                    result = await fade_out(self.light, duration, cancel_check, progress_cb)
                    if result:
                        self.root.after(0, lambda: setattr(self, '_power_state', False) or self._update_power_btn())

                if not self._timer_cancel:
                    self.root.after(0, lambda: self.timer_status.configure(
                        text="complete ✓", foreground=THEME["accent"]))

            except Exception as e:
                self.root.after(0, lambda: self.timer_status.configure(
                    text=f"error: {e}", foreground=THEME["error"]))
            finally:
                self.root.after(0, self._on_timer_done)

        self._async.run_async(run_effect())

    def _on_timer_done(self):
        self._timer_running = False
        self._show_running_state(False)

    def _cancel_timer(self):
        self._timer_cancel = True
        self.timer_status.configure(text="stopped", foreground=THEME["text_dim"])

    def _save_schedule(self):
        try:
            hour = int(self.time_hour_var.get())
            minute = int(self.time_min_var.get())
            duration = float(self.duration_var.get()) if self.effect_var.get() != "alarm" else 0
            delay = float(self.delay_var.get()) if self.when_var.get() == "delay" else 0
            alarm_duration = float(self.alarm_duration_var.get()) if self.effect_var.get() == "alarm" else 0
        except ValueError:
            self.timer_status.configure(text="invalid values", foreground=THEME["error"])
            return

        effect = self.effect_var.get()
        colour = self._alarm_colour
        alarm_style = self.alarm_style_var.get()
        use_time = self.when_var.get() == "time"

        save_schedule(hour, minute, effect, duration, colour, alarm_style, use_time, delay, alarm_duration)

        if effect == "alarm":
            dur_str = f" for {int(alarm_duration)}min" if alarm_duration > 0 else ""
            self.timer_status.configure(text=f"saved ✓ alarm ({colour}){dur_str}",
                                       foreground=THEME["accent"])
        else:
            if use_time:
                time_str = f"{hour:02d}:{minute:02d}"
            else:
                time_str = f"in {delay} min"
            effect_names = {"fade_in": "fade in", "fade_out": "fade out"}
            self.timer_status.configure(text=f"saved ✓ {effect_names[effect]} {time_str}",
                                       foreground=THEME["accent"])

    def _load_saved_schedule(self):
        config = load_schedule()
        if config:
            # Check if it's a routine
            if "routine" in config:
                self._routine_steps = config["routine"]
                self._update_routine_display()
                return

            self.time_hour_var.set(f"{config.get('hour', 7):02d}")
            self.time_min_var.set(f"{config.get('minute', 30):02d}")
            self.effect_var.set(config.get('effect', 'fade_in'))
            self.duration_var.set(str(config.get('duration', 15)))
            self._alarm_colour = config.get('colour', 'red')
            self.alarm_style_var.set(config.get('alarm_style', 'flash'))
            self.when_var.set("time" if config.get('use_time', True) else "delay")
            self.delay_var.set(str(config.get('delay_mins', 15)))
            self.alarm_duration_var.set(str(config.get('alarm_duration', 0)))

            # Update alarm colour dots
            for dot in self._alarm_dots:
                dot._draw(dot._name == self._alarm_colour)

            self._on_effect_change()

    # === ROUTINE BUILDER ===

    def _get_current_step(self) -> dict:
        """Build a step dict from current UI settings."""
        effect = self.effect_var.get()
        use_time = self.when_var.get() == "time"

        step = {
            "effect": effect,
            "use_time": use_time,
        }

        if use_time:
            step["hour"] = int(self.time_hour_var.get())
            step["minute"] = int(self.time_min_var.get())
        else:
            step["delay_mins"] = float(self.delay_var.get())

        if effect == "alarm":
            step["colour"] = self._alarm_colour
            step["alarm_style"] = self.alarm_style_var.get()
            step["alarm_duration"] = float(self.alarm_duration_var.get())
        else:
            step["duration"] = float(self.duration_var.get())

        return step

    def _format_step(self, step: dict) -> str:
        """Format a step for display."""
        effect = step["effect"]
        effect_icons = {"fade_in": "☀", "fade_out": "🌙", "alarm": "⚡"}
        effect_names = {"fade_in": "fade in", "fade_out": "fade out", "alarm": "alarm"}

        if step.get("use_time", True):
            time_str = f"{step.get('hour', 0):02d}:{step.get('minute', 0):02d}"
        else:
            time_str = f"in {step.get('delay_mins', 0):.0f}m"

        if effect == "alarm":
            dur = step.get("alarm_duration", 0)
            dur_str = f" ({dur:.0f}min)" if dur > 0 else ""
            return f"{effect_icons[effect]} {time_str}: {step.get('colour', 'red')} alarm{dur_str}"
        else:
            return f"{effect_icons[effect]} {time_str}: {effect_names[effect]} ({step.get('duration', 15):.0f}min)"

    def _update_routine_display(self):
        """Update the routine list display."""
        if not self._routine_steps:
            self.routine_list_label.configure(text="no steps added")
        else:
            lines = [f"{i+1}. {self._format_step(s)}" for i, s in enumerate(self._routine_steps)]
            self.routine_list_label.configure(text="\n".join(lines))

    def _add_routine_step(self):
        """Add current settings as a routine step."""
        try:
            step = self._get_current_step()
            self._routine_steps.append(step)
            self._update_routine_display()
            self.timer_status.configure(text=f"added step {len(self._routine_steps)}",
                                       foreground=THEME["accent"])
        except ValueError:
            self.timer_status.configure(text="invalid values", foreground=THEME["error"])

    def _clear_routine(self):
        """Clear all routine steps."""
        self._routine_steps = []
        self._update_routine_display()
        self.timer_status.configure(text="routine cleared", foreground=THEME["text_dim"])

    def _save_routine(self):
        """Save the routine to config file."""
        if not self._routine_steps:
            self.timer_status.configure(text="no steps to save", foreground=THEME["error"])
            return

        save_routine(self._routine_steps)
        self.timer_status.configure(
            text=f"saved routine with {len(self._routine_steps)} step(s) ✓",
            foreground=THEME["accent"])

    def run(self):
        self.root.mainloop()


def main():
    app = HueControllerGUI()
    app.run()


if __name__ == "__main__":
    main()