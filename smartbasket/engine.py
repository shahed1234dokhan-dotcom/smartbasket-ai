"""מנוע החישוב של SmartBasket AI.

כל החישובים הכספיים נעשים כאן בנוסחאות קבועות (לא בידי מודל שפה).
המדד המרכזי הוא "רווח תרומתי משוער לסל" — הוא *אינו* רווח נקי של העסק:
לא נכללים שכירות, שכר, מסים או הוצאות קבועות אחרות.

מדיניות עיגול: מחשבים בערכים מלאים, ומעגלים לאגורה רק בהצגה (money()).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import defaults


def money(x: float) -> float:
    """עיגול לאגורה — לשימוש בהצגה בלבד."""
    return round(x + 0.0, 2)


# ---------- קלט ----------

@dataclass
class Item:
    """פריט בסל. buy_price ו-spoilage_rate אופציונליים — יושלמו מברירות המחדל."""
    name: str
    category: str
    quantity: float                     # Q
    sell_price: float                   # P — ₪ ליחידה, ללא מע"מ
    buy_price: Optional[float] = None   # C
    spoilage_rate: Optional[float] = None  # d, בין 0 ל-1 (לא כולל 1)


@dataclass
class PaymentSettings:
    method: str = "card"  # "card" או "cash"
    variable_rate: float = defaults.DEFAULT_VARIABLE_RATE  # r
    fixed_fee: float = defaults.DEFAULT_FIXED_FEE          # F


# ---------- פלט ----------

@dataclass
class ItemResult:
    name: str
    category: str
    quantity: float
    sell_price: float
    buy_price: float
    spoilage_rate: float
    buy_price_estimated: bool   # True אם C חושב כ-0.75×P
    adjusted_unit_cost: float   # C_adj = C / (1 - d)
    revenue: float              # Rev_i = P × Q
    naive_cost: float           # C × Q
    adjusted_cost: float        # Cost_adj_i = C_adj × Q
    margin_before_card: float   # Margin_i = Rev_i - Cost_adj_i


@dataclass
class BasketResult:
    items: list[ItemResult]
    payment_method: str
    total_revenue: float
    naive_cost: float
    naive_profit: float          # הכנסות פחות עלות קנייה, בלי פחת ועמלות
    adjusted_cost: float
    spoilage_loss: float         # עלות מתואמת פחות עלות נאיבית
    card_fee: float
    contribution: float          # רווח תרומתי משוער לסל
    margin_pct: Optional[float]  # contribution / revenue × 100; None אם אין הכנסות
    breakeven_revenue: float     # הכנסה שבה הרווח התרומתי של הסל = 0 (באותו הרכב סל)
    warnings: list[str] = field(default_factory=list)


# ---------- אימות קלט ----------

def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x  # x==x שולל NaN


def validate_item(item: Item) -> None:
    """זורקת ValueError עם הודעה בעברית אם הפריט אינו תקין."""
    name = (item.name or "").strip() if isinstance(item.name, str) else ""
    if not name:
        raise ValueError("שם הפריט חסר")
    if len(name) > defaults.MAX_NAME_LENGTH:
        raise ValueError(f"שם הפריט ארוך מ-{defaults.MAX_NAME_LENGTH} תווים")
    if item.category not in defaults.CATEGORY_SPOILAGE:
        allowed = " / ".join(defaults.CATEGORY_SPOILAGE)
        raise ValueError(f"קטגוריה לא מוכרת: '{item.category}'. אפשרויות: {allowed}")
    if not _is_number(item.quantity) or item.quantity <= 0:
        raise ValueError(f"'{name}': הכמות חייבת להיות גדולה מאפס")
    if not _is_number(item.sell_price) or item.sell_price <= 0:
        raise ValueError(f"'{name}': מחיר המכירה חייב להיות גדול מאפס")
    if item.buy_price is not None and (not _is_number(item.buy_price) or item.buy_price < 0):
        raise ValueError(f"'{name}': מחיר הקנייה אינו יכול להיות שלילי")
    if item.spoilage_rate is not None and (
        not _is_number(item.spoilage_rate) or not (0 <= item.spoilage_rate < 1)
    ):
        raise ValueError(f"'{name}': שיעור הפחת חייב להיות בין 0% ל-100% (לא כולל 100%)")


def validate_payment(payment: PaymentSettings) -> None:
    if payment.method not in ("card", "cash"):
        raise ValueError("אמצעי תשלום חייב להיות 'card' (אשראי) או 'cash' (מזומן)")
    if not _is_number(payment.variable_rate) or not (
        0 <= payment.variable_rate < defaults.MAX_VARIABLE_RATE
    ):
        raise ValueError("עמלת האשראי המשתנה חייבת להיות בין 0% ל-10% (לא כולל 10%)")
    if not _is_number(payment.fixed_fee) or payment.fixed_fee < 0:
        raise ValueError("עמלת האשראי הקבועה אינה יכולה להיות שלילית")


# ---------- חישוב ----------

def _calculate_item(item: Item) -> ItemResult:
    d = item.spoilage_rate
    if d is None:
        d = defaults.CATEGORY_SPOILAGE[item.category]
    estimated = item.buy_price is None
    c = item.sell_price * defaults.ESTIMATED_BUY_PRICE_FACTOR if estimated else item.buy_price

    c_adj = c / (1 - d)
    revenue = item.sell_price * item.quantity
    adjusted_cost = c_adj * item.quantity
    return ItemResult(
        name=item.name.strip(),
        category=item.category,
        quantity=item.quantity,
        sell_price=item.sell_price,
        buy_price=c,
        spoilage_rate=d,
        buy_price_estimated=estimated,
        adjusted_unit_cost=c_adj,
        revenue=revenue,
        naive_cost=c * item.quantity,
        adjusted_cost=adjusted_cost,
        margin_before_card=revenue - adjusted_cost,
    )


def calculate_basket(items: list[Item], payment: Optional[PaymentSettings] = None) -> BasketResult:
    """מחשבת את רווחיות הסל. זורקת ValueError על קלט לא תקין."""
    if payment is None:
        payment = PaymentSettings()
    if not items:
        raise ValueError("הסל ריק — יש להוסיף לפחות פריט אחד")
    for it in items:
        validate_item(it)
    validate_payment(payment)

    rows = [_calculate_item(it) for it in items]
    total_revenue = sum(r.revenue for r in rows)
    naive_cost = sum(r.naive_cost for r in rows)
    adjusted_cost = sum(r.adjusted_cost for r in rows)

    if payment.method == "card":
        r, f = payment.variable_rate, payment.fixed_fee
    else:
        r, f = 0.0, 0.0
    card_fee = f + r * total_revenue
    contribution = total_revenue - adjusted_cost - card_fee
    margin_pct = contribution / total_revenue * 100 if total_revenue > 0 else None
    # R - adjusted_cost - (F + r·R) = 0  =>  R = (adjusted_cost + F) / (1 - r)
    breakeven = (adjusted_cost + f) / (1 - r)

    warnings = []
    estimated = [row.name for row in rows if row.buy_price_estimated]
    if estimated:
        warnings.append("מחיר קנייה משוער (75% ממחיר המכירה) עבור: " + ", ".join(estimated))

    return BasketResult(
        items=rows,
        payment_method=payment.method,
        total_revenue=total_revenue,
        naive_cost=naive_cost,
        naive_profit=total_revenue - naive_cost,
        adjusted_cost=adjusted_cost,
        spoilage_loss=adjusted_cost - naive_cost,
        card_fee=card_fee,
        contribution=contribution,
        margin_pct=margin_pct,
        breakeven_revenue=breakeven,
        warnings=warnings,
    )


_COMPARED_FIELDS = (
    "total_revenue",
    "adjusted_cost",
    "spoilage_loss",
    "card_fee",
    "contribution",
    "breakeven_revenue",
)


def compare_scenarios(base: BasketResult, alt: BasketResult) -> dict[str, dict[str, float]]:
    """השוואת תרחיש חלופי לתרחיש הבסיס: לכל מדד — before / after / change."""
    out = {}
    for name in _COMPARED_FIELDS:
        before, after = getattr(base, name), getattr(alt, name)
        out[name] = {"before": before, "after": after, "change": after - before}
    return out
