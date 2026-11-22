"""בדיקות לשלב 2: מאגר המוצרים המדומים והתרחישים המוכנים."""
from dataclasses import asdict

import pytest

from smartbasket import Item, PaymentSettings, calculate_basket, compare_scenarios, money
from smartbasket.catalog import find_product, load_products
from smartbasket.presets import card_plan_change, dairy_increase, supplier_increase
from smartbasket.defaults import CATEGORY_SPOILAGE


def prd_basket():
    """דוגמת ה-PRD (סעיף 6), כמו ב-test_engine."""
    return [
        Item("לחם אחיד", "יבש", 1, sell_price=7.00, buy_price=5.00, spoilage_rate=0.01),
        Item("חלב 3%", "חלב-מקורר", 2, sell_price=7.20, buy_price=5.40, spoilage_rate=0.10),
        Item("עגבניות 1 ק\"ג", "ירקות-פירות", 1, sell_price=9.00, buy_price=6.40, spoilage_rate=0.20),
    ]


CARD = PaymentSettings("card", 0.015, 0.50)


# ---------- מאגר המוצרים ----------

def test_catalog_has_12_valid_products_4_per_category():
    products = load_products()
    assert len(products) == 12
    for cat in CATEGORY_SPOILAGE:
        assert sum(p.category == cat for p in products) == 4
    calculate_basket(products, CARD)  # כל המוצרים עוברים אימות קלט


def test_catalog_builds_prd_basket_in_three_lines():
    """תנאי הסיום של שלב 2: סל מהמאגר בשלוש שורות, והתוצאה זהה לדוגמת ה-PRD."""
    bread, milk, tomato = (find_product(n) for n in ("לחם אחיד כהה", "חלב 3% קרטון", "עגבניות חממה 1 ק\"ג"))
    milk.quantity = 2
    res = calculate_basket([bread, milk, tomato], CARD)
    assert money(res.total_revenue) == 30.40
    assert money(res.contribution) == 4.39
    assert res.warnings == []  # לשלושת המוצרים יש מחיר קנייה, ולכן אין אומדן


def test_catalog_missing_buy_price_is_estimated():
    res = calculate_basket([find_product("פסטה 500 גרם")], CARD)
    assert res.items[0].buy_price_estimated
    assert res.items[0].buy_price == pytest.approx(5.90 * 0.75)


def test_find_unknown_product_raises():
    with pytest.raises(KeyError):
        find_product("מוצר שלא קיים")


# ---------- התייקרות ספקים 5% ----------

def test_supplier_increase_matches_design_screen():
    """המספרים במסך design/scenario_active: רווח תרומתי 4.39 → 3.14, נקודת איזון 25.94 → 27.21."""
    base = calculate_basket(prd_basket(), CARD)
    alt = calculate_basket(supplier_increase(prd_basket()), CARD)
    cmp = compare_scenarios(base, alt)
    assert money(alt.naive_cost) == 23.31
    assert money(alt.contribution) == 3.14
    assert money(alt.breakeven_revenue) == 27.21
    assert money(cmp["contribution"]["change"]) == -1.25


def test_supplier_increase_does_not_change_original():
    basket = prd_basket()
    before = [asdict(it) for it in basket]
    supplier_increase(basket)
    assert [asdict(it) for it in basket] == before


def test_supplier_increase_applies_to_estimated_price():
    alt = supplier_increase([find_product("פסטה 500 גרם")])
    assert alt[0].buy_price == pytest.approx(5.90 * 0.75 * 1.05)


# ---------- התייקרות מוצרי חלב ----------

def test_dairy_increase_only_changes_dairy():
    basket = prd_basket()
    alt = dairy_increase(basket, 0.10)
    assert [it.buy_price for it in alt] == pytest.approx([5.00, 5.94, 6.40])
    assert [asdict(it) for it in basket] == [asdict(it) for it in prd_basket()]


def test_dairy_increase_profit_change():
    """חלב: 5.40 → 5.94, עלות מתואמת ליחידה 6.00 → 6.60, כפול 2 = ‎-1.20 ₪ ברווח."""
    base = calculate_basket(prd_basket(), CARD)
    alt = calculate_basket(dairy_increase(prd_basket(), 0.10), CARD)
    assert money(alt.contribution - base.contribution) == -1.20
    assert money(alt.contribution) == 3.19


def test_invalid_increase_rejected():
    with pytest.raises(ValueError):
        supplier_increase(prd_basket(), -1.0)


# ---------- שינוי מסלול אשראי ----------

def test_card_plan_change_lower_rate():
    alt_payment = card_plan_change(CARD, variable_rate=0.01)
    assert (alt_payment.variable_rate, alt_payment.fixed_fee) == (0.01, 0.50)
    assert CARD.variable_rate == 0.015  # המקור לא השתנה
    res = calculate_basket(prd_basket(), alt_payment)
    assert money(res.card_fee) == 0.80  # 0.50 + 1% × 30.40


def test_card_plan_change_to_cash_saves_fee():
    base = calculate_basket(prd_basket(), CARD)
    alt = calculate_basket(prd_basket(), card_plan_change(CARD, method="cash"))
    assert money(alt.contribution - base.contribution) == 0.96
