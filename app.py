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

st.set_page_config(page_title="Flavor Build Station", layout="wide")

# --- SIDEBAR: LOGISTICS ---
with st.sidebar:
    st.header("📂 Data Center")
    
    # 1. Master Inventory
    inv_file = st.file_uploader("Upload Master Inventory (CSV)", type=['csv'])
    if inv_file and st.session_state.inventory_df.empty:
        df = pd.read_csv(inv_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        st.session_state.inventory_df = df
        st.success("Inventory Ready")

    # 2. Daily Schedule (The Excel Multi-Tab file)
    sch_file = st.file_uploader("Upload Daily Schedule (Excel)", type=['xlsx'])
    if sch_file:
        st.session_state.schedule_df = pd.ExcelFile(sch_file)
        st.success("Schedule Ready")

    if st.session_state.permanent_history:
        st.divider()
        st.download_button(
            label="📥 DOWNLOAD SESSION LOG",
            data=pd.DataFrame(st.session_state.permanent_history).to_csv(index=False).encode('latin1'),
            file_name=f"session_history_{time.strftime('%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# --- MAIN INTERFACE ---
st.title("🧪 Guided Flavor Build")

if st.session_state.inventory_df.empty or st.session_state.schedule_df is None:
    st.info("Awaiting both Inventory (CSV) and Daily Schedule (Excel) uploads in the sidebar.")
else:
    # 1. LINE SELECTION (Tabs from your Excel)
    available_tabs = [sheet for sheet in st.session_state.schedule_df.sheet_names if sheet in ['10 List', '30List', '4oz List']]
    selected_tab = st.selectbox("Select Bottling Line", available_tabs)
    
    # Load the specific sheet
    current_sheet = st.session_state.schedule_df.parse(selected_tab)
    current_sheet.columns = current_sheet.columns.str.strip()
    
    # 2. BATCH SELECTION
    # We assume 'Name' contains the 5-digit ID + Flavor Name
    batch_options = current_sheet['Name'].unique()
    selected_batch = st.selectbox("Select Assigned Batch", batch_options)
    
    # 3. SMART LOGIC: Extract Base ID and Target Qty
    batch_data = current_sheet[current_sheet['Name'] == selected_batch].iloc[0]
    full_code = str(batch_data['Name']).split()[0]  # Extracts the 10054 part
    target_qty = float(batch_data['Qty'])
    
    # STRIP THE FIRST DIGIT: 10054 -> 0054
    required_base_id = full_code[1:] if len(full_code) >= 5 else full_code
    
    # 4. DASHBOARD VIEW
    st.divider()
    col_target, col_status = st.columns(2)
    
    # Calculate progress
    current_total = sum(item['Used'] for item in st.session_state.current_build)
    remaining = max(0.0, target_qty - current_total)
    
    with col_target:
        st.metric("🎯 Target for this Batch", f"{target_qty}g")
    with col_status:
        st.metric("⚖️ Remaining to Pour", f"{remaining}g", delta=f"-{current_total}g")

    st.warning(f"🛡️ **Safety Lock Active:** Scanning restricted to Base ID: **{required_base_id}**")

    # 5. SCAN & VALIDATE
    sku_scan = st.text_input("Scan Ingredient Barcode").strip()

    if sku_scan:
        # THE SAFETY LOCK CHECK
        if sku_scan != required_base_id:
            st.error(f"❌ WRONG INGREDIENT! This batch requires Base **{required_base_id}**, but you scanned **{sku_scan}**.")
        else:
            matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]
            
            if not matches.empty:
                col_main, col_info = st.columns([2, 1])
                with col_main:
                    st.success("✅ Ingredient Validated")
                    sel_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                    active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                    
                    c1, c2 = st.columns(2)
                    with c1: w_start = st.number_input("Weight BEFORE", value=float(active['Quantity']))
                    with c2: w_end = st.number_input("Weight AFTER", value=float(active['Quantity']))
                    
                    if st.button("➕ Log Bottle to Build", type="secondary", use_container_width=True):
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
            else:
                st.error("SKU found in schedule, but no matching Lot IDs found in Inventory.")

    # 6. BUILD REVIEW & FINALIZATION
    if st.session_state.current_build:
        st.divider()
        st.subheader("📋 Current Build Progress")
        st.table(pd.DataFrame(st.session_state.current_build))
        
        if st.button("✅ FINALIZE BATCH & CLEAR SCREEN", type="primary", use_container_width=True):
            st.session_state.permanent_history.extend(st.session_state.current_build)
            st.session_state.current_build = []
            st.success("Batch finalized!")
            st.rerun()

    # 7. MASTER LOG
    if st.session_state.permanent_history:
        st.divider()
        st.subheader("📜 Running Day Log")
        st.dataframe(pd.DataFrame(st.session_state.permanent_history), use_container_width=True)
