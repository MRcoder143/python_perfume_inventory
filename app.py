import sqlite3
from datetime import datetime
import io
import pandas as pd
import streamlit as st
import os
import sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# CRITICAL FIX: This locates your database correctly inside the compiled EXE
db_path = get_resource_path("inventory.db")
conn = sqlite3.connect(db_path)

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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT UNIQUE NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tiers_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tier_name TEXT UNIQUE NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT UNIQUE NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                tier_id INTEGER NOT NULL,
                FOREIGN KEY(tier_id) REFERENCES tiers_registry(id) ON DELETE CASCADE,
                UNIQUE(product_name, tier_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS main_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                category_id INTEGER,
                location_id INTEGER,
                total_qty REAL DEFAULT 0,
                usage_qty REAL DEFAULT 0,
                remaining REAL DEFAULT 0,
                unit TEXT,
                reorder_level REAL DEFAULT 10,
                last_updated TEXT,
                FOREIGN KEY(product_id) REFERENCES products_registry(id) ON DELETE CASCADE,
                FOREIGN KEY(category_id) REFERENCES categories_registry(id) ON DELETE CASCADE,
                FOREIGN KEY(location_id) REFERENCES locations_registry(id) ON DELETE CASCADE,
                UNIQUE(product_id, category_id, location_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issue_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_date TEXT,
                item_name TEXT,
                category_name TEXT,
                tier_name TEXT,
                location_name TEXT,
                quantity REAL,
                approved_by TEXT,
                remarks TEXT
            )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM tiers_registry")
        if cursor.fetchone()[0] == 0:
            categories = [("Raw Material",), ("Packaging",), ("Assembled SKU",)]
            cursor.executemany("INSERT OR IGNORE INTO categories_registry (category_name) VALUES (?)", categories)
            
            tiers = [("Standard",), ("Premium",), ("Tester",)]
            cursor.executemany("INSERT OR IGNORE INTO tiers_registry (tier_name) VALUES (?)", tiers)
            
            locations = [("Warehouse Rack A1",), ("Warehouse Rack B5",), ("Retail Showcase",)]
            cursor.executemany("INSERT OR IGNORE INTO locations_registry (location_name) VALUES (?)", locations)
            
            conn.commit()
            
            products = [
                ("Rose Essential Oil", 1),
                ("Ethanol Alcohol 96%", 1),
                ("P11 Cap", 1),
                ("P11 Bottle Base", 1),
                ("P11 Final SKU", 2)
            ]
            cursor.executemany("INSERT OR IGNORE INTO products_registry (product_name, tier_id) VALUES (?, ?)", products)
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            base_stock = [
                (1, 1, 1, 10.0, 0, 10.0, "Liters", 5.0),
                (2, 1, 1, 100.0, 0, 100.0, "Liters", 20.0),
                (3, 2, 2, 500.0, 495.0, 5.0, "Pcs", 50.0),
                (4, 2, 2, 500.0, 0, 500.0, "Pcs", 50.0),
                (5, 3, 3, 50.0, 0, 50.0, "Pcs", 10.0)
            ]
            # FIXED: Properly unrolls items to flat arguments preventing the tuple binding crash
            cursor.executemany("""
                INSERT OR IGNORE INTO main_inventory (product_id, category_id, location_id, total_qty, usage_qty, remaining, unit, reorder_level, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [(b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], now) for b in base_stock])
            
        conn.commit()

def get_db_dicts():
    with sqlite3.connect("inventory.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, category_name FROM categories_registry")
        cats = {r[1]: r[0] for r in cursor.fetchall()}
        cursor.execute("SELECT id, tier_name FROM tiers_registry")
        tiers = {r[1]: r[0] for r in cursor.fetchall()}
        cursor.execute("SELECT id, location_name FROM locations_registry")
        locations = {r[1]: r[0] for r in cursor.fetchall()}
        return cats, tiers, locations

global_db_init()

# =========================================================================
# APPLICATION CONTROL NAV BAR SHELL CONTROLLER
# =========================================================================
st.sidebar.title("💎 Inventory ERP System")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Go To Module:", 
    ["Dashboard Home", "Base Config (Products/Cats/Tiers/Locations)", "Main Inventory Ledger", "Issue Dispatch Logs", "Excel Export Reports"]
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
        total_items = cursor.fetchone()[0] # FIXED: Index unrolls data correctly
        
        cursor.execute("SELECT COUNT(*) FROM main_inventory WHERE remaining <= reorder_level")
        low_stock = cursor.fetchone()[0] # FIXED: Index unrolls data correctly
        
        cursor.execute("SELECT COUNT(*) FROM issue_log")
        total_issues = cursor.fetchone()[0] # FIXED: Index unrolls data correctly
        
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items Managed", int(total_items))
    col2.metric("Low Stock Alerts", int(low_stock), delta=f"-{low_stock}" if low_stock > 0 else "0", delta_color="inverse")
    col3.metric("Total Log Issues Filed", int(total_issues))

# =========================================================================
# MODULE 2: BASE CONFIGS
# =========================================================================
elif page == "Base Config (Products/Cats/Tiers/Locations)":
    st.title("🔧 System Base Parameters Setup")
    
    with sqlite3.connect("inventory.db") as conn:
        col_t, col_p, col_c = st.columns(3)
        
        with col_t:
            st.subheader("Manage Tiers")
            
            # 🛠️ Encapsulate in a form to handle automatic clearing safely
            with st.form("tier_form", clear_on_submit=True):
                t_name = st.text_input("New Tier Label Name")
                submit_tier = st.form_submit_button("Register Tier")
                
                if submit_tier:
                    if t_name.strip():
                        try:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO tiers_registry (tier_name) VALUES (?)", (t_name.strip(),))
                            conn.commit()
                            st.success(f"Registered Tier: {t_name.strip()}")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("This tier label already exists.")
                    else:
                        st.warning("Tier name field cannot be blank.")


                    
            df_t = pd.read_sql_query("SELECT id as 'ID', tier_name as 'Tier Name' FROM tiers_registry", conn)
            st.dataframe(df_t, use_container_width=True, hide_index=True, height=180)
            
            t_to_del = st.selectbox("Choose tier to drop:", [""] + list(df_t['Tier Name'].values), key="del_t_select")
            if st.button("Delete Tier", key="red_btn_tier"):
                if t_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tiers_registry WHERE tier_name = ?", (t_to_del,))
                    conn.commit()
                    st.rerun()

        with col_p:
            st.subheader("Manage Products")
            p_tier_choice = st.selectbox("Assign Product to Tier:", [""] + list(df_t['Tier Name'].values), key="prod_tier_assign")
            p_name = st.text_input("New Product Label Name", key="add_p")
            
            if st.button("Register Product", key="green_btn_prod"):
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
                        st.error("This product label already exists inside this tier.")
            
            df_p = pd.read_sql_query("""
                SELECT p.id as 'ID', p.product_name as 'Product Name', t.tier_name as 'Belongs to Tier' 
                FROM products_registry p
                JOIN tiers_registry t ON p.tier_id = t.id
            """, conn)
            st.dataframe(df_p, use_container_width=True, hide_index=True, height=180)
            
            p_to_del = st.selectbox("Choose product to drop:", [""] + list(df_p['Product Name'].values), key="del_p_select")
            if st.button("Delete Product", key="red_btn_prod"):
                if p_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM products_registry WHERE product_name = ?", (p_to_del,))
                    conn.commit()
                    st.rerun()

        with col_c:
            st.subheader("Manage Categories")
            c_name = st.text_input("New Category Label Name", key="add_c")
            if st.button("Register Category", key="green_btn_cat"):
                if c_name.strip():
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO categories_registry (category_name) VALUES (?)", (c_name.strip(),))
                        conn.commit()
                        st.success(f"Registered: {c_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("This category label already exists.")
                    
            df_c = pd.read_sql_query("SELECT id as 'ID', category_name as 'Category Name' FROM categories_registry", conn)
            st.dataframe(df_c, use_container_width=True, hide_index=True, height=180)
            
            c_to_del = st.selectbox("Choose category to drop:", [""] + list(df_c['Category Name'].values), key="del_c_select")
            if st.button("Delete Category", key="red_btn_cat"):
                if c_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM categories_registry WHERE category_name = ?", (c_to_del,))
                    conn.commit()
                    st.rerun()

        # ---- LOCATIONS SECTION ----
        st.markdown("---")
        st.subheader("📍 Warehouse Locations & Rack Management")
        col_l1, col_l2 = st.columns(2)
        
        with col_l1:
            l_name = st.text_input("New Warehouse Location / Rack Name", key="add_l")
            if st.button("Register Location", key="green_btn_loc"):
                if l_name.strip():
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO locations_registry (location_name) VALUES (?)", (l_name.strip(),))
                        conn.commit()
                        st.success(f"Registered Warehouse Slot: {l_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("This storage layout destination already exists.")
                        
            df_l = pd.read_sql_query("SELECT id as 'ID', location_name as 'Warehouse Location' FROM locations_registry", conn)
            
            l_to_del = st.selectbox("Choose location to delete:", [""] + list(df_l['Warehouse Location'].values), key="del_l_select")
            if st.button("Delete Location", key="red_btn_loc"):
                if l_to_del:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM locations_registry WHERE location_name = ?", (l_to_del,))
                    conn.commit()
                    st.success("Storage location dropped successfully!")
                    st.rerun()
                    
        with col_l2:
            st.markdown("**Active Storage Mapping Registries Ledger**")
            st.dataframe(df_l, use_container_width=True, hide_index=True, height=220)

# =========================================================================
# MODULE 3: MAIN INVENTORY LEDGER
# =========================================================================
elif page == "Main Inventory Ledger":
    st.title("📦 Master Inventory Control Ledger")
    
    cats, tiers, locations = get_db_dicts()
    form_col, table_col = st.columns(2)
    
    # =========================================================================
    # SIDE A: TABLE MONITORING GRID (MOVED FIRST TO TRACK USER CLICKS)
    # =========================================================================
    with table_col:
        st.subheader("Live Operational Inventory Monitoring Grid")
        search_query = st.text_input("🔍 Live Grid Search:", placeholder="Type name, category, tier, or location string to filter...")
        
        # FIXED: Uses your global db_path tracking safety variable
        with sqlite3.connect(db_path) as conn:
            sql = """
                SELECT p.product_name as 'Item Name', c.category_name as 'Category Group', t.tier_name as 'Tier Level', l.location_name as 'Warehouse Location',
                       m.total_qty as 'Total In', m.usage_qty as 'Total Out', m.remaining as 'In Stock', 
                       m.unit as 'Unit', m.reorder_level as 'Alert Threshold', m.last_updated as 'Last Updated'
                FROM main_inventory m
                JOIN products_registry p ON m.product_id = p.id
                JOIN categories_registry c ON m.category_id = c.id
                JOIN tiers_registry t ON p.tier_id = t.id
                JOIN locations_registry l ON m.location_id = l.id
            """
            df = pd.read_sql_query(sql, conn)
        
        if search_query:
            df = df[
                df['Item Name'].str.contains(search_query, case=False) | 
                df['Category Group'].str.contains(search_query, case=False) |
                df['Tier Level'].str.contains(search_query, case=False) |
                df['Warehouse Location'].str.contains(search_query, case=False)
            ]
            
        def highlight_low_stock(row):
            return ['background-color: #FFD2D2; color: #A94442' if row['In Stock'] <= row['Alert Threshold'] else '' for _ in row]
            
        # FIXED: Added live selection monitoring configuration to the dataframe view
        selection_event = st.dataframe(
            df.style.apply(highlight_low_stock, axis=1), 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="inventory_live_grid"
        )
        
               # Pull selection indices from the user grid interaction cache
        selected_rows = selection_event.get("selection", {}).get("rows", [])
        
        # Initialize form placeholder defaults
        default_tier = ""
        default_prod = ""
        default_cat = ""
        default_loc = ""
        default_tot = 0.0
        default_usg = 0.0
        default_unit = "Pcs"
        default_reorder = 10.0
        
        # 👑 CRITICAL BUGFIX: Ensure selected_rows is NOT empty and contains a valid index integer
        if selected_rows and len(selected_rows) > 0:
            # Safely extract the first integer from the selection array list
            row_idx = selected_rows[0]
            
            # Check to make sure the selected index is actually inside our current dataframe bounds
            if row_idx < len(df):
                clicked_row = df.iloc[row_idx]
                
                # Map selected text back to your dropdown default variables safely
                default_tier = clicked_row['Tier Level']
                default_prod = clicked_row['Item Name']
                default_cat = clicked_row['Category Group']
                default_loc = clicked_row['Warehouse Location']
                default_tot = float(clicked_row['Total In'])
                default_usg = float(clicked_row['Total Out'])
                default_unit = str(clicked_row['Unit'])
                default_reorder = float(clicked_row['Alert Threshold'])


    # =========================================================================
    # SIDE B: INVENTORY ACTION CONTROLS FORM (WITH SELECTION AUTOFILL)
    # =========================================================================
    with form_col:
        st.subheader("Inventory Action Controls")
        
        # Calculate selected tier index fallback position
        tier_list = [""] + list(tiers.keys())
        tier_index = tier_list.index(default_tier) if default_tier in tier_list else 0
        
        selected_tier = st.selectbox("Select Filter Tier Level:", tier_list, index=tier_index, key="inv_tier_select")
        
        available_products = {}
        if selected_tier:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, product_name FROM products_registry WHERE tier_id = ?", (tiers[selected_tier],))
                available_products = {r[1]: r[0] for r in cursor.fetchall()}
        
        prod_list = [""] + list(available_products.keys())
        prod_index = prod_list.index(default_prod) if default_prod in prod_list else 0
        
        selected_prod = st.selectbox("Select Target Product Name:", prod_list, 
                                     index=prod_index,
                                     disabled=not selected_tier, 
                                     key="inv_prod_select",
                                     help="Choose a tier level above first to unlock products list.")
        
        cat_list = [""] + list(cats.keys())
        cat_index = cat_list.index(default_cat) if default_cat in cat_list else 0
        selected_cat = st.selectbox("Select Target Category Group:", cat_list, index=cat_index, key="inv_cat_select")
        
        loc_list = [""] + list(locations.keys())
        loc_index = loc_list.index(default_loc) if default_loc in loc_list else 0
        selected_loc = st.selectbox("Select Storage Location Dropdown:", loc_list, index=loc_index, key="inv_loc_select")
        
        val_tot = st.number_input("Total Quantity Inbound:", min_value=0.0, value=default_tot)
        val_usg = st.number_input("Total Quantity Used Out:", min_value=0.0, value=default_usg)
        val_unit = st.text_input("Unit Measure Label:", value=default_unit)
        val_reorder = st.number_input("Low Stock Safety Threshold Alert:", min_value=0.0, value=default_reorder)
        
        if selected_rows:
            st.info(f"👉 Active Selection Locked: **{selected_prod}** inside **{selected_loc}**.")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Save/Add Entry", use_container_width=True, key="green_btn_save_ledger"):
                if selected_prod and selected_cat and selected_tier and selected_loc:
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        rem = val_tot - val_usg
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        try:
                            cursor.execute("""
                                INSERT INTO main_inventory (product_id, category_id, location_id, total_qty, usage_qty, remaining, unit, reorder_level, last_updated)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(product_id, category_id, location_id) DO UPDATE SET
                                    total_qty = total_qty + excluded.total_qty,
                                    usage_qty = usage_qty + excluded.usage_qty,
                                    remaining = (total_qty + excluded.total_qty) - (usage_qty + excluded.usage_qty),
                                    last_updated = excluded.last_updated,
                                    unit = excluded.unit,
                                    reorder_level = excluded.reorder_level
                            """, (available_products[selected_prod], cats[selected_cat], locations[selected_loc], val_tot, val_usg, rem, val_unit, val_reorder, now))
                            conn.commit()
                            st.success(f"Inventory saved successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database Error: {e}")
                else:
                    st.warning("Please fill out Tier, Product, Category, and Location completely.")
                    
        with col_btn2:
            if st.button("Update Existing", use_container_width=True, key="blue_btn_update_ledger"):
                if selected_prod and selected_cat and selected_tier and selected_loc:
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        rem = val_tot - val_usg
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        cursor.execute("""
                            UPDATE main_inventory SET total_qty=?, usage_qty=?, remaining=?, unit=?, reorder_level=?, last_updated=?
                            WHERE product_id=? AND category_id=? AND location_id=?
                        """, (val_tot, val_usg, rem, val_unit, val_reorder, now, available_products[selected_prod], cats[selected_cat], locations[selected_loc]))
                        conn.commit()
                        st.success("Record modified successfully!")
                        st.rerun()
                        
            if st.button("Delete Stock Mapping Relationship Row", use_container_width=True, key="red_btn_delete_ledger"):
            # 1. Check if a row has actually been highlighted in the grid cache
             if selected_rows:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    
                    # 2. Get the exact text names straight from the highlighted row dataframe
                    row_idx = selected_rows[0] if isinstance(selected_rows, list) else selected_rows
                    clicked_row = df.iloc[row_idx]
                    
                    p_name = clicked_row['Item Name']
                    c_name = clicked_row['Category Group']
                    l_name = clicked_row['Warehouse Location']
                    
                    # 3. Query the precise IDs directly from the database registries
                    cursor.execute("SELECT id FROM products_registry WHERE product_name = ?", (p_name,))
                    p_res = cursor.fetchone()
                    
                    cursor.execute("SELECT id FROM categories_registry WHERE category_name = ?", (c_name,))
                    c_res = cursor.fetchone()
                    
                    cursor.execute("SELECT id FROM locations_registry WHERE location_name = ?", (l_name,))
                    l_res = cursor.fetchone()
                    
                    # 4. If all IDs match, run the safe deletion transaction immediately
                    if p_res and c_res and l_res:
                        prod_id = p_res[0]
                        cat_id = c_res[0]
                        loc_id = l_res[0]
                        
                        cursor.execute("""
                            DELETE FROM main_inventory 
                            WHERE product_id=? AND category_id=? AND location_id=?
                        """, (prod_id, cat_id, loc_id))
                        
                        conn.commit()
                        st.toast(f"🗑️ Relationship for '{p_name}' dropped successfully!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Registry Matching Failed: Could not map data columns back to true relational database IDs.")
        

# =========================================================================
# MODULE 4: AUDITED OUTWARD DISPATCH ISSUE TRACKING
# =========================================================================
elif page == "Issue Dispatch Logs":
    st.title("📋 Audit Dispatch Issue Tracking Log")
    form_col, table_col = st.columns(2)
    
    cats, tiers, locations = get_db_dicts()
    
    with form_col:
        st.subheader("Log Outward Dispatch Row")
        
        log_tier = st.selectbox("Select Filter Tier Level:", [""] + list(tiers.keys()), key="log_tier_select")
        
        log_products = {}
        if log_tier:
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT p.id, p.product_name 
                    FROM main_inventory m
                    JOIN products_registry p ON m.product_id = p.id
                    WHERE p.tier_id = ?
                """, (tiers[log_tier],))
                log_products = {r[1]: r[0] for r in cursor.fetchall()}
        
        selected_log_prod = st.selectbox("Select Target Product Name:", [""] + list(log_products.keys()),
                                         disabled=not log_tier,
                                         key="log_prod_select")
        
        log_categories = {}
        if selected_log_prod:
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT c.id, c.category_name 
                    FROM main_inventory m
                    JOIN categories_registry c ON m.category_id = c.id
                    WHERE m.product_id = ?
                """, (log_products[selected_log_prod],))
                log_categories = {r[1]: r[0] for r in cursor.fetchall()}
                
        selected_log_cat = st.selectbox("Select Target Category Group:", [""] + list(log_categories.keys()),
                                         disabled=not selected_log_prod,
                                         key="log_cat_select")
        
        log_locations = {}
        if selected_log_prod and selected_log_cat:
            with sqlite3.connect("inventory.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT l.id, l.location_name 
                    FROM main_inventory m
                    JOIN locations_registry l ON m.location_id = l.id
                    WHERE m.product_id = ? AND m.category_id = ?
                """, (log_products[selected_log_prod], log_categories[selected_log_cat]))
                log_locations = {r[1]: r[0] for r in cursor.fetchall()}
                
        selected_log_loc = st.selectbox("Select Storage Location Dispatch Target Dropdown:", [""] + list(log_locations.keys()),
                                         disabled=not selected_log_cat,
                                         key="log_loc_select")

        i_qty = st.number_input("Quantity Outbound:", min_value=0.0, value=0.0)
        i_appr = st.text_input("Approved By Signature:")
        i_rem = st.text_input("Operational Remarks:")
        
        if st.button("Execute Stock-Out Transaction", use_container_width=True, key="green_btn_execute_dispatch"):
            if selected_log_prod and selected_log_cat and selected_log_loc and i_appr and i_qty > 0:
                with sqlite3.connect("inventory.db") as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT id, remaining, usage_qty 
                        FROM main_inventory 
                        WHERE product_id = ? AND category_id = ? AND location_id = ?
                    """, (log_products[selected_log_prod], log_categories[selected_log_cat], locations[selected_log_loc]))
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
                            
                            cursor.execute("""
                                INSERT INTO issue_log (issue_date, item_name, category_name, tier_name, location_name, quantity, approved_by, remarks) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (now, selected_log_prod, selected_log_cat, log_tier, selected_log_loc, i_qty, i_appr, i_rem if i_rem else "N/A"))
                            
                            conn.commit()
                            st.success(f"Stock-out processed successfully from {selected_log_loc}!")
                            st.rerun()
                        else:
                            st.error(f"Insufficient stock to complete dispatch. Balance at this rack is: {remaining}")
                    else:
                        st.error("No active stock records exist matching this specific item configuration.")
            else:
                st.warning("Please complete all dropdown choices, signature, and quantity inputs completely.")

    with table_col:
        st.subheader("Historical Dispatch Audit Trails Ledger")
        with sqlite3.connect("inventory.db") as conn:
            df_log = pd.read_sql_query("""
                SELECT id as 'ID', issue_date as 'Timestamp', item_name as 'Item Name', 
                       category_name as 'Category', tier_name as 'Tier', location_name as 'Location Slot', 
                       quantity as 'Qty Out', approved_by as 'Approved By', remarks as 'Remarks' 
                FROM issue_log
            """, conn)
        st.dataframe(df_log, use_container_width=True, hide_index=True)

# =========================================================================
# MODULE 5: EXCEL/CSV DATA EXPORT REPORTS 
# =========================================================================
elif page == "Excel Export Reports":
    st.title("📊 Excel & CSV Report Generation Workspace")
    st.markdown("Download backups of your live inventory transaction ledgers and audit historical logs.")
    
    with sqlite3.connect("inventory.db") as conn:
        sql_inv = """
            SELECT p.product_name as 'Item Name', c.category_name as 'Category Group', t.tier_name as 'Tier Level', l.location_name as 'Warehouse Location',
                   m.total_qty as 'Total In', m.usage_qty as 'Total Out', m.remaining as 'In Stock', 
                   m.unit as 'Unit', m.reorder_level as 'Alert Threshold', m.last_updated as 'Last Updated'
            FROM main_inventory m
            JOIN products_registry p ON m.product_id = p.id
            JOIN categories_registry c ON m.category_id = c.id
            JOIN tiers_registry t ON p.tier_id = t.id
            JOIN locations_registry l ON m.location_id = l.id
        """
        df_inv = pd.read_sql_query(sql_inv, conn)
        df_logs = pd.read_sql_query("""
            SELECT id as 'ID', issue_date as 'Timestamp', item_name as 'Item Name', 
                   category_name as 'Category', tier_name as 'Tier', location_name as 'Location Slot', 
                   quantity as 'Qty Out', approved_by as 'Approved By', remarks as 'Remarks' 
            FROM issue_log
        """, conn)

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
