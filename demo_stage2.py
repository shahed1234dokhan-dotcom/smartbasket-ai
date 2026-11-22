"""דף בדיקה זמני לשלבים 1–2: מאגר המוצרים, המנוע והתרחישים המוכנים.

זה לא הממשק הסופי (app.py ייבנה בשלב 3 לפי העיצוב). הרצה:
    streamlit run demo_stage2.py
"""
import pandas as pd
import streamlit as st

from smartbasket import PaymentSettings, calculate_basket, compare_scenarios, money
from smartbasket.catalog import load_products
from smartbasket.presets import card_plan_change, dairy_increase, supplier_increase

st.set_page_config(page_title="SmartBasket — בדיקת שלב 2", layout="wide")
st.markdown(
    "<style>.stApp, .stMarkdown, .stDataFrame, label {direction: rtl; text-align: right;}</style>",
    unsafe_allow_html=True,
)

st.title("SmartBasket AI: דף בדיקה לשלב 2")
st.caption("דף בדיקה זמני, לא הממשק הסופי. כל הנתונים מדומים. "
           "רווח תרומתי לסל אינו כולל שכירות, שכר והוצאות קבועות.")

catalog = load_products()
PRD_QTY = {"לחם אחיד כהה": 1, "חלב 3% קרטון": 2, "עגבניות חממה 1 ק\"ג": 1}

# ---------- בחירת סל ----------
st.subheader("1. בחירת סל מהמאגר")
st.write("הכמויות מתחילות מסל הדוגמה של ה-PRD. כמות 0 = המוצר לא בסל.")
table = pd.DataFrame(
    {
        "מוצר": [p.name for p in catalog],
        "קטגוריה": [p.category for p in catalog],
        "מחיר מכירה": [p.sell_price for p in catalog],
        "מחיר קנייה": [p.buy_price for p in catalog],
        "כמות": [float(PRD_QTY.get(p.name, 0)) for p in catalog],
    }
)
edited = st.data_editor(
    table,
    disabled=["מוצר", "קטגוריה", "מחיר מכירה", "מחיר קנייה"],
    column_config={"כמות": st.column_config.NumberColumn(min_value=0.0, step=1.0)},
    hide_index=True,
    use_container_width=True,
)
basket = []
for product, qty in zip(catalog, edited["כמות"]):
    if qty and qty > 0:
        product.quantity = float(qty)
        basket.append(product)

# ---------- תשלום ----------
st.subheader("2. אמצעי תשלום")
c1, c2, c3 = st.columns(3)
method = c1.radio("אמצעי תשלום", ["אשראי", "מזומן"], horizontal=True)
rate_pct = c2.number_input("עמלה משתנה (%)", 0.0, 9.99, 1.5, 0.1)
fixed = c3.number_input("עמלה קבועה (₪)", 0.0, 10.0, 0.50, 0.05)
payment = PaymentSettings("card" if method == "אשראי" else "cash", rate_pct / 100, fixed)

# ---------- תרחיש ----------
st.subheader("3. תרחיש מוכן")
choice = st.radio(
    "תרחיש",
    ["ללא", "התייקרות ספקים 5%", "התייקרות מוצרי חלב", "שינוי מסלול אשראי"],
    horizontal=True,
)
alt_items, alt_payment = basket, payment
if choice == "התייקרות ספקים 5%":
    alt_items = supplier_increase(basket)
elif choice == "התייקרות מוצרי חלב":
    pct = st.slider("אחוז ההתייקרות (הצעה: 10%)", 0, 30, 10)
    alt_items = dairy_increase(basket, pct / 100)
elif choice == "שינוי מסלול אשראי":
    d1, d2 = st.columns(2)
    new_rate = d1.number_input("עמלה משתנה חדשה (%)", 0.0, 9.99, 1.0, 0.1)
    new_fixed = d2.number_input("עמלה קבועה חדשה (₪)", 0.0, 10.0, 0.50, 0.05)
    alt_payment = card_plan_change(payment, variable_rate=new_rate / 100, fixed_fee=new_fixed)

# ---------- תוצאות ----------
st.subheader("4. תוצאות")
try:
    base = calculate_basket(basket, payment)
    alt = calculate_basket(alt_items, alt_payment)
except ValueError as e:
    st.error(str(e))
    st.stop()

k = st.columns(4)
k[0].metric("הכנסות", f"₪{money(base.total_revenue):.2f}")
k[1].metric("רווח נאיבי", f"₪{money(base.naive_profit):.2f}")
k[2].metric("רווח תרומתי משוער", f"₪{money(base.contribution):.2f}", f"{base.margin_pct:.2f}%", delta_color="off")
k[3].metric("סך השחיקה (פחת + עמלה)", f"₪{money(base.spoilage_loss + base.card_fee):.2f}")
st.write(f"נקודת איזון של הסל: **₪{money(base.breakeven_revenue):.2f}**")
for w in base.warnings:
    st.info("אומדן: " + w)

if choice != "ללא":
    st.markdown(f"**השוואה: בסיס מול \"{choice}\"**")
    labels = {
        "total_revenue": "הכנסות",
        "adjusted_cost": "עלות מתואמת לפחת",
        "spoilage_loss": "הפסד על פחת",
        "card_fee": "עמלת אשראי",
        "contribution": "רווח תרומתי משוער",
        "breakeven_revenue": "נקודת איזון",
    }
    rows = [
        {"מדד": labels[key], "לפני": money(v["before"]), "אחרי": money(v["after"]), "שינוי": money(v["change"])}
        for key, v in compare_scenarios(base, alt).items()
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

with st.expander("פירוט לפי פריט (בסיס)"):
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "מוצר": r.name,
                    "כמות": r.quantity,
                    "מחיר קנייה": money(r.buy_price),
                    "אומדן": "כן" if r.buy_price_estimated else "",
                    "פחת %": round(r.spoilage_rate * 100, 1),
                    "עלות מתואמת": money(r.adjusted_cost),
                    "הכנסה": money(r.revenue),
                    "רווח לפני עמלה": money(r.margin_before_card),
                }
                for r in base.items
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
