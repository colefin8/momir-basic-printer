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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

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
