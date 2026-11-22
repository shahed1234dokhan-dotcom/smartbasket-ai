"""תרחישים מוכנים (PRD 2.0 §5: "סימולטור").

כל פונקציה מקבלת את הסל (או את הגדרות התשלום) ומחזירה עותק חדש ששונה.
המקור לא משתנה, כך שאפשר תמיד להשוות לתרחיש הבסיס עם compare_scenarios.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from . import defaults
from .engine import Item, PaymentSettings

DAIRY_CATEGORY = "חלב-מקורר"

# הצעה בלבד: ה-PRD לא מגדיר בכמה מתייקרים מוצרי החלב (החלטה פתוחה מס' 5 ב-CLAUDE.md).
DEFAULT_DAIRY_INCREASE = 0.10
SUPPLIER_INCREASE = 0.05


def _raise_buy_price(item: Item, pct: float) -> Item:
    """מעלה את מחיר הקנייה ב-pct.

    אם מחיר הקנייה לא הוזן, ההעלאה חלה על האומדן (75% ממחיר המכירה). התוצאה נשמרת כמספר,
    ולכן במקרה הזה הפריט כבר לא יסומן "אומדן" בתרחיש החלופי.
    """
    if pct <= -1:
        raise ValueError("שיעור השינוי במחיר הקנייה חייב להיות גדול מ-100%-")
    base = item.buy_price
    if base is None:
        base = item.sell_price * defaults.ESTIMATED_BUY_PRICE_FACTOR
    return replace(item, buy_price=base * (1 + pct))


def supplier_increase(items: list[Item], pct: float = SUPPLIER_INCREASE) -> list[Item]:
    """התייקרות ספקים: כל מחירי הקנייה בסל עולים ב-pct (ברירת מחדל 5%)."""
    return [_raise_buy_price(it, pct) for it in items]


def dairy_increase(items: list[Item], pct: float = DEFAULT_DAIRY_INCREASE) -> list[Item]:
    """התייקרות מוצרי חלב: רק מחירי הקנייה בקטגוריה חלב-מקורר עולים ב-pct."""
    return [_raise_buy_price(it, pct) if it.category == DAIRY_CATEGORY else replace(it) for it in items]


def card_plan_change(
    payment: PaymentSettings,
    variable_rate: Optional[float] = None,
    fixed_fee: Optional[float] = None,
    method: Optional[str] = None,
) -> PaymentSettings:
    """שינוי מסלול אשראי: מחזירה הגדרות תשלום חדשות. ערך שלא נמסר נשאר כמו במקור.

    הערכים החדשים נקבעים בממשק, כי ה-PRD לא מגדיר מסלול חלופי מסוים.
    """
    changes = {}
    if variable_rate is not None:
        changes["variable_rate"] = variable_rate
    if fixed_fee is not None:
        changes["fixed_fee"] = fixed_fee
    if method is not None:
        changes["method"] = method
    return replace(payment, **changes)
