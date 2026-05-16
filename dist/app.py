import sqlite3
import pandas as pd
from datetime import datetime
import io
import streamlit as st

# Configure the browser tab title, layout mode, and initial sidebar state
st.set_page_config(
    page_title="Perfumes ERP Manager v3.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================================
# SYSTEM DATABASE ARCHITECTURE INITIALIZATION
# =========================================================================
def global_db_init():
    with sqlite3.connect("inventory.db") as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # 1. Base Configurations: Categories Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE NOT NULL
            )
        """)
        
        # 2. Base Configurations: Products Name Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT UNIQUE NOT NULL
            )
        """)
        
        # 3. Relational Core Transaction Ledger
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS main_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                category_id INTEGER,
                total_qty REAL DEFAULT 0,
                usage_qty REAL DEFAULT 0,
                remaining REAL DEFAULT 0,
                unit TEXT,
                reorder_level REAL DEFAULT 10,
                last_updated TEXT,
                FOREIGN KEY(product_id) REFERENCES products_registry(id) ON DELETE CASCADE,
                FOREIGN KEY(category_id) REFERENCES categories_registry(id) ON DELETE CASCADE,
                UNIQUE(product_id, category_id)
            )
        """)
        
        # 4. Audit Outward Tracking Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issue_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_date TEXT,
                item_name TEXT,
                quantity REAL,
                approved_by TEXT,
                remarks TEXT
            )
        """)
        conn.commit()

# Helper dict utilities to keep state synchronized across web elements
def get_db_dicts():
    with sqlite3.connect("inventory.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, product_name FROM products_registry")
        prods = {r[1]: r[0] for r in cursor.fetchall()}
        cursor.execute("SELECT id, category_name FROM categories_registry")
        cats = {r[1]: r[0] for r in cursor.fetchall()}
    return prods, cats

# Initialize database schema immediately on load
global_db_init()

# =========================================================================
# MASTER WEB APPLICATION SIDEBAR NAVIGATION CONTROLLER
# =========================================================================
st.sidebar.title("💎 Inventory ERP System")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Go To Module:", 
    ["Dashboard Home", "Base Config (Products/Cats)", "Main Inventory Ledger", "Issue Dispatch Logs", "Excel Export Reports"]
)

# =========================================================================
# MODULE 1: DASHBOARD HOME VIEW
# =========================================================================
if page == "Dashboard Home":
    st.title("Dashboard")
    st.markdown("Welcome to your centralized manufacturing management web app.")
    
    with sqlite3.connect("inventory.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM main_inventory")
        total_items = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM main_inventory WHERE remaining <= reorder_level")
        low_stock = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM issue_log")
        total_issues = cursor.fetchone()[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Registered Stock Mappings", int(total_items))
    col2.metric("Critical Low-Stock Warnings", int(low_stock), delta=f"-{low_stock}" if low_stock > 0 else "0", delta_color="inverse")
    col3.metric("Dispatched Logs Handled", int(total_issues))

# =========================================================================
# MODULE 2: BASE CONFIGS (PRODUCTS & CATEGORIES MANAGEMENT)
# =========================================================================
elif page == "Base Config (Products/Cats)":
    st.title("🔧 System Base Parameters Setup")
    col_left, col_right = st.columns(2)
    
    with sqlite3.connect("inventory.db") as conn:
        with col_left:
            st.subheader("Manage Base Registry Products")
            p_name = st.text_input("New Product Label Name", key="add_p")
            if st.button("Register Product", type="primary"):
                if p_name.strip():
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO products_registry (product_name) VALUES (?)", (p_name.strip(),))
                        conn.commit()
                        st.success(f"Registered: {p_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("This product label already exists inside your registry.")
                else:
                    st.warning("Product name field cannot be left blank.")
            
            df_p = pd.read_sql_query("SELECT id as 'ID', product_name as 'Registered Product Name' FROM products_registry", conn)
            st.dataframe(df_p, use_container_width=True, hide_index=True)
            
            st.markdown("**Delete Selected Product Label**")
            p_to_del = st.selectbox("Choose product label to drop:", [""] + list(df_p['Registered Product Name'].values))
            if st.button("Delete Product Label", type="primary"):
                if p_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM products_registry WHERE product_name = ?", (p_to_del,))
                    conn.commit()
                    st.rerun()

        with col_right:
            st.subheader("Manage Base Registry Categories")
            c_name = st.text_input("New Category Label Name", key="add_c")
            if st.button("Register Category", type="primary"):
                if c_name.strip():
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO categories_registry (category_name) VALUES (?)", (c_name.strip(),))
                        conn.commit()
                        st.success(f"Registered: {c_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("This category label already exists inside your registry.")
                else:
                    st.warning("Category name field cannot be left blank.")
                    
            df_c = pd.read_sql_query("SELECT id as 'ID', category_name as 'Registered Category Name' FROM categories_registry", conn)
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            
            st.markdown("**Delete Selected Category Label**")
            c_to_del = st.selectbox("Choose category label to drop:", [""] + list(df_c['Registered Category Name'].values))
            if st.button("Delete Category Label", type="primary"):
                if c_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM categories_registry WHERE category_name = ?", (c_to_del,))
                    conn.commit()
                    st.rerun()

# =========================================================================
# MODULE 3: MAIN INVENTORY LEDGER
# =========================================================================
elif page == "Main Inventory Ledger":
    st.title("📊 Main Stock Ledger")
    
    prods, cats = get_db_dicts()
    
    if not prods or not cats:
        st.warning("Please configure at least one Product and Category in the Base Config tab first.")
    else:
        st.subheader("Link Stock Profile")
        with st.form("ledger_entry_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                p_select = st.selectbox("Product:", options=list(prods.keys()))
                cat_select = st.selectbox("Category:", options=list(cats.keys()))
            with col2:
                total_q = st.number_input("Total Stock Received:", min_value=0.0, step=1.0)
                reorder_l = st.number_input("Reorder Boundary Level:", min_value=0.0, step=1.0, value=10.0)
            with col3:
                unit_label = st.selectbox("Measurement Unit:", ["Liters", "Pcs", "Kgs", "Ml", "Boxes"])
                
            submit_ledger = st.form_submit_button("Map Stock Entry", type="primary")
            
        if submit_ledger:
            pid = prods[p_select]
            cid = cats[cat_select]
            now_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, total_qty, remaining FROM main_inventory 
                    WHERE product_id = ? AND category_id = ?
                """, (pid, cid))
                
                existing_stock = cursor.fetchone()
                
                if existing_stock:
                    row_id, prev_total, prev_remaining = existing_stock
                    new_total = prev_total + total_q
                    new_remaining = prev_remaining + total_q
                    
                    cursor.execute("""
                        UPDATE main_inventory 
                        SET total_qty = ?, remaining = ?, reorder_level = ?, last_updated = ?
                        WHERE id = ?
                    """, (new_total, new_remaining, reorder_l, now_time, row_id))
                    st.success(f"Added {total_q} units! New total stock balance for '{p_select}': {new_total} {unit_label}.")
                else:
                    cursor.execute("""
                        INSERT INTO main_inventory (product_id, category_id, total_qty, remaining, unit, reorder_level, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (pid, cid, total_q, total_q, unit_label, reorder_l, now_time))
                    st.success(f"Successfully created a new stock profile mapping for '{p_select}'.")
                
                conn.commit()
                st.rerun()

        st.markdown("---")
        st.subheader("Active Structural Stock Quantities Balance")
        with sqlite3.connect("inventory.db") as conn:
            df_ledger = pd.read_sql_query("""
                SELECT m.id as 'Stock ID',
                       p.product_name as 'Product',
                       c.category_name as 'Category',
                       m.total_qty as 'Total Deposited',
                       m.usage_qty as 'Total Deducted',
                       m.remaining as 'Current Balance',
                       m.unit as 'Unit',
                       m.reorder_level as 'Alert Limit'
                FROM main_inventory m
                JOIN products_registry p ON m.product_id = p.id
                JOIN categories_registry c ON m.category_id = c.id
            """, conn)
            
        def highlight_low_stock(row):
            if row['Current Balance'] <= row['Alert Limit']:
                return ['background-color: #ff4b4b; color: white; font-weight: bold;'] * len(row)
            return [''] * len(row)
            
        styled_df = df_ledger.style.apply(highlight_low_stock, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

# =========================================================================
# MODULE 4: ISSUE DISPATCH LOGS (WITH QUANTITY STOCK VALIDATION)
# =========================================================================
elif page == "Issue Dispatch Logs":
    st.title("📦 Outward Issue & Dispatch Tracking Logs")
    
    with sqlite3.connect("inventory.db") as conn:
        df_products = pd.read_sql_query("SELECT product_name FROM products_registry", conn)
        product_options = [""] + list(df_products['product_name'].values)

    st.subheader("Record New Dispatch Entry")
    with st.form("issue_entry_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_product = st.selectbox("Select Product to Issue:", options=product_options)
            issued_by = st.text_input("Approved By (Name/ID):")
        with col2:
            issue_qty = st.number_input("Quantity to Dispatch:", min_value=0.1, step=1.0, format="%.2f")
        with col3:
            issue_date = st.date_input("Dispatch Date:", value=datetime.today())
            remarks = st.text_area("Remarks / Notes:", max_chars=150)
            
        submit_issue = st.form_submit_button("Commit Dispatch Entry", type="primary")

    if submit_issue:
        if not selected_product:
            st.error("Please select a valid product from the dropdown menu.")
        elif issue_qty <= 0:
            st.error("Dispatch quantity must be greater than zero.")
        elif not issued_by.strip():
            st.error("Authorized approver field cannot be left blank.")
        else:
            formatted_date = issue_date.strftime("%Y-%m-%d")
            
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT SUM(remaining), unit FROM main_inventory 
                    WHERE product_id = (SELECT id FROM products_registry WHERE product_name = ?)
                """, (selected_product,))
                
                stock_status = cursor.fetchone()
                current_stock = stock_status[0] if stock_status and stock_status[0] is not None else 0.0
                stock_unit = stock_status[1] if stock_status and stock_status[1] is not None else "units"
                
                if current_stock < issue_qty:
                    st.error(f"❌ Dispatch Blocked! Insufficient Stock. Requested: {issue_qty} {stock_unit} | Available Current Stock: {current_stock} {stock_unit}")
                else:
                    cursor.execute("""
                        SELECT id, quantity FROM issue_log 
                        WHERE item_name = ? AND issue_date = ? AND approved_by = ?
                    """, (selected_product, formatted_date, issued_by.strip()))
                    
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        record_id, previous_qty = existing_record
                        new_total_qty = previous_qty + issue_qty
                        updated_remarks = f"{remarks.strip()} (Updated: +{issue_qty} units)"
                        
                        cursor.execute("""
                            UPDATE issue_log 
                            SET quantity = ?, remarks = ?
                            WHERE id = ?
                        """, (new_total_qty, updated_remarks, record_id))
                    else:
                        cursor.execute("""
                            INSERT INTO issue_log (issue_date, item_name, quantity, approved_by, remarks)
                            VALUES (?, ?, ?, ?, ?)
                        """, (formatted_date, selected_product, issue_qty, issued_by.strip(), remarks.strip()))
                    
                    cursor.execute("""
                        UPDATE main_inventory
                        SET usage_qty = usage_qty + ?,
                            remaining = remaining - ?
                        WHERE product_id = (SELECT id FROM products_registry WHERE product_name = ?)
                    """, (issue_qty, issue_qty, selected_product))
                    
                    st.success(f"✅ Dispatch entry processed successfully! Dispatched: {issue_qty} {stock_unit}.")
                    conn.commit()
                    st.rerun()

    st.markdown("---")
    st.subheader("Historical Dispatch Audit Trail Ledger")
    
    with sqlite3.connect("inventory.db") as conn:
        df_logs = pd.read_sql_query("""
            SELECT id as 'Log ID', 
                   issue_date as 'Date', 
                   item_name as 'Product Name', 
                   quantity as 'Total Dispatched Qty', 
                   approved_by as 'Authorized Approver', 
                   remarks as 'Transaction Remarks' 
            FROM issue_log 
            ORDER BY id DESC
        """, conn)
        
    st.dataframe(df_logs, use_container_width=True, hide_index=True)

# =========================================================================
# MODULE 5: EXCEL REPORT GENERATOR
# =========================================================================
elif page == "Excel Export Reports":
    st.title("🖨️ ERP Excel Report Generator Module")
    st.markdown("Generate clean, multi-tab audit spreadsheets containing live warehouse tracking ledger states and complete transaction timelines.")
    
    # Setup data pulling queries
    with sqlite3.connect("inventory.db") as conn:
        df_ledger_out = pd.read_sql_query("""
            SELECT m.id as 'Stock ID', p.product_name as 'Product', c.category_name as 'Category',
                   m.total_qty as 'Total Deposited', m.usage_qty as 'Total Deducted',
                   m.remaining as 'Current Balance', m.unit as 'Unit', m.reorder_level as 'Alert Limit',
                   m.last_updated as 'Last Transaction timestamp'
            FROM main_inventory m
            JOIN products_registry p ON m.product_id = p.id
            JOIN categories_registry c ON m.category_id = c.id
        """, conn)
        
        df_logs_out = pd.read_sql_query("""
            SELECT id as 'Log ID', issue_date as 'Dispatch Date', item_name as 'Product Label Name', 
                   quantity as 'Quantity Dispatched', approved_by as 'Authorized Signatory', remarks as 'Remarks'
            FROM issue_log ORDER BY id DESC
        """, conn)

    # UI Action Panel Layout
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Live Ledger Metrics Preview")
        st.dataframe(df_ledger_out, use_container_width=True, hide_index=True)
    with col_r:
        st.subheader("Dispatch Timeline Log Preview")
        st.dataframe(df_logs_out, use_container_width=True, hide_index=True)
        
    st.markdown("---")
    
    # File compiler generation memory pipeline engine
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_ledger_out.to_excel(writer, sheet_name="Warehouse Current Balance", index=False)
        df_logs_out.to_excel(writer, sheet_name="Outward Dispatches Trail Log", index=False)
        
    # Generate timestamped file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    report_filename = f"Perfumes_ERP_Report_{timestamp}.xlsx"
    
    # Render interactive Streamlit native download controller widget link
    st.download_button(
        label="📥 Compile & Download Master Excel Report",
        data=buffer.getvalue(),
        file_name=report_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
    st.info("The exported file features dedicated layout tables separating active warehouse levels from dispatch records.")
