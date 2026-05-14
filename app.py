import streamlit as st
import pandas as pd
import time
import random

# --- SESSION MEMORY ---
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
if 'current_build' not in st.session_state:
    st.session_state.current_build = []
if 'permanent_history' not in st.session_state:
    st.session_state.permanent_history = []

st.set_page_config(page_title="Flavor Build", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Data Center")
    inv_file = st.file_uploader("Upload Master Inventory (CSV)", type=['csv'])
    if inv_file:
        st.session_state.inventory_df = pd.read_csv(inv_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        st.success("Inventory Loaded")

    sch_file = st.file_uploader("Upload Daily Schedule (Excel)", type=['xlsx'])
    if sch_file:
        st.session_state.schedule_df = pd.ExcelFile(sch_file)
        st.success("Schedule Loaded")

    if st.session_state.permanent_history:
        st.divider()
        st.header("📥 Export Data")
        
        # FINAL EXPORT MAPPING (Based on your Screenshot)
        export_df = pd.DataFrame(st.session_state.permanent_history)
        # Ensure correct column order for your system
        final_cols = [
            'Build ID*', 'Description', 'Status', 'Product ID', 'Lot ID to produce', 
            'Quantity to produce', 'Start date estimated', 'Start date actual', 
            'Complete date estimated', 'Complete date actual', 'Sublocation', 
            'Consume location', 'Consume sublocation', 'Consume product ID', 'Consume quantity'
        ]
        
        st.download_button(
            label="📊 DOWNLOAD FORMATTED CSV",
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
            
            # --- CALCULATIONS ---
            full_name = str(batch_data['Name']).strip()
            full_code = full_name.split()[0]
            units_to_make = int(batch_data['Qty'])
            
            # Conversion for operator's target oz
            size_prefix = full_code[0]
            if size_prefix == '1': oz_per, label = 0.33814, "10ml"
            elif size_prefix == '3': oz_per, label = 1.01442, "30ml"
            elif size_prefix == '4': oz_per, label = 4.0, "4oz"
            else: oz_per, label = 1.0, "Unknown"

            target_oz = round(units_to_make * oz_per, 4)
            req_base_id = full_code[1:] if len(full_code) >= 5 else full_code
            
            # --- DASHBOARD ---
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Units to Make", f"{units_to_make} bottles")
            c2.metric("📏 Unit Size", label)
            c3.metric("🎯 Target to Pour", f"{target_oz} oz")

            st.divider()
            current_oz = sum(item['Consume quantity'] for item in st.session_state.current_build)
            remaining_oz = round(target_oz - current_oz, 4)
            
            cl, cr = st.columns(2)
            cl.metric("⚖️ Remaining", f"{remaining_oz} oz")
            cr.metric("🧪 Already Logged", f"{current_oz} oz")

            st.warning(f"🛡️ **Safety Lock:** Scan Base ID: **{req_base_id}**")
            sku_scan = st.text_input("Scan Barcode").strip()

            if sku_scan:
                if sku_scan != req_base_id:
                    st.error(f"❌ INCORRECT INGREDIENT! Expected **{req_base_id}**.")
                else:
                    matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]
                    if not matches.empty:
                        col_m, col_i = st.columns([2, 1])
                        with col_m:
                            st.success("✅ Validated")
                            sel_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                            active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                            w1, w2 = st.columns(2)
                            w_before = w1.number_input("Weight BEFORE (oz)", value=float(active['Quantity']))
                            w_after = w2.number_input("Weight AFTER (oz)", value=float(active['Quantity']))
                            
                            if st.button("➕ Log Bottle to Build", use_container_width=True):
                                # Generate Build ID if first bottle, otherwise reuse
                                if not st.session_state.current_build:
                                    st.session_state.new_build_id = int(time.time())
                                
                                st.session_state.current_build.append({
                                    'Build ID*': st.session_state.new_build_id,
                                    'Description': full_name,
                                    'Status': 'Completed',
                                    'Product ID': full_code,
                                    'Lot ID to produce': '',
                                    'Quantity to produce': units_to_make,
                                    'Start date estimated': time.strftime('%m/%d/%Y'),
                                    'Start date actual': time.strftime('%m/%d/%Y'),
                                    'Complete date estimated': time.strftime('%m/%d/%Y'),
                                    'Complete date actual': time.strftime('%m/%d/%Y'),
                                    'Sublocation': 'Bottling',
                                    'Consume location': 'Warehouse', # Example
                                    'Consume sublocation': 'Bottling',
                                    'Consume product ID': req_base_id,
                                    'Consume quantity': round(w_before - w_after, 4)
                                })
                                st.rerun()
                        with col_i:
                            st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)

    # --- FINALIZATION ---
    if st.session_state.current_build:
        st.divider()
        st.subheader("📋 Current Build Progress")
        st.table(pd.DataFrame(st.session_state.current_build)[['Build ID*', 'Consume product ID', 'Consume quantity']])
        if st.button("✅ FINALIZE BATCH", type="primary", use_container_width=True):
            st.session_state.permanent_history.extend(st.session_state.current_build)
            st.session_state.current_build = []
            st.rerun()

    if st.session_state.permanent_history:
        st.divider()
        st.subheader("📜 Running Day Log")
        st.dataframe(pd.DataFrame(st.session_state.permanent_history), use_container_width=True)
