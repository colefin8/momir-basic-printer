from __future__ import annotations

import argparse
from pathlib import Path

from .input import get_mana_value_cli
from .print import parse_printer_spec, print_image
from .render import render_receipt
from .scryfall import fetch_random_creature


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a random Scryfall creature by mana value.")
    parser.add_argument("--mv", type=int, help="Mana value (whole number >= 0)")
    parser.add_argument("--width", type=int, default=384, help="Receipt width in pixels (default: 384)")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Save output PNG instead of printing")
    parser.add_argument("--output", type=str, default="output.png", help="PNG path for dry-run")
    parser.add_argument("--printer", type=str, help="Printer spec: usb:VID:PID or net:HOST:PORT")
    parser.add_argument("--hardware", action="store_true", help="Use rotary encoder + 7-seg display")
    parser.add_argument("--min-mv", type=int, default=0, help="Minimum mana value for hardware mode")
    parser.add_argument("--max-mv", type=int, default=99, help="Maximum mana value for hardware mode")
    parser.add_argument("--encoder-a", type=int, default=17, help="GPIO pin for encoder A/CLK")
    parser.add_argument("--encoder-b", type=int, default=18, help="GPIO pin for encoder B/DT")
    parser.add_argument("--encoder-sw", type=int, default=27, help="GPIO pin for encoder SW")
    parser.add_argument(
        "--seg-pins",
        type=str,
        default="5,6,13,19,26,12,16,20",
        help="GPIO pins for segments a,b,c,d,e,f,g,dp",
    )
    parser.add_argument("--digit-pins", type=str, default="21,25", help="GPIO pins for digit commons")
    parser.add_argument("--refresh-hz", type=float, default=150.0, help="Display refresh rate in Hz")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.hardware:
        from .hardware import run_hardware_interface

        return run_hardware_interface(
            printer_spec=args.printer,
            width_px=args.width,
            timeout=args.timeout,
            dry_run=args.dry_run,
            output_path=args.output,
            min_mv=args.min_mv,
            max_mv=args.max_mv,
            encoder_pins=(args.encoder_a, args.encoder_b, args.encoder_sw),
            segment_pins=args.seg_pins,
            digit_pins=args.digit_pins,
            refresh_hz=args.refresh_hz,
        )

    if args.mv is None:
        mana_value = get_mana_value_cli()
    else:
        if args.mv < 0:
            raise ValueError("Mana value must be >= 0")
        mana_value = args.mv

    card = fetch_random_creature(mana_value, timeout=args.timeout)
    image = render_receipt(card, width_px=args.width)

    if args.dry_run or not args.printer:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        print(f"Saved receipt image to {output_path}")
        return 0

    printer = parse_printer_spec(args.printer)
    if printer is None:
        raise ValueError("Printer spec is required unless --dry-run is used")
    print_image(image, printer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
