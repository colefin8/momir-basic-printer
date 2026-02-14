from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

SCRYFALL_RANDOM_URL = "https://api.scryfall.com/cards/random"


@dataclass
class CardInfo:
    name: str
    mana_value: int
    mana_cost: str
    type_line: str
    oracle_text: str
    image_url: Optional[str]


def fetch_random_creature(mana_value: int, timeout: float = 10.0) -> CardInfo:
    query = f"is:paper t:creature mv={mana_value}"
    resp = requests.get(SCRYFALL_RANDOM_URL, params={"q": query}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    name = data.get("name", "Unknown")
    mv = int(data.get("mana_value", mana_value))
    mana_cost = data.get("mana_cost", "")
    type_line = data.get("type_line", "")

    oracle_text = data.get("oracle_text", "")
    image_url = None

    image_uris = data.get("image_uris")
    if image_uris:
        image_url = image_uris.get("art_crop") or image_uris.get("normal") or image_uris.get("large")
    else:
        faces = data.get("card_faces", [])
        if faces:
            face = faces[0]
            image_uris = face.get("image_uris") or {}
            image_url = image_uris.get("art_crop") or image_uris.get("normal") or image_uris.get("large")

            face_texts = []
            face_costs = []
            for f in faces:
                face_name = f.get("name", "")
                face_type = f.get("type_line", "")
                face_oracle = f.get("oracle_text", "")
                face_cost = f.get("mana_cost", "")
                if face_cost:
                    face_costs.append(face_cost)
                block = "\n".join(part for part in [face_name, face_type, face_oracle] if part)
                if block:
                    face_texts.append(block)
            if face_texts:
                oracle_text = "\n\n".join(face_texts)
            if not mana_cost and face_costs:
                mana_cost = " // ".join(face_costs)

    return CardInfo(
        name=name,
        mana_value=mv,
        mana_cost=mana_cost,
        type_line=type_line,
        oracle_text=oracle_text,
        image_url=image_url,
    )
