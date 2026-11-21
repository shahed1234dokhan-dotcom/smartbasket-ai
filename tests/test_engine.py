"""בדיקות יחידה למנוע החישוב. הערכים הצפויים לקוחים מהדוגמאות המספריות שבמסמכי האפיון."""
import pytest

from smartbasket import Item, PaymentSettings, calculate_basket, compare_scenarios, money


def prd_basket():
    """דוגמת ה-PRD (סעיף 6): לחם, חלב 3%, עגבניות."""
    return [
        Item("לחם אחיד", "יבש", 1, sell_price=7.00, buy_price=5.00, spoilage_rate=0.01),
        Item("חלב 3%", "חלב-מקורר", 2, sell_price=7.20, buy_price=5.40, spoilage_rate=0.10),
        Item("עגבניות 1 ק\"ג", "ירקות-פירות", 1, sell_price=9.00, buy_price=6.40, spoilage_rate=0.20),
    ]


CARD = PaymentSettings("card", 0.015, 0.50)
CASH = PaymentSettings("cash")


# ---------- דוגמאות מהמסמכים ----------

def test_spec_example_single_fresh_item():
    """אפיון סעיף 7."""
    res = calculate_basket([Item("ירק טרי", "ירקות-פירות", 2, 9, 6, 0.20)], CARD)
    assert money(res.total_revenue) == 18.00
    assert money(res.adjusted_cost) == 15.00
    assert money(res.card_fee) == 0.77
    assert money(res.contribution) == 2.23


def test_prd_example_totals():
    res = calculate_basket(prd_basket(), CARD)
    assert money(res.total_revenue) == 30.40
    assert money(res.naive_cost) == 22.20
    assert money(res.naive_profit) == 8.20
    assert money(res.adjusted_cost) == 25.05
    assert money(res.spoilage_loss) == 2.85
    assert money(res.card_fee) == 0.96
    assert money(res.contribution) == 4.39
    # מערכים לא מעוגלים: 14.45%. ה-PRD מציג 14.44% כי חישב מסכומים מעוגלים (נקודה פתוחה).
    assert round(res.margin_pct, 2) == 14.45


def test_prd_example_per_item():
    res = calculate_basket(prd_basket(), CARD)
    assert [money(r.adjusted_cost) for r in res.items] == [5.05, 12.00, 8.00]
    assert [money(r.margin_before_card) for r in res.items] == [1.95, 2.40, 1.00]


def test_cash_has_no_fee():
    res = calculate_basket(prd_basket(), CASH)
    assert res.card_fee == 0
    assert money(res.contribution) == 5.35  # 30.40 - 25.05


# ---------- התנהגות המודל ----------

def test_zero_spoilage_equals_naive_cost():
    res = calculate_basket([Item("אורז", "יבש", 3, 10, 7, 0.0)], CASH)
    assert res.adjusted_cost == res.naive_cost == 21
    assert res.spoilage_loss == 0


def test_default_spoilage_by_category():
    items = [
        Item("פסטה", "יבש", 1, 5, 3),
        Item("יוגורט", "חלב-מקורר", 1, 5, 3),
        Item("בננה", "ירקות-פירות", 1, 5, 3),
    ]
    res = calculate_basket(items, CASH)
    assert [r.spoilage_rate for r in res.items] == [0.01, 0.10, 0.20]


def test_missing_buy_price_is_estimated():
    res = calculate_basket([Item("גבינה", "חלב-מקורר", 1, 20)], CASH)
    row = res.items[0]
    assert row.buy_price == 15.0
    assert row.buy_price_estimated is True
    assert any("גבינה" in w for w in res.warnings)


@pytest.mark.parametrize("payment", [CARD, CASH], ids=["card", "cash"])
def test_breakeven_gives_zero_contribution(payment):
    res = calculate_basket(prd_basket(), payment)
    r = payment.variable_rate if payment.method == "card" else 0
    f = payment.fixed_fee if payment.method == "card" else 0
    be = res.breakeven_revenue
    assert be - res.adjusted_cost - (f + r * be) == pytest.approx(0, abs=1e-9)
    if payment.method == "card":
        assert money(be) == 25.94


def test_compare_lower_spoilage_increases_contribution():
    base = calculate_basket(prd_basket(), CARD)
    alt_items = prd_basket()
    alt_items[2].spoilage_rate = 0.10
    alt = calculate_basket(alt_items, CARD)
    diff = compare_scenarios(base, alt)
    assert diff["contribution"]["change"] > 0
    # עגבניות: 6.40/0.8 - 6.40/0.9 = 8.00 - 7.111 = 0.889
    assert money(diff["contribution"]["change"]) == 0.89
    assert diff["total_revenue"]["change"] == 0


def test_compare_switch_to_cash_saves_fee():
    diff = compare_scenarios(calculate_basket(prd_basket(), CARD), calculate_basket(prd_basket(), CASH))
    assert money(diff["contribution"]["change"]) == 0.96


# ---------- קלט לא תקין ----------

@pytest.mark.parametrize(
    "item",
    [
        Item("x", "יבש", 0, 5, 3),               # כמות 0
        Item("x", "יבש", -1, 5, 3),              # כמות שלילית
        Item("x", "יבש", 1, 0, 3),               # מחיר מכירה 0
        Item("x", "יבש", 1, 5, -1),              # מחיר קנייה שלילי
        Item("x", "יבש", 1, 5, 3, 1.0),          # פחת 100% — חלוקה באפס
        Item("x", "יבש", 1, 5, 3, -0.1),         # פחת שלילי
        Item("", "יבש", 1, 5, 3),                # שם ריק
        Item("א" * 51, "יבש", 1, 5, 3),          # שם ארוך מ-50
        Item("x", "בשר", 1, 5, 3),               # קטגוריה לא מוכרת
        Item("x", "יבש", float("nan"), 5, 3),    # NaN
    ],
    ids=["qty0", "qty-neg", "price0", "cost-neg", "d=1", "d-neg",
         "name-empty", "name-long", "bad-category", "nan"],
)
def test_invalid_item_rejected(item):
    with pytest.raises(ValueError):
        calculate_basket([item], CASH)


@pytest.mark.parametrize(
    "payment",
    [
        PaymentSettings("card", 0.10, 0.5),   # r = 10%
        PaymentSettings("card", -0.01, 0.5),  # r שלילי
        PaymentSettings("card", 0.015, -1),   # F שלילי
        PaymentSettings("bitcoin"),           # אמצעי תשלום לא מוכר
    ],
    ids=["r=10%", "r-neg", "F-neg", "bad-method"],
)
def test_invalid_payment_rejected(payment):
    with pytest.raises(ValueError):
        calculate_basket(prd_basket(), payment)


def test_empty_basket_rejected():
    with pytest.raises(ValueError, match="ריק"):
        calculate_basket([], CASH)
