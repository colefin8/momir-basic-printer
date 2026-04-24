from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs

from PIL import Image


@dataclass
class PrinterSpec:
    kind: str
    host: Optional[str] = None
    port: Optional[int] = None
    vid: Optional[int] = None
    pid: Optional[int] = None
    interface: Optional[int] = None
    in_ep: Optional[int] = None
    out_ep: Optional[int] = None


def _parse_int(value: str, field_name: str) -> int:
    if value == "":
        raise ValueError(f"USB {field_name} must not be empty")
    try:
        return int(value, 0)
    except ValueError as exc:
        raise ValueError(f"USB {field_name} must be an int (e.g. 0 or 0x02)") from exc


def _get_query_int(params: dict[str, list[str]], keys: tuple[str, ...], field_name: str) -> Optional[int]:
    for key in keys:
        values = params.get(key)
        if values:
            return _parse_int(values[0], field_name)
    return None


def parse_printer_spec(raw: Optional[str]) -> Optional[PrinterSpec]:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("usb:"):
        base, _, query = raw.partition("?")
        parts = base.split(":", 2)
        if len(parts) != 3:
            raise ValueError("USB printer format must be usb:0xVID:0xPID[?intf=0&out=0x02&in=0x81]")
        vid = int(parts[1], 16)
        pid = int(parts[2], 16)
        params = parse_qs(query, keep_blank_values=True)
        interface = _get_query_int(params, ("intf", "interface"), "interface")
        out_ep = _get_query_int(params, ("out", "out_ep"), "out endpoint")
        in_ep = _get_query_int(params, ("in", "in_ep"), "in endpoint")
        return PrinterSpec(kind="usb", vid=vid, pid=pid, interface=interface, in_ep=in_ep, out_ep=out_ep)
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
        usb_kwargs: dict[str, int] = {}
        if printer.interface is not None:
            usb_kwargs["interface"] = printer.interface
        if printer.out_ep is not None:
            usb_kwargs["out_ep"] = printer.out_ep
        if printer.in_ep is not None:
            usb_kwargs["in_ep"] = printer.in_ep
        device = Usb(printer.vid, printer.pid, **usb_kwargs)
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
