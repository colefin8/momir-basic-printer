from __future__ import annotations


def get_mana_value_cli() -> int:
    while True:
        raw = input("Enter mana value (whole number >= 0): ").strip()
        if raw.isdigit():
            value = int(raw)
            if value >= 0:
                return value
        print("Please enter a whole number >= 0.")
