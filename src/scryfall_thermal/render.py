from __future__ import annotations

import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import requests
from PIL import Image, ImageDraw, ImageFont

from .scryfall import CardInfo
from .symbols import load_symbol_map


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    if hasattr(draw, "textlength"):
        return int(draw.textlength(text, font=font))
    box = font.getbbox(text)
    return box[2] - box[0]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _text_width(draw, trial, font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _line_height(font: ImageFont.ImageFont) -> int:
    box = font.getbbox("Ag")
    return (box[3] - box[1]) + 2


def _load_text_font(size: int) -> ImageFont.ImageFont:
    env_path = os.getenv("SCRYFALL_TEXT_FONT")
    candidates = [env_path] if env_path else []
    candidates.extend(
        [
            "DejaVuSans.ttf",
            "arial.ttf",
            "segoeui.ttf",
        ]
    )
    for path in candidates:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _tokenize_mana_cost(mana_cost: str) -> list[str]:
    tokens = re.findall(r"\{([^}]+)\}", mana_cost)
    if tokens:
        return tokens
    cleaned = mana_cost.replace("{", "").replace("}", "").strip()
    return cleaned.split() if cleaned else []


@dataclass
class TextLine:
    text: str
    font: ImageFont.ImageFont


@dataclass
class SymbolLine:
    symbols: list[Image.Image]
    height: int


Line = Union[TextLine, SymbolLine]


class SymbolRenderer:
    def __init__(self, symbol_map: dict[str, Path], size_px: int, spacing: int) -> None:
        self.symbol_map = symbol_map
        self.size_px = size_px
        self.spacing = spacing
        self.cache: dict[str, Image.Image] = {}

    def symbol_for_token(self, token: str) -> Optional[Image.Image]:
        key = f"{{{token}}}"
        source_path = self.symbol_map.get(key)
        if source_path is None:
            return None
        if key in self.cache:
            return self.cache[key]
        with Image.open(source_path) as source:
            img = source.convert("RGBA")
        if img.height > 0:
            ratio = self.size_px / img.height
            width = max(1, int(img.width * ratio))
            img = img.resize((width, self.size_px), Image.BICUBIC)
        self.cache[key] = img
        return img

    def layout_rows(self, symbols: list[Image.Image], max_width: int) -> list[list[Image.Image]]:
        rows: list[list[Image.Image]] = []
        current: list[Image.Image] = []
        width = 0
        for symbol in symbols:
            symbol_width = symbol.width
            next_width = symbol_width if not current else width + self.spacing + symbol_width
            if current and next_width > max_width:
                rows.append(current)
                current = [symbol]
                width = symbol_width
            else:
                current.append(symbol)
                width = next_width
        if current:
            rows.append(current)
        return rows


def _build_text_lines(
    draw: ImageDraw.ImageDraw,
    card: CardInfo,
    font: ImageFont.ImageFont,
    symbol_renderer: Optional[SymbolRenderer],
    max_width: int,
) -> list[Line]:
    lines: list[Line] = []
    lines.extend(TextLine(line, font) for line in _wrap_text(draw, card.name, font, max_width))

    if card.mana_cost:
        tokens = _tokenize_mana_cost(card.mana_cost)
        if symbol_renderer and tokens:
            symbols: list[Image.Image] = []
            missing = False
            for token in tokens:
                symbol = symbol_renderer.symbol_for_token(token)
                if symbol is None:
                    missing = True
                    break
                symbols.append(symbol)
            if not missing and symbols:
                for row in symbol_renderer.layout_rows(symbols, max_width):
                    lines.append(SymbolLine(row, symbol_renderer.size_px))
            else:
                lines.extend(TextLine(line, font) for line in _wrap_text(draw, card.mana_cost, font, max_width))
        else:
            lines.extend(TextLine(line, font) for line in _wrap_text(draw, card.mana_cost, font, max_width))
    else:
        mv_line = f"MV {card.mana_value}"
        lines.extend(TextLine(line, font) for line in _wrap_text(draw, mv_line, font, max_width))

    if card.type_line:
        lines.extend(TextLine(line, font) for line in _wrap_text(draw, card.type_line, font, max_width))
    if card.oracle_text:
        lines.append(TextLine("", font))
        for paragraph in card.oracle_text.split("\n"):
            lines.extend(TextLine(line, font) for line in _wrap_text(draw, paragraph, font, max_width))
    return lines


def _download_image(url: str, timeout: float = 10.0) -> Image.Image:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content))


def render_receipt(card: CardInfo, width_px: int = 384) -> Image.Image:
    margin = 10
    font = _load_text_font(size=28)
    symbol_map: dict[str, Path] = {}
    try:
        symbol_map = load_symbol_map()
    except Exception:
        symbol_map = {}
    symbol_renderer = None
    if symbol_map:
        symbol_renderer = SymbolRenderer(symbol_map, size_px=max(16, _line_height(font) + 2), spacing=2)

    text_img = Image.new("L", (width_px, 10), 255)
    draw = ImageDraw.Draw(text_img)

    max_width = width_px - (margin * 2)
    lines = _build_text_lines(draw, card, font, symbol_renderer, max_width)

    text_height = margin * 2
    for line in lines:
        if isinstance(line, TextLine):
            text_height += _line_height(line.font)
        else:
            text_height += line.height
    text_img = Image.new("L", (width_px, text_height), 255)
    draw = ImageDraw.Draw(text_img)

    y = margin
    for line in lines:
        if isinstance(line, TextLine):
            draw.text((margin, y), line.text, font=line.font, fill=0)
            y += _line_height(line.font)
        else:
            x = margin
            for symbol in line.symbols:
                if symbol.mode in ("RGBA", "LA"):
                    text_img.paste(symbol.convert("L"), (x, y), symbol.split()[-1])
                else:
                    text_img.paste(symbol.convert("L"), (x, y))
                x += symbol.width + (symbol_renderer.spacing if symbol_renderer else 2)
            y += line.height

    image_part = None
    if card.image_url:
        try:
            img = _download_image(card.image_url)
            img = img.convert("L")
            ratio = width_px / img.width
            new_height = max(1, int(img.height * ratio))
            image_part = img.resize((width_px, new_height), Image.BICUBIC)
        except Exception:
            image_part = None

    if image_part:
        combined = Image.new("L", (width_px, image_part.height + text_height + margin), 255)
        combined.paste(image_part, (0, 0))
        combined.paste(text_img, (0, image_part.height + margin))
    else:
        combined = text_img

    return combined.convert("1")
