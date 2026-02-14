from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable
from urllib.parse import urlparse

import requests

SYMBOLS_URL = "https://api.scryfall.com/symbology"
SYMBOLS_INDEX = "symbols.json"
BUNDLED_SYMBOLOGY = Path(__file__).with_name("assets") / "symbology.json"


def _default_cache_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "scryfall-thermal" / "symbols"
    return Path.home() / ".cache" / "scryfall-thermal" / "symbols"


def get_symbols_dir() -> Path:
    override = os.getenv("SCRYFALL_SYMBOLS_DIR")
    return Path(override) if override else _default_cache_dir()


def _load_index(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _write_index(path: Path, data: Dict[str, str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def _iter_entries(payload: object) -> Iterable[dict]:
    if isinstance(payload, dict):
        entries = payload.get("data", [])
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []
    for entry in entries:
        if isinstance(entry, dict):
            yield entry


def _load_entries_from_api(timeout: float) -> list[dict]:
    resp = requests.get(SYMBOLS_URL, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    return list(_iter_entries(payload))


def _load_entries_from_file(path: Path) -> list[dict]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []
    return list(_iter_entries(payload))


def _download_symbols(cache_dir: Path, entries: Iterable[dict], timeout: float = 10.0) -> Dict[str, Path]:
    try:
        import cairosvg
    except Exception as exc:  # pragma: no cover - optional dependency safety
        raise RuntimeError("cairosvg is required to rasterize Scryfall SVG symbols") from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    index: Dict[str, str] = {}

    for entry in entries:
        symbol = entry.get("symbol")
        svg_uri = entry.get("svg_uri")
        if not symbol or not svg_uri:
            continue
        path_part = urlparse(svg_uri).path
        stem = Path(path_part).stem
        filename = f"{stem}.png"
        index[symbol] = filename

        out_path = cache_dir / filename
        if out_path.exists():
            continue

        svg_resp = requests.get(svg_uri, timeout=timeout)
        svg_resp.raise_for_status()
        png_bytes = cairosvg.svg2png(bytestring=svg_resp.content)
        out_path.write_bytes(png_bytes)

    _write_index(cache_dir / SYMBOLS_INDEX, index)
    return {symbol: cache_dir / filename for symbol, filename in index.items()}


def load_symbol_map(timeout: float = 10.0) -> Dict[str, Path]:
    cache_dir = get_symbols_dir()
    index_path = cache_dir / SYMBOLS_INDEX

    if not index_path.exists():
        bundled_entries = _load_entries_from_file(BUNDLED_SYMBOLOGY) if BUNDLED_SYMBOLOGY.exists() else []
        if bundled_entries:
            return _download_symbols(cache_dir, bundled_entries, timeout=timeout)
        api_entries = _load_entries_from_api(timeout)
        return _download_symbols(cache_dir, api_entries, timeout=timeout)

    index = _load_index(index_path)
    symbol_map = {symbol: cache_dir / filename for symbol, filename in index.items()}

    missing = [path for path in symbol_map.values() if not path.exists()]
    if missing:
        bundled_entries = _load_entries_from_file(BUNDLED_SYMBOLOGY) if BUNDLED_SYMBOLOGY.exists() else []
        if bundled_entries:
            return _download_symbols(cache_dir, bundled_entries, timeout=timeout)
        api_entries = _load_entries_from_api(timeout)
        return _download_symbols(cache_dir, api_entries, timeout=timeout)

    return symbol_map
