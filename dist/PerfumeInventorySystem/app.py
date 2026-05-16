import sqlite3
from datetime import datetime
import io
import pandas as pd
import streamlit as st

# Configure browser tab title, layout mode, and initial sidebar state safely
st.set_page_config(
    page_title="Perfumes ERP Manager v3.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================================
# RELATIONAL DATABASE ARCHITECTURE INITIALIZATION
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
        
        # 2. Base Configurations: Tiers Table (Must exist first)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiers_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tier_name TEXT UNIQUE NOT NULL
            )
        """)
        
        # 3. Base Configurations: Products Name Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                tier_id INTEGER NOT NULL,
                FOREIGN KEY(tier_id) REFERENCES tiers_registry(id) ON DELETE CASCADE,
                UNIQUE(product_name, tier_id)
            )
        """)
        
        # 4. Relational Core Transaction Ledger
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
        
        # 5. Audit Outward Tracking Log
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
        
        # Seed default dictionary values safely in sequence order
        cursor.execute("SELECT COUNT(*) FROM tiers_registry")
        if cursor.fetchone()[0] == 0:
            categories = [("Raw Material",), ("Packaging",), ("Assembled SKU",)]
            cursor.executemany("INSERT OR IGNORE INTO categories_registry (category_name) VALUES (?)", categories)
            
            tiers = [("Standard",), ("Premium",), ("Tester",)]
            cursor.executemany("INSERT OR IGNORE INTO tiers_registry (tier_name) VALUES (?)", tiers)
            
            conn.commit()
            
            products = [
                ("Rose Essential Oil", 1),
                ("Ethanol Alcohol 96%", 1),
                ("P11 Cap", 1),
                ("P11 Bottle", 1),
                ("P11 Final SKU", 2)
            ]
            cursor.executemany("INSERT OR IGNORE INTO products_registry (product_name, tier_id) VALUES (?, ?)", products)
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            base_stock = [
                (1, 1, 10.0, 0, 10.0, "Liters", 5.0),
                (2, 1, 100.0, 0, 100.0, "Liters", 20.0),
                (3, 2, 500.0, 495.0, 5.0, "Pcs", 50.0),
                (4, 2, 500.0, 0, 500.0, "Pcs", 50.0),
                (5, 3, 50.0, 0, 50.0, "Pcs", 10.0)
            ]
            cursor.executemany("""
                INSERT OR IGNORE INTO main_inventory (product_id, category_id, total_qty, usage_qty, remaining, unit, reorder_level, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [(b[0], b[1], b[2], b[3], b[4], b[5], b[6], now) for b in base_stock])
            
        conn.commit()

# Helper dict utilities to sync dropdown lists with active database states
def get_db_dicts():
    with sqlite3.connect("inventory.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, category_name FROM categories_registry")
        cats = {r[1]: r[0] for r in cursor.fetchall()}
        cursor.execute("SELECT id, tier_name FROM tiers_registry")
        tiers = {r[1]: r[0] for r in cursor.fetchall()}
        return cats, tiers

# Initialize database schema immediately on load
global_db_init()

# =========================================================================
# MASTER WEB APPLICATION SIDEBAR NAVIGATION CONTROLLER
# =========================================================================
st.sidebar.title("💎 Inventory ERP System")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Go To Module:", 
    ["Dashboard Home", "Base Config (Products/Cats/Tiers)", "Main Inventory Ledger", "Issue Dispatch Logs", "Excel Export Reports"]
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
    col1.metric("Total Items Managed", int(total_items))
    col2.metric("Low Stock Alerts", int(low_stock), delta=f"-{low_stock}" if low_stock > 0 else "0", delta_color="inverse")
    col3.metric("Total Log Issues Filed", int(total_issues))

# =========================================================================
# MODULE 2: BASE CONFIGS (PRODUCTS, CATEGORIES, & TIERS CRUD)
# =========================================================================
elif page == "Base Config (Products/Cats/Tiers)":
    st.title("🔧 System Base Parameters Setup")
    col_left, col_mid, col_right = st.columns(3)
    
    with sqlite3.connect("inventory.db") as conn:
        # --- 1. TIERS COLUMN ---
        with col_left:
            st.subheader("Manage Tiers")
            t_name = st.text_input("New Tier Label Name", key="add_t")
            if st.button("Register Tier", type="primary"):
                if t_name.strip():
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tiers_registry (tier_name) VALUES (?)", (t_name.strip(),))
                        conn.commit()
                        st.success(f"Registered Tier: {t_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("This tier label already exists.")
                else:
                    st.warning("Tier name field cannot be blank.")
                    
            df_t = pd.read_sql_query("SELECT id as 'ID', tier_name as 'Tier Name' FROM tiers_registry", conn)
            st.dataframe(df_t, use_container_width=True, hide_index=True)
            
            st.markdown("**Delete Tier**")
            t_to_del = st.selectbox("Choose tier to drop:", [""] + list(df_t['Tier Name'].values), key="del_t_select")
            if st.button("Delete Tier"):
                if t_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tiers_registry WHERE tier_name = ?", (t_to_del,))
                    conn.commit()
                    st.success("Tier deleted successfully!")
                    st.rerun()

        # --- 2. DEPENDENT PRODUCTS COLUMN ---
        with col_mid:
            st.subheader("Manage Products")
            p_tier_choice = st.selectbox("Assign Product to Tier:", [""] + list(df_t['Tier Name'].values), key="prod_tier_assign")
            p_name = st.text_input("New Product Label Name", key="add_p")
            
            if st.button("Register Product", type="primary"):
                if p_name.strip() and p_tier_choice:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM tiers_registry WHERE tier_name = ?", (p_tier_choice,))
                        t_id = cursor.fetchone()[0]
                        
                        cursor.execute("INSERT INTO products_registry (product_name, tier_id) VALUES (?, ?)", (p_name.strip(), t_id))
                        conn.commit()
                        st.success(f"Registered '{p_name}' inside '{p_tier_choice}' Tier.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("This product label already exists inside this specific tier configuration.")
                else:
                    st.warning("Please complete both the Product Name and Tier Assignment.")
            
            df_p = pd.read_sql_query("""
                SELECT p.id as 'ID', p.product_name as 'Product Name', t.tier_name as 'Belongs to Tier' 
                FROM products_registry p
                JOIN tiers_registry t ON p.tier_id = t.id
            """, conn)
            st.dataframe(df_p, use_container_width=True, hide_index=True)
            
            st.markdown("**Delete Product**")
            p_to_del = st.selectbox("Choose product to drop:", [""] + list(df_p['Product Name'].values), key="del_p_select")
            if st.button("Delete Product"):
                if p_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM products_registry WHERE product_name = ?", (p_to_del,))
                    conn.commit()
                    st.success("Product deleted successfully!")
                    st.rerun()

        # --- 3. CATEGORIES COLUMN ---
        with col_right:
            st.subheader("Manage Categories")
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
                        st.error("This category label already exists.")
                else:
                    st.warning("Category name field cannot be blank.")
                    
            df_c = pd.read_sql_query("SELECT id as 'ID', category_name as 'Category Name' FROM categories_registry", conn)
            st.dataframe(df_c, use_container_width=True, hide_index=True)
            
            st.markdown("**Delete Category**")
            c_to_del = st.selectbox("Choose category to drop:", [""] + list(df_c['Category Name'].values), key="del_c_select")
            if st.button("Delete Category"):
                if c_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM categories_registry WHERE category_name = ?", (c_to_del,))
                    conn.commit()
                    st.success("Category deleted successfully!")
                    st.rerun()

# =========================================================================
# MODULE 3: MAIN INVENTORY LEDGER (WITH DEPENDENT DROPDOWNS)
# =========================================================================
elif page == "Main Inventory Ledger":
    st.title("📦 Master Inventory Control Ledger")
    
    cats, tiers = get_db_dicts()
    form_col, table_col = st.columns(2)
    
    with form_col:
        st.subheader("Inventory Action Controls")
        
        selected_tier = st.selectbox("Select Filter Tier Level:", [""] + list(tiers.keys()), key="inv_tier_select")
        
        available_products = {}
        if selected_tier:
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, product_name FROM products_registry WHERE tier_id = ?", (tiers[selected_tier],))
                available_products = {r[1]: r[0] for r in cursor.fetchall()}
        
        selected_prod = st.selectbox("Select Target Product Name:", [""] + list(available_products.keys()), 
                                     disabled=not selected_tier, 
                                     key="inv_prod_select",
                                     help="Choose a tier level above first to unlock products list.")
        
        selected_cat = st.selectbox("Select Target Category Group:", [""] + list(cats.keys()), key="inv_cat_select")
        
        val_tot = st.number_input("Total Quantity Inbound:", min_value=0.0, value=0.0)
        val_usg = st.number_input("Total Quantity Used Out:", min_value=0.0, value=0.0)
        val_unit = st.text_input("Unit Measure Label:", value="Pcs")
        val_reorder = st.number_input("Low Stock Safety Threshold Alert:", min_value=0.0, value=10.0)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Save/Add Entry", type="primary", use_container_width=True):
                if selected_prod and selected_cat and selected_tier:
                    with sqlite3.connect("inventory.db") as conn:
                        cursor = conn.cursor()
                        rem = val_tot - val_usg
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        try:
                            cursor.execute("""
                                INSERT INTO main_inventory (product_id, category_id, total_qty, usage_qty, remaining, unit, reorder_level, last_updated)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(product_id, category_id) DO UPDATE SET
                                    total_qty = total_qty + excluded.total_qty,
                                    usage_qty = usage_qty + excluded.usage_qty,
                                    remaining = (total_qty + excluded.total_qty) - (usage_qty + excluded.usage_qty),
                                    last_updated = excluded.last_updated,
                                    unit = excluded.unit,
                                    reorder_level = excluded.reorder_level
                            """, (available_products[selected_prod], cats[selected_cat], val_tot, val_usg, rem, val_unit, val_reorder, now))
                            conn.commit()
                            st.success(f"Inventory updated for {selected_prod} ({selected_tier})!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database Error: {e}")
                else:
                    st.warning("Please specify Tier, Product, and Category choices completely.")
                    
        with col_btn2:
            if st.button("Update Existing", use_container_width=True):
                if selected_prod and selected_cat and selected_tier:
                    with sqlite3.connect("inventory.db") as conn:
                        cursor = conn.cursor()
                        rem = val_tot - val_usg
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        cursor.execute("""
                            UPDATE main_inventory SET total_qty=?, usage_qty=?, remaining=?, unit=?, reorder_level=?, last_updated=?
                            WHERE product_id=? AND category_id=?
                        """, (val_tot, val_usg, rem, val_unit, val_reorder, now, available_products[selected_prod], cats[selected_cat]))
                        conn.commit()
                        st.success("Record modified successfully!")
                        st.rerun()
                        
        if st.button("Delete Stock Mapping Relationship Row", type="primary", use_container_width=True):
            if selected_prod and selected_cat and selected_tier:
                with sqlite3.connect("inventory.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM main_inventory WHERE product_id=? AND category_id=?", (available_products[selected_prod], cats[selected_cat]))
                    conn.commit()
                    st.warning("Relationship row dropped completely.")
                    st.rerun()

    with table_col:
        st.subheader("Live Operational Inventory Monitoring Grid")
        search_query = st.text_input("🔍 Live Grid Search:", placeholder="Type name, category, or tier string to filter...")
        
        with sqlite3.connect("inventory.db") as conn:
            sql = """
                SELECT p.product_name as 'Item Name', c.category_name as 'Category Group', t.tier_name as 'Tier Level',
                       m.total_qty as 'Total In', m.usage_qty as 'Total Out', m.remaining as 'In Stock', 
                       m.unit as 'Unit', m.reorder_level as 'Alert Threshold', m.last_updated as 'Last Updated'
                FROM main_inventory m
                JOIN products_registry p ON m.product_id = p.id
                JOIN categories_registry c ON m.category_id = c.id
                JOIN tiers_registry t ON p.tier_id = t.id
            """
            df = pd.read_sql_query(sql, conn)
        
        if search_query:
            df = df[
                df['Item Name'].str.contains(search_query, case=False) | 
                df['Category Group'].str.contains(search_query, case=False) |
                df['Tier Level'].str.contains(search_query, case=False)
            ]
            
        def highlight_low_stock(row):
            return ['background-color: #FFD2D2; color: #A94442' if row['In Stock'] <= row['Alert Threshold'] else '' for _ in row]
            
        st.dataframe(df.style.apply(highlight_low_stock, axis=1), use_container_width=True, hide_index=True)

# =========================================================================
# MODULE 4: AUDITED OUTWARD DISPATCH ISSUE TRACKING (WITH DEPENDENT DROPDOWNS)
# =========================================================================
elif page == "Issue Dispatch Logs":
    st.title("📋 Audit Dispatch Issue Tracking Log")
    form_col, table_col = st.columns(2)
    
    cats, tiers = get_db_dicts()
    
    with form_col:
        st.subheader("Log Outward Dispatch Row")
        
        # FIXED: Implemented parental filtering selections mapping tier levels upstream
        log_tier = st.selectbox("Select Filter Tier Level:", [""] + list(tiers.keys()), key="log_tier_select")
        
        log_products = {}
        if log_tier:
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                # Only display products that are registered under the selected tier inside main_inventory
                cursor.execute("""
                    SELECT DISTINCT p.id, p.product_name 
                    FROM main_inventory m
                    JOIN products_registry p ON m.product_id = p.id
                    WHERE p.tier_id = ?
                """, (tiers[log_tier],))
                log_products = {r[1]: r[0] for r in cursor.fetchall()}
        
        selected_log_prod = st.selectbox("Select Target Product Name:", [""] + list(log_products.keys()),
                                         disabled=not log_tier,
                                         key="log_prod_select",
                                         help="Choose a tier above to populate its registered products list.")
        
        # Fetch the applicable categories for the selected product to narrow choice down
        log_categories = {}
        if selected_log_prod:
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.id, c.category_name 
                    FROM main_inventory m
                    JOIN categories_registry c ON m.category_id = c.id
                    WHERE m.product_id = ?
                """, (log_products[selected_log_prod],))
                log_categories = {r[1]: r[0] for r in cursor.fetchall()}
                
        selected_log_cat = st.selectbox("Select Target Category Group:", [""] + list(log_categories.keys()),
                                         disabled=not selected_log_prod,
                                         key="log_cat_select",
                                         help="Select product above to unlock tracking categories.")

        i_qty = st.number_input("Quantity Outbound:", min_value=0.0, value=0.0)
        i_appr = st.text_input("Approved By Signature:")
        i_rem = st.text_input("Operational Remarks:")
        
        if st.button("Execute Stock-Out Transaction", type="primary", use_container_width=True):
            if selected_log_prod and selected_log_cat and i_appr and i_qty > 0:
                with sqlite3.connect("inventory.db") as conn:
                    cursor = conn.cursor()
                    
                    # Target explicit relational tracking IDs rather than fuzzy name strings
                    cursor.execute("""
                        SELECT id, remaining, usage_qty 
                        FROM main_inventory 
                        WHERE product_id = ? AND category_id = ?
                    """, (log_products[selected_log_prod], log_categories[selected_log_cat]))
                    res = cursor.fetchone()
                    
                    if res:
                        row_id, remaining, usage_qty = res
                        if remaining >= i_qty:
                            now = datetime.now().strftime("%Y-%m-%d %H:%M")
                            cursor.execute("""
                                UPDATE main_inventory 
                                SET usage_qty = usage_qty + ?, remaining = remaining - ?, last_updated = ? 
                                WHERE id = ?
                            """, (i_qty, i_qty, now, row_id))
                            
                            # Log formatted composite layout index references for your spreadsheet audits
                            composite_item_label = f"{selected_log_prod} ({log_tier} - {selected_log_cat})"
                            cursor.execute("""
                                INSERT INTO issue_log (issue_date, item_name, quantity, approved_by, remarks) 
                                VALUES (?, ?, ?, ?, ?)
                            """, (now, composite_item_label, i_qty, i_appr, i_rem if i_rem else "N/A"))
                            
                            conn.commit()
                            st.success(f"Stock-out handled! Dispatched {i_qty} units of {selected_log_prod}.")
                            st.rerun()
                        else:
                            st.error(f"Insufficient stock to dispatch. Available balance is: {remaining}")
                    else:
                        st.error("No active stock records exist matching this item-category mapping link.")
            else:
                st.warning("Please complete all dropdown choices, signature, and quantity inputs completely.")

    with table_col:
        st.subheader("Historical Dispatch Audit Trails Ledger")
        with sqlite3.connect("inventory.db") as conn:
            df_log = pd.read_sql_query("SELECT id as 'ID', issue_date as 'Timestamp', item_name as 'Item Dispatched', quantity as 'Qty Out', approved_by as 'Approved By', remarks as 'Remarks' FROM issue_log", conn)
        st.dataframe(df_log, use_container_width=True, hide_index=True)

# =========================================================================
# MODULE 5: EXCEL/CSV DATA EXPORT REPORTS 
# =========================================================================
elif page == "Excel Export Reports":
    st.title("📊 Excel & CSV Report Generation Workspace")
    st.markdown("Download backups of your live inventory transaction ledgers and audit historical logs.")
    
    with sqlite3.connect("inventory.db") as conn:
        sql_inv = """
            SELECT p.product_name as 'Item Name', c.category_name as 'Category Group', t.tier_name as 'Tier Level',
                   m.total_qty as 'Total In', m.usage_qty as 'Total Out', m.remaining as 'In Stock', 
                   m.unit as 'Unit', m.reorder_level as 'Alert Threshold', m.last_updated as 'Last Updated'
            FROM main_inventory m
            JOIN products_registry p ON m.product_id = p.id
            JOIN categories_registry c ON m.category_id = c.id
            JOIN tiers_registry t ON p.tier_id = t.id
        """
        df_inv = pd.read_sql_query(sql_inv, conn)
        df_logs = pd.read_sql_query("SELECT id as 'ID', issue_date as 'Timestamp', item_name as 'Item Dispatched', quantity as 'Qty Out', approved_by as 'Approved By', remarks as 'Remarks' FROM issue_log", conn)

    st.subheader("1. Master Inventory Data Backups")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Download Inventory Ledger (CSV)", data=df_inv.to_csv(index=False), file_name="Perfume_Inventory_Ledger.csv", mime="text/csv", use_container_width=True)
    with col2:
        buffer_inv = io.BytesIO()
        with pd.ExcelWriter(buffer_inv, engine='openpyxl') as writer:
            df_inv.to_excel(writer, index=False)
        st.download_button("📥 Download Inventory Ledger (Excel)", data=buffer_inv.getvalue(), file_name="Perfume_Inventory_Ledger.xlsx", mime="application/vnd.ms-excel", use_container_width=True)

    st.subheader("2. Historical Audit Trail Logs Backups")
    col3, col4 = st.columns(2)
    with col3:
        st.download_button("📥 Download Historical Log Logs (CSV)", data=df_logs.to_csv(index=False), file_name="Perfume_Dispatch_Audit_Logs.csv", mime="text/csv", use_container_width=True)
    with col4:
        buffer_logs = io.BytesIO()
        with pd.ExcelWriter(buffer_logs, engine='openpyxl') as writer:
            df_logs.to_excel(writer, index=False)
        st.download_button("📥 Download Historical Log Logs (Excel)", data=buffer_logs.getvalue(), file_name="Perfume_Dispatch_Audit_Logs.xlsx", mime="application/vnd.ms-excel", use_container_width=True)
