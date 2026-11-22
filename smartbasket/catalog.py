"""מאגר המוצרים המדומים (data/products.json).

הפונקציה load_products() קוראת את הקובץ ומחזירה רשימת Item שהמנוע מקבל כמו שהיא.
שיעור הפחת לא נשמר במאגר: המנוע משלים אותו לפי הקטגוריה (defaults.CATEGORY_SPOILAGE).
"""
from __future__ import annotations

import json
from pathlib import Path

from .engine import Item

PRODUCTS_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"


def load_products(path: Path | str = PRODUCTS_PATH) -> list[Item]:
    """מחזירה את כל מוצרי המאגר, כל אחד בכמות 1."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        Item(
            name=p["name"],
            category=p["category"],
            quantity=1,
            sell_price=p["sell_price"],
            buy_price=p.get("buy_price"),
        )
        for p in data["products"]
    ]


def find_product(name: str, path: Path | str = PRODUCTS_PATH) -> Item:
    """מחזירה מוצר מהמאגר לפי שם מדויק. זורקת KeyError אם אינו קיים."""
    for item in load_products(path):
        if item.name == name:
            return item
    raise KeyError(f"המוצר '{name}' לא נמצא במאגר")
