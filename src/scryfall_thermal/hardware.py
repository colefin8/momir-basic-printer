from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .print import parse_printer_spec, print_image
from .render import render_receipt
from .scryfall import fetch_random_creature


@dataclass(frozen=True)
class PinConfig:
    segment_pins: tuple[int, ...]
    digit_pins: tuple[int, ...]
    encoder_pins: tuple[int, int, int]


_SEGMENT_MAP: dict[int, tuple[int, ...]] = {
    0: (1, 1, 1, 1, 1, 1, 0, 0),
    1: (0, 1, 1, 0, 0, 0, 0, 0),
    2: (1, 1, 0, 1, 1, 0, 1, 0),
    3: (1, 1, 1, 1, 0, 0, 1, 0),
    4: (0, 1, 1, 0, 0, 1, 1, 0),
    5: (1, 0, 1, 1, 0, 1, 1, 0),
    6: (1, 0, 1, 1, 1, 1, 1, 0),
    7: (1, 1, 1, 0, 0, 0, 0, 0),
    8: (1, 1, 1, 1, 1, 1, 1, 0),
    9: (1, 1, 1, 1, 0, 1, 1, 0),
}


def _parse_pin_list(raw: str) -> tuple[int, ...]:
    cleaned = [part.strip() for part in raw.split(",") if part.strip()]
    return tuple(int(part) for part in cleaned)


class SevenSegmentDisplay:
    def __init__(
        self,
        segment_pins: Sequence[int],
        digit_pins: Sequence[int],
        refresh_hz: float = 150.0,
        digit_active_high: bool = True,
        leading_zero: bool = False,
    ) -> None:
        from gpiozero import DigitalOutputDevice

        self._segments = [DigitalOutputDevice(pin, active_high=True, initial_value=False) for pin in segment_pins]
        self._digits = [
            DigitalOutputDevice(pin, active_high=digit_active_high, initial_value=False) for pin in digit_pins
        ]
        self._refresh_hz = refresh_hz
        self._leading_zero = leading_zero
        self._lock = threading.Lock()
        self._value = 0
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._refresh_loop, daemon=True)

    def start(self) -> None:
        self._stop_event.clear()
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self._set_all(False)
        for device in self._segments + self._digits:
            device.close()

    def set_value(self, value: int) -> None:
        with self._lock:
            self._value = max(0, min(99, value))

    def _format_digits(self, value: int) -> tuple[int | None, int]:
        tens = value // 10
        ones = value % 10
        if tens == 0 and not self._leading_zero:
            return None, ones
        return tens, ones

    def _set_all(self, state: bool) -> None:
        for digit in self._digits:
            digit.value = False
        for segment in self._segments:
            segment.value = state

    def _set_segments(self, segments: Iterable[int]) -> None:
        values = list(segments)
        for index, segment in enumerate(self._segments):
            value = values[index] if index < len(values) else 0
            segment.value = bool(value)

    def _refresh_loop(self) -> None:
        digits_count = len(self._digits)
        delay = 1.0 / max(1.0, self._refresh_hz * digits_count)
        while not self._stop_event.is_set():
            with self._lock:
                value = self._value
            tens, ones = self._format_digits(value)
            patterns = [tens, ones]
            for index, digit_value in enumerate(patterns):
                for digit in self._digits:
                    digit.value = False
                if digit_value is None:
                    self._set_segments((0,) * len(self._segments))
                else:
                    self._set_segments(_SEGMENT_MAP.get(digit_value, (0,) * len(self._segments)))
                self._digits[index].value = True
                time.sleep(delay)


class EncoderSelector:
    def __init__(
        self,
        encoder_pins: tuple[int, int, int],
        min_value: int,
        max_value: int,
        on_select: Callable[[int], None],
        display: SevenSegmentDisplay,
    ) -> None:
        from gpiozero import Button, RotaryEncoder

        self._min_value = min_value
        self._max_value = max_value
        self._on_select = on_select
        self._display = display
        self._lock = threading.Lock()
        self._value = min_value
        self._busy = threading.Event()
        self.encoder = RotaryEncoder(a=encoder_pins[0], b=encoder_pins[1], max_steps=0, wrap=False)
        self.encoder.when_rotated_clockwise = self._increment
        self.encoder.when_rotated_counter_clockwise = self._decrement
        self.button = Button(encoder_pins[2], pull_up=True, bounce_time=0.05)
        self.button.when_pressed = self._handle_press
        self._display.set_value(self._value)

    def close(self) -> None:
        self.encoder.close()
        self.button.close()

    def _increment(self) -> None:
        self._update_value(1)

    def _decrement(self) -> None:
        self._update_value(-1)

    def _update_value(self, delta: int) -> None:
        with self._lock:
            value = max(self._min_value, min(self._max_value, self._value + delta))
            self._value = value
        self._display.set_value(value)

    def _handle_press(self) -> None:
        if self._busy.is_set():
            return
        self._busy.set()
        with self._lock:
            value = self._value
        thread = threading.Thread(target=self._run_action, args=(value,), daemon=True)
        thread.start()

    def _run_action(self, value: int) -> None:
        try:
            self._on_select(value)
        finally:
            self._busy.clear()


def run_hardware_interface(
    printer_spec: str | None,
    width_px: int,
    timeout: float,
    dry_run: bool,
    output_path: str,
    min_mv: int,
    max_mv: int,
    encoder_pins: tuple[int, int, int],
    segment_pins: str,
    digit_pins: str,
    refresh_hz: float,
) -> int:
    if min_mv < 0 or max_mv < min_mv:
        raise ValueError("Invalid min/max mana value range")

    pins = PinConfig(
        segment_pins=_parse_pin_list(segment_pins),
        digit_pins=_parse_pin_list(digit_pins),
        encoder_pins=encoder_pins,
    )

    if len(pins.segment_pins) != 8:
        raise ValueError("Expected 8 segment pins in order: a,b,c,d,e,f,g,dp")
    if len(pins.digit_pins) != 2:
        raise ValueError("Expected 2 digit pins for a 2-digit display")

    printer = parse_printer_spec(printer_spec) if printer_spec else None

    def handle_select(mana_value: int) -> None:
        card = fetch_random_creature(mana_value, timeout=timeout)
        image = render_receipt(card, width_px=width_px)
        if dry_run or not printer:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_file)
            print(f"Saved receipt image to {output_file}")
            return
        print_image(image, printer)

    display = SevenSegmentDisplay(
        pins.segment_pins,
        pins.digit_pins,
        refresh_hz=refresh_hz,
        digit_active_high=True,
        leading_zero=False,
    )
    selector = EncoderSelector(
        pins.encoder_pins,
        min_value=min_mv,
        max_value=max_mv,
        on_select=handle_select,
        display=display,
    )

    display.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        selector.close()
        display.stop()
