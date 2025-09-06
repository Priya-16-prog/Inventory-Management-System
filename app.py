
import streamlit as st
import mysql.connector
import pandas as pd
from io import BytesIO
from datetime import datetime
import random

# --- PDF (ReportLab) ---
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# ---------------- DB ----------------
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="RaviPriya1606*",
       database="inventory_db",
        autocommit=True,
    )

def fetch_inventory():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM inventory")
    rows = cur.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["ID", "Name", "Quantity", "Price"])

def add_item(name, qty, price):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO inventory (name, quantity, price) VALUES (%s, %s, %s)", (name, qty, price))
    conn.close()

def update_item(item_id, qty, price):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE inventory SET quantity=%s, price=%s WHERE id=%s", (qty, price, item_id))
    conn.close()

def delete_item(item_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM inventory WHERE id=%s", (item_id,))
    conn.close()

def reduce_stock(item_id, qty):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE inventory SET quantity = quantity - %s WHERE id=%s", (qty, item_id))
    conn.close()

# ------------- PDF helper -------------
def make_invoice_pdf(business_name, business_addr, customer_name, invoice_no, items, subtotal, tax_rate, tax_amt, grand_total):
    """
    items: list of tuples (Item, Qty, Price, Total)
    returns: BytesIO of PDF
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18, leftMargin=18, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()

    parts = []
    title = Paragraph(f"<b>{business_name}</b>", styles["Title"])
    addr = Paragraph(business_addr, styles["Normal"])
    hdr = Paragraph(f"<b>Invoice</b> &nbsp;&nbsp; #{invoice_no} &nbsp;&nbsp; Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"])
    cust = Paragraph(f"<b>Billed To:</b> {customer_name or 'Walk-in Customer'}", styles["Normal"])

    parts += [title, addr, Spacer(1, 6), hdr, cust, Spacer(1, 12)]

    table_data = [["Item", "Qty", "Price", "Total"]]
    for it in items:
        table_data.append([str(it[0]), str(it[1]), f"₹{it[2]:.2f}", f"₹{it[3]:.2f}"])

    tbl = Table(table_data, colWidths=[90*mm, 20*mm, 35*mm, 35*mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.4, colors.grey),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
    ]))
    parts += [tbl, Spacer(1, 12)]

    summary = [
        ["Subtotal", f"₹{subtotal:.2f}"],
        [f"Tax ({tax_rate:.2f}%)", f"₹{tax_amt:.2f}"],
        ["Grand Total", f"₹{grand_total:.2f}"],
    ]
    sum_tbl = Table(summary, colWidths=[120*mm, 60*mm])
    sum_tbl.setStyle(TableStyle([
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("LINEABOVE", (0,-1), (-1,-1), 0.5, colors.black),
    ]))
    parts += [sum_tbl, Spacer(1, 12), Paragraph("Thank you for your business!", styles["Italic"])]

    doc.build(parts)
    buf.seek(0)
    return buf

# ------------- UI -------------
st.title("📦 Inventory Management System (MySQL + Streamlit + PDF Invoice)")

menu = ["Inventory", "Billing"]
choice = st.sidebar.radio("Menu", menu)

# -- Inventory page --
if choice == "Inventory":
    st.header("🗂 Inventory Management")

    with st.form("add_form"):
        name = st.text_input("Item Name")
        qty = st.number_input("Quantity", min_value=1, step=1)
        price = st.number_input("Price", min_value=0.0, step=0.5)
        submitted = st.form_submit_button("Add Item")
        if submitted and name:
            add_item(name, qty, price)
            st.success(f"✅ {name} added")

    st.subheader("📋 Current Inventory")
    inv_df = fetch_inventory()
    st.dataframe(inv_df, use_container_width=True)

    if not inv_df.empty:
        st.subheader("✏️ Update / Delete")
        item_id = st.selectbox("Select Item ID", inv_df["ID"])
        row = inv_df[inv_df["ID"] == item_id].iloc[0]
        new_qty = st.number_input("New Quantity", min_value=0, step=1, value=int(row["Quantity"]))
        new_price = st.number_input("New Price", min_value=0.0, step=0.5, value=float(row["Price"]))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Update"):
                update_item(item_id, new_qty, new_price)
                st.success("✅ Updated")
        with c2:
            if st.button("Delete"):
                delete_item(item_id)
                st.warning("🗑️ Deleted")

# -- Billing page --
elif choice == "Billing":
    st.header("🧾 Billing & Invoice")

    inv_df = fetch_inventory()
    st.dataframe(inv_df, use_container_width=True)

    if "cart" not in st.session_state:
        st.session_state.cart = []

    with st.form("bill_form"):
        item_id = st.selectbox("Select Item ID", inv_df["ID"] if not inv_df.empty else [])
        qty = st.number_input("Quantity", min_value=1, step=1)
        add_btn = st.form_submit_button("Add to Cart")
        if add_btn:
            row = inv_df[inv_df["ID"] == item_id].iloc[0]
            if qty > row["Quantity"]:
                st.error(f"Only {row['Quantity']} in stock")
            else:
                total = float(qty) * float(row["Price"])
                st.session_state.cart.append((row["Name"], int(qty), float(row["Price"]), float(total), int(item_id)))
                st.success(f"🛒 {qty} x {row['Name']} added")

    if st.session_state.cart:
        st.subheader("🛍️ Cart")
        cart_df = pd.DataFrame(st.session_state.cart, columns=["Item","Qty","Price","Total","ID"])
        st.table(cart_df[["Item","Qty","Price","Total"]])

        subtotal = float(cart_df["Total"].sum())
        customer_name = st.text_input("Customer Name", placeholder="Walk-in Customer")
        tax_rate = st.number_input("Tax %", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
        tax_amt = subtotal * (tax_rate / 100.0)
        grand_total = subtotal + tax_amt

        st.markdown(f"*Subtotal:* ₹{subtotal:.2f} &nbsp; | &nbsp; *Tax:* ₹{tax_amt:.2f} &nbsp; | &nbsp; *Grand Total:* ₹{grand_total:.2f}")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Generate Bill (Update Stock)"):
                for _, r in cart_df.iterrows():
                    reduce_stock(int(r["ID"]), int(r["Qty"]))
                st.success("✅ Stock updated. You can now download the invoice.")
        with c2:
            # Build PDF whenever user clicks download (doesn't re-update stock)
            inv_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100,999)}"
            pdf_buf = make_invoice_pdf(
                business_name="Your Store Name",
                business_addr="123 Market Road, City, PIN 000000\nPhone: +91-00000-00000",
                customer_name=customer_name,
                invoice_no=inv_no,
                items=[(r["Item"], int(r["Qty"]), float(r["Price"]), float(r["Total"])) for _, r in cart_df.iterrows()],
                subtotal=subtotal,
                tax_rate=tax_rate,
                tax_amt=tax_amt,
                grand_total=grand_total
            )
            st.download_button(
                label="⬇️ Download PDF Invoice",
                data=pdf_buf,
                file_name=f"{inv_no}.pdf",
                mime="application/pdf"
            )
        with c3:
            if st.button("Clear Cart"):
                st.session_state.cart = []
                st.info("Cart cleared")
