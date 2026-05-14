import streamlit as st
import pandas as pd
import time

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

# --- MAIN INTERFACE ---
st.title("🧪 Flavor Build")

if st.session_state.inventory_df.empty or st.session_state.schedule_df is None:
    st.info("Awaiting Inventory and Schedule uploads...")
else:
    all_tabs = st.session_state.schedule_df.sheet_names
    target_tabs = ['10 List', '30 List', '4oz List']
    relevant_tabs = [t for t in all_tabs if t in target_tabs]
    
    if not relevant_tabs:
        st.error(f"Target tabs not found. Found: {all_tabs}")
    else:
        selected_tab = st.selectbox("Select Bottling Line", relevant_tabs)
        
        # 1. Load the sheet
        df_raw = st.session_state.schedule_df.parse(selected_tab)
        
        # 2. AGGRESSIVE HEADER CLEANING
        # We find the first column that looks like 'Name' and 'Qty'
        name_col = next((c for c in df_raw.columns if "Name" in str(c)), None)
        qty_col = next((c for c in df_raw.columns if "Qty" in str(c)), None)

        if name_col and qty_col:
            # Create a clean version with only the two columns we need
            df_clean = df_raw[[name_col, qty_col]].copy()
            df_clean.columns = ['Name', 'Qty'] # Rename them to standard
            
            # 3. DATA CLEANING
            df_clean = df_clean.dropna(subset=['Name'])
            df_clean['Qty'] = pd.to_numeric(df_clean['Qty'], errors='coerce').fillna(0)
            
            # Filter for active work only
            df_final = df_clean[df_clean['Qty'] > 0].copy()
            
            batch_options = df_final['Name'].unique()
            
            if len(batch_options) == 0:
                st.warning(f"No active batches found on {selected_tab}.")
            else:
                selected_batch = st.selectbox("Select Assigned Batch", batch_options)
                
                batch_data = df_final[df_final['Name'] == selected_batch].iloc[0]
                name_str = str(batch_data['Name']).strip()
                full_code = name_str.split()[0]
                target_qty = float(batch_data['Qty'])
                
                # ID Stripping: 34107 -> 4107
                required_base_id = full_code[1:] if len(full_code) >= 5 else full_code
                
                # --- DASHBOARD ---
                st.divider()
                current_total = sum(item['Used'] for item in st.session_state.current_build)
                remaining = round(target_qty - current_total, 4)
                
                c_t, c_s = st.columns(2)
                c_t.metric("🎯 Target Weight", f"{target_qty}g")
                c_s.metric("⚖️ Remaining to Pour", f"{remaining}g", delta=f"-{current_total}g")

                st.warning(f"🛡️ **Safety Lock:** Scan Base ID: **{required_base_id}**")

                sku_scan = st.text_input("Scan Barcode").strip()

                if sku_scan:
                    if sku_scan != required_base_id:
                        st.error(f"❌ INCORRECT INGREDIENT! Expected **{required_base_id}**, but scanned **{sku_scan}**.")
                    else:
                        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]
                        
                        if not matches.empty:
                            col_m, col_i = st.columns([2, 1])
                            with col_m:
                                st.success("✅ Ingredient Validated")
                                sel_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                                active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                                
                                c1, c2 = st.columns(2)
                                w_before = c1.number_input("Weight BEFORE", value=float(active['Quantity']))
                                w_after = c2.number_input("Weight AFTER", value=float(active['Quantity']))
                                
                                if st.button("➕ Log Bottle to Build", use_container_width=True):
                                    st.session_state.current_build.append({
                                        'Line': selected_tab,
                                        'Batch': full_code,
                                        'Product': selected_batch,
                                        'Base ID': required_base_id,
                                        'Lot ID': sel_lot,
                                        'Used': round(w_before - w_after, 4),
                                        'Time': time.strftime('%H:%M:%S')
                                    })
                                    st.rerun()
                            
                            with col_info:
                                st.subheader("📚 Lot Options")
                                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)
        else:
            st.error(f"Couldn't find 'Name' or 'Qty' columns. Headers seen: {list(df_raw.columns)}")

    # --- REVIEW & HISTORY ---
    if st.session_state.current_build:
        st.divider()
        st.subheader("📋 Current Build Progress")
        st.table(pd.DataFrame(st.session_state.current_build))
        if st.button("✅ FINALIZE BATCH", type="primary", use_container_width=True):
            st.session_state.permanent_history.extend(st.session_state.current_build)
            st.session_state.current_build = []
            st.rerun()

    if st.session_state.permanent_history:
        st.divider()
        st.subheader("📜 Running Day Log")
        st.dataframe(pd.DataFrame(st.session_state.permanent_history), use_container_width=True)
