from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PIL import Image


@dataclass
class PrinterSpec:
    kind: str
    host: Optional[str] = None
    port: Optional[int] = None
    vid: Optional[int] = None
    pid: Optional[int] = None


def parse_printer_spec(raw: Optional[str]) -> Optional[PrinterSpec]:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("usb:"):
        parts = raw.split(":", 2)
        if len(parts) != 3:
            raise ValueError("USB printer format must be usb:0xVID:0xPID")
        vid = int(parts[1], 16)
        pid = int(parts[2], 16)
        return PrinterSpec(kind="usb", vid=vid, pid=pid)
    if raw.startswith("net:"):
        parts = raw.split(":")
        if len(parts) not in (2, 3):
            raise ValueError("Network printer format must be net:HOST[:PORT]")
        host = parts[1]
        port = int(parts[2]) if len(parts) == 3 else 9100
        return PrinterSpec(kind="net", host=host, port=port)
    raise ValueError("Printer format must start with usb: or net:")


def print_image(image: Image.Image, printer: PrinterSpec) -> None:
    if printer.kind == "usb":
        from escpos.printer import Usb

        if printer.vid is None or printer.pid is None:
            raise ValueError("USB printer requires VID and PID")
        device = Usb(printer.vid, printer.pid)
    elif printer.kind == "net":
        from escpos.printer import Network

        if printer.host is None:
            raise ValueError("Network printer requires host")
        device = Network(printer.host, printer.port or 9100)
    else:
        raise ValueError("Unsupported printer kind")

    device.image(image)
    device.cut()
    device.close()
