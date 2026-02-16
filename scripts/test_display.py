from __future__ import annotations

import argparse
import time

from scryfall_thermal.hardware import SevenSegmentDisplay


def _parse_pin_list(raw: str, expected: int) -> tuple[int, ...]:
    cleaned = [part.strip() for part in raw.split(",") if part.strip()]
    pins = tuple(int(part) for part in cleaned)
    if len(pins) != expected:
        raise ValueError(f"Expected {expected} pins, got {len(pins)}")
    return pins


def main() -> int:
    parser = argparse.ArgumentParser(description="Test 2-digit 7-segment display output.")
    parser.add_argument(
        "--seg-pins",
        default="5,6,13,19,26,12,16,20",
        help="Segment pins a,b,c,d,e,f,g,dp in BCM order.",
    )
    parser.add_argument(
        "--digit-pins",
        default="21,25",
        help="Digit common pins D1,D2 in BCM order.",
    )
    parser.add_argument("--refresh-hz", type=float, default=150.0, help="Refresh rate per digit.")
    parser.add_argument("--min", dest="min_value", type=int, default=0, help="Start value.")
    parser.add_argument("--max", dest="max_value", type=int, default=99, help="End value.")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between updates.")
    parser.add_argument(
        "--value",
        type=int,
        default=None,
        help="If set, show a fixed value instead of counting.",
    )
    parser.add_argument(
        "--static",
        action="store_true",
        help="Show the fixed value and wait (used with --value).",
    )
    args = parser.parse_args()

    if args.max_value < args.min_value:
        raise ValueError("--max must be >= --min")
    if args.value is not None and not (0 <= args.value <= 99):
        raise ValueError("--value must be between 0 and 99")

    segment_pins = _parse_pin_list(args.seg_pins, expected=8)
    digit_pins = _parse_pin_list(args.digit_pins, expected=2)

    display = SevenSegmentDisplay(
        segment_pins,
        digit_pins,
        refresh_hz=args.refresh_hz,
        digit_active_high=True,
        leading_zero=False,
    )

    display.start()
    try:
        if args.value is not None:
            display.set_value(args.value)
            if args.static:
                while True:
                    time.sleep(1.0)
            value = args.value
        else:
            value = args.min_value
        while True:
            display.set_value(value)
            value = args.min_value if value >= args.max_value else value + 1
            time.sleep(args.delay)
    except KeyboardInterrupt:
        return 0
    finally:
        display.stop()


if __name__ == "__main__":
    raise SystemExit(main())
