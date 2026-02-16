from __future__ import annotations

import argparse
import time
from typing import Iterable

from scryfall_thermal.hardware import EncoderSelector


def _parse_pin_list(raw: str, expected: int) -> tuple[int, ...]:
    cleaned = [part.strip() for part in raw.split(",") if part.strip()]
    pins = tuple(int(part) for part in cleaned)
    if len(pins) != expected:
        raise ValueError(f"Expected {expected} pins, got {len(pins)}")
    return pins


class EncoderLoggerDisplay:
    def __init__(self, show_timestamp: bool) -> None:
        self._show_timestamp = show_timestamp
        self._last_value: int | None = None

    def set_value(self, value: int) -> None:
        if value == self._last_value:
            return
        self._last_value = value
        prefix = ""
        if self._show_timestamp:
            prefix = time.strftime("%H:%M:%S ")
        print(f"{prefix}encoder value: {value}", flush=True)


def _on_select(value: int) -> None:
    print(f"button pressed at value: {value}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test rotary encoder input over SSH.")
    parser.add_argument(
        "--encoder-pins",
        default="17,18,27",
        help="GPIO pins for encoder A,B,SW in BCM order (default: 17,18,27).",
    )
    parser.add_argument("--min", dest="min_value", type=int, default=0, help="Minimum value.")
    parser.add_argument("--max", dest="max_value", type=int, default=9, help="Maximum value.")
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Prefix events with a HH:MM:SS timestamp.",
    )
    args = parser.parse_args()

    if args.max_value < args.min_value:
        raise ValueError("--max must be >= --min")

    encoder_pins = _parse_pin_list(args.encoder_pins, expected=3)
    display = EncoderLoggerDisplay(show_timestamp=args.timestamp)

    selector = EncoderSelector(
        encoder_pins=encoder_pins,
        min_value=args.min_value,
        max_value=args.max_value,
        on_select=_on_select,
        display=display,
    )

    print(
        "Encoder test running. Rotate to see value changes, press to log a select. Ctrl+C to exit.",
        flush=True,
    )
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        selector.close()


if __name__ == "__main__":
    raise SystemExit(main())
