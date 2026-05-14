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
        st.error(f"Could not find tabs: '10 List', '30 List', or '4oz List'. Found: {all_tabs}")
    else:
        selected_tab = st.selectbox("Select Bottling Line", relevant_tabs)
        
        # Load and clean headers
        current_sheet = st.session_state.schedule_df.parse(selected_tab)
        current_sheet.columns = [str(c).strip() for c in current_sheet.columns]
        
        if 'Name' not in current_sheet.columns or 'Qty' not in current_sheet.columns:
            st.error(f"Sheet '{selected_tab}' is missing 'Name' or 'Qty' columns.")
        else:
            # Filter Qty > 0 and drop empties
            current_sheet['Qty'] = pd.to_numeric(current_sheet['Qty'], errors='coerce')
            current_sheet = current_sheet.dropna(subset=['Name', 'Qty'])
            current_sheet = current_sheet[current_sheet['Qty'] > 0]
            
            batch_options = current_sheet['Name'].unique()
            
            if len(batch_options) == 0:
                st.warning(f"No active batches found on {selected_tab}.")
            else:
                selected_batch = st.selectbox("Select Assigned Batch", batch_options)
                
                # Fetch Data
                batch_data = current_sheet[current_sheet['Name'] == selected_batch].iloc[0]
                full_code = str(batch_data['Name']).split()[0]
                target_qty = float(batch_data['Qty'])
                
                # ID Stripping Logic: 10054 -> 0054
                required_base_id = full_code[1:] if len(full_code) >= 5 else full_code
                
                # --- DASHBOARD ---
                st.divider()
                current_total = sum(item['Used'] for item in st.session_state.current_build)
                remaining = round(target_qty - current_total, 4)
                
                c_t, c_s = st.columns(2)
                c_t.metric("🎯 Target Weight", f"{target_qty}g")
                c_s.metric("⚖️ Remaining to Pour", f"{remaining}g", delta=f"-{current_total}g")

                st.warning(f"🛡️ **Safety Lock Active:** Expected Base ID: **{required_base_id}**")

                sku_scan = st.text_input("Scan Ingredient Barcode").strip()

                if sku_scan:
                    if sku_scan != required_base_id:
                        st.error(f"❌ WRONG INGREDIENT! Expected **{required_base_id}**, scanned **{sku_scan}**.")
                    else:
                        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]
                        
                        if not matches.empty:
                            col_m, col_i = st.columns([2, 1])
                            with col_m:
                                st.success("✅ Ingredient Validated")
                                sel_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                                active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                                
                                c1, c2 = st.columns(2)
                                w_start = c1.number_input("Weight BEFORE", value=float(active['Quantity']))
                                w_end = c2.number_input("Weight AFTER", value=float(active['Quantity']))
                                
                                if st.button("➕ Log Bottle to Build", use_container_width=True):
                                    st.session_state.current_build.append({
                                        'Line': selected_tab,
                                        'Batch Code': full_code,
                                        'Product Name': selected_batch,
                                        'Base ID': required_base_id,
                                        'Lot ID': sel_lot,
                                        'Start': w_start,
                                        'End': w_end,
                                        'Used': round(w_start - w_end, 4),
                                        'Time': time.strftime('%H:%M:%S')
                                    })
                                    st.rerun()
                            
                            with col_info:
                                st.subheader("📚 Lot Options")
                                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)

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
