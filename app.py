import streamlit as st
import pd as pd
import time
import random

# --- 1. USER DATABASE ---
USER_DB = {
    "Admin": "1234",
    "Mike": "5678",
    "Sarah": "9012",
    "Production_Station_1": "bottling2024"
}

# --- SESSION MEMORY ---
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
if 'current_build' not in st.session_state:
    st.session_state.current_build = []
if 'permanent_history' not in st.session_state:
    st.session_state.permanent_history = []
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

st.set_page_config(page_title="Flavor Build", layout="wide")

# --- LOGIN SCREEN ---
if not st.session_state.authenticated:
    st.title("🔐 Flavor Build Login")
    with st.container(border=True):
        user = st.selectbox("Select Your Name", list(USER_DB.keys()))
        password = st.text_input("Enter Password", type="password")
        
        if st.button("Log In", use_container_width=True):
            if USER_DB.get(user) == password:
                st.session_state.authenticated = True
                st.session_state.user_name = user
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop() 

# --- SIDEBAR ---
with st.sidebar:
    st.success(f"✅ User: **{st.session_state.user_name}**")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()
    
    st.divider()
    st.header("📂 Data Center")
    inv_file = st.file_uploader("Upload Inventory (CSV)", type=['csv'])
    if inv_file:
        st.session_state.inventory_df = pd.read_csv(inv_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')

    sch_file = st.file_uploader("Upload Schedule (Excel)", type=['xlsx'])
    if sch_file:
        st.session_state.schedule_df = pd.ExcelFile(sch_file)

    if st.session_state.permanent_history:
        st.divider()
        st.header("📥 Export Data")
        export_df = pd.DataFrame(st.session_state.permanent_history)
        
        # HEADERS UPDATED: "Product ID to produce" 
        final_cols = [
            'Build ID', 'Description', 'Status', 'Product ID to produce', 'Lot ID to produce', 
            'Quantity to produce', 'Start date estimated', 'Start date actual', 
            'Complete date estimated', 'Complete date actual', 'Sublocation', 
            'Consume location', 'Consume sublocation', 'Consume product ID', 'Consume quantity'
        ]
        
        st.download_button(
            label="📊 DOWNLOAD CSV",
            data=export_df[final_cols].to_csv(index=False).encode('latin1'),
            file_name=f"flavor_build_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )
        
        if st.button("Clear History"):
            st.session_state.permanent_history = []
            st.rerun()

# --- MAIN INTERFACE ---
st.title("🧪 Flavor Build")

if st.session_state.inventory_df.empty or st.session_state.schedule_df is None:
    st.info("Awaiting Inventory and Schedule uploads...")
else:
    all_tabs = st.session_state.schedule_df.sheet_names
    target_tabs = ['10 List', '30 List', '4oz List']
    relevant_tabs = [t for t in all_tabs if t in target_tabs]
    
    selected_tab = st.selectbox("Select Bottling Line", relevant_tabs)
    df_raw = st.session_state.schedule_df.parse(selected_tab)
    
    name_col = next((c for c in df_raw.columns if "Name" in str(c)), None)
    qty_col = next((c for c in df_raw.columns if "Qty" in str(c)), None)

    if name_col and qty_col:
        df_clean = df_raw[[name_col, qty_col]].copy()
        df_clean.columns = ['Name', 'Qty']
        df_clean = df_clean.dropna(subset=['Name'])
        df_clean['Qty'] = pd.to_numeric(df_clean['Qty'], errors='coerce').fillna(0)
        df_final = df_clean[df_clean['Qty'] > 0].copy()
        
        batch_options = df_final['Name'].unique()
        
        if len(batch_options) > 0:
            selected_batch = st.selectbox("Select Assigned Batch", batch_options)
            batch_data = df_final[df_final['Name'] == selected_batch].iloc[0]
            
            full_name = str(batch_data['Name']).strip()
            full_code = full_name.split()[0]
            planned_qty = int(batch_data['Qty'])
            
            # Conv math for Operator only
            prefix = full_code[0]
            if prefix == '1': oz_per, label = 0.33814, "10ml"
            elif prefix == '3': oz_per, label = 1.01442, "30ml"
            elif prefix == '4': oz_per, label = 4.0, "4oz"
            else: oz_per, label = 1.0, "Unknown"

            target_oz = round(planned_qty * oz_per, 4)
            req_base_id = full_code[1:] if len(full_code) >= 5 else full_code
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Planned Units", f"{planned_qty}")
            c2.metric("📏 Unit Size", label)
            c3.metric("🎯 Target Oz", f"{target_oz} oz")

            current_oz = sum(item['Consume quantity'] for item in st.session_state.current_build)
            remaining_oz = round(target_oz - current_oz, 4)
            
            cl, cr = st.columns(2)
            cl.metric("⚖️ Remaining", f"{remaining_oz} oz")
            cr.metric("🧪 Logged", f"{current_oz} oz")

            st.warning(f"🛡️ **Safety Lock:** Scan Base ID: **{req_base_id}**")
            sku_scan = st.text_input("Scan Barcode").strip()

            if sku_scan:
                if sku_scan != req_base_id:
                    st.error(f"❌ Incorrect ID: Expected **{req_base_id}**.")
                else:
                    matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]
                    if not matches.empty:
                        col_m, col_i = st.columns([2, 1])
                        with col_m:
                            st.success("✅ Validated")
                            sel_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                            active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                            w_before = st.number_input("Weight BEFORE", value=float(active['Quantity']))
                            w_after = st.number_input("Weight AFTER", value=float(active['Quantity']))
                            
                            if st.button("➕ Log Bottle", use_container_width=True):
                                if not st.session_state.current_build:
                                    # RANDOM 6 DIGIT ID
                                    st.session_state.new_build_id = random.randint(100000, 999999)
                                
                                st.session_state.current_build.append({
                                    'Build ID': st.session_state.new_build_id,
                                    'Description': f"{full_name} - {st.session_state.user_name}",
                                    'Status': 'Completed',
                                    'Product ID to produce': full_code, # Updated Header
                                    'Lot ID to produce': '',
                                    'Quantity to produce': 0, # Placeholder, filled at finalization
                                    'Start date estimated': time.strftime('%m/%d/%Y'),
                                    'Start date actual': time.strftime('%m/%d/%Y'),
                                    'Complete date estimated': time.strftime('%m/%d/%Y'),
                                    'Complete date actual': time.strftime('%m/%d/%Y'),
                                    'Sublocation': 'Bottling',
                                    'Consume location': 'Bottling',
                                    'Consume sublocation': 'Bottling',
                                    'Consume product ID': req_base_id,
                                    'Consume quantity': round(w_before - w_after, 4)
                                })
                                st.rerun()
                        with col_i:
                            st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)

# --- REVIEW & FINALIZATION ---
if st.session_state.current_build:
    st.divider()
    st.subheader("📋 Finalize Build")
    
    # NEW: Manual Entry for Actual Quantity Produced
    final_units = st.number_input("Actual Units Produced (Final Count)", value=int(st.session_state.current_build[0]['Quantity to produce']) or planned_qty)
    
    if st.button("✅ FINALIZE & SAVE BATCH", type="primary", use_container_width=True):
        # Apply the manual count to all rows in this build
        for item in st.session_state.current_build:
            item['Quantity to produce'] = final_units
            
        st.session_state.permanent_history.extend(st.session_state.current_build)
        st.session_state.current_build = []
        st.success("Batch Saved to Log!")
        st.rerun()

if st.session_state.permanent_history:
    st.divider()
    st.subheader("📜 Running Day Log")
    st.dataframe(pd.DataFrame(st.session_state.permanent_history), use_container_width=True)
