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

    if st.session_state.permanent_history:
        st.divider()
        st.header("📥 Export Data")
        
        # MAPPING TO YOUR REQUIRED HEADERS
        raw_data = st.session_state.permanent_history
        export_df = pd.DataFrame({
            'Build ID*': [item.get('Build ID*', '') for item in raw_data],
            'Description': [item.get('Description', '') for item in raw_data],
            'Status': [item.get('Status', '') for item in raw_data],
            'Product ID': [item.get('Product ID', '') for item in raw_data],
            'Lot ID to produce': [item.get('Lot ID to produce', '') for item in raw_data],
            'Quantity to produce': [item.get('Quantity to produce', '') for item in raw_data],
            'Start date estimated': [item.get('Start date estimated', '') for item in raw_data],
            'Start date actual': [item.get('Start date actual', '') for item in raw_data],
            'Complete date estimated': [item.get('Complete date estimated', '') for item in raw_data],
            'Complete date actual': [item.get('Complete date actual', '') for item in raw_data],
            'Sublocation': [item.get('Sublocation', '') for item in raw_data],
            'Consume location': [item.get('Consume location', '') for item in raw_data],
            'Consume sublocation': [item.get('Consume sublocation', '') for item in raw_data],
            'Consume product ID': [item.get('Base ID', '') for item in raw_data], # Mapping Base ID here
            'Consume quantity': [item.get('Used (oz)', '') for item in raw_data] # Mapping Used Oz here
        })

        st.download_button(
            label="📊 DOWNLOAD FORMATTED CSV",
            data=export_df.to_csv(index=False).encode('latin1'),
            file_name=f"build_export_{time.strftime('%Y%m%d_%H%M')}.csv",
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
    
    if not relevant_tabs:
        st.error(f"Target tabs not found. Found: {all_tabs}")
    else:
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
            
            if len(batch_options) == 0:
                st.warning(f"No active batches found on {selected_tab}.")
            else:
                selected_batch = st.selectbox("Select Assigned Batch", batch_options)
                batch_data = df_final[df_final['Name'] == selected_batch].iloc[0]
                name_str = str(batch_data['Name']).strip()
                full_code = name_str.split()[0]
                bottles_to_make = float(batch_data['Qty'])
                
                # Conversion Math
                size_prefix = full_code[0]
                if size_prefix == '1': 
                    oz_per_unit, unit_label = 0.33814, "10ml"
                elif size_prefix == '3': 
                    oz_per_unit, unit_label = 1.01442, "30ml"
                elif size_prefix == '4': 
                    oz_per_unit, unit_label = 4.0, "4oz"
                else: 
                    oz_per_unit, unit_label = 1.0, "Unknown"

                target_qty_oz = round(bottles_to_make * oz_per_unit, 4)
                required_base_id = full_code[1:] if len(full_code) >= 5 else full_code
                
                # --- DASHBOARD ---
                st.divider()
                c1, c2, c3 = st.columns(3)
                c1.metric("📦 Units to Make", f"{int(bottles_to_make)} bottles")
                c2.metric("📏 Unit Size", unit_label)
                c3.metric("🎯 Total Target", f"{target_qty_oz} oz")

                st.divider()
                current_total = sum(item['Used (oz)'] for item in st.session_state.current_build)
                remaining = round(target_qty_oz - current_total, 4)
                
                cl, cr = st.columns(2)
                cl.metric("⚖️ Remaining", f"{remaining} oz")
                cr.metric("🧪 Logged", f"{current_total} oz")

                st.warning(f"🛡️ **Safety Lock:** Scan Base ID: **{required_base_id}**")
                sku_scan = st.text_input("Scan Barcode").strip()

                if sku_scan:
                    if sku_scan != required_base_id:
                        st.error(f"❌ INCORRECT INGREDIENT! Expected **{required_base_id}**.")
                    else:
                        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]
                        if not matches.empty:
                            col_m, col_i = st.columns([2, 1])
                            with col_m:
                                st.success("✅ Ingredient Validated")
                                sel_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                                active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                                w1, w2 = st.columns(2)
                                w_before = w1.number_input("Weight BEFORE (oz)", value=float(active['Quantity']))
                                w_after = w2.number_input("Weight AFTER (oz)", value=float(active['Quantity']))
                                
                                if st.button("➕ Log Bottle to Build", use_container_width=True):
                                    st.session_state.current_build.append({
                                        'Base ID': required_base_id,
                                        'Used (oz)': round(w_before - w_after, 4),
                                        'Lot ID to produce': sel_lot, # Placeholder logic
                                        'Quantity to produce': target_qty_oz, # Placeholder logic
                                        # The other headers will stay empty until you explain where they come from
                                    })
                                    st.rerun()
                            with col_i:
                                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)
                        else:
                            st.error(f"Base ID {required_base_id} not found in Inventory.")
        else:
            st.error(f"Couldn't find 'Name' or 'Qty' columns.")

    # --- REVIEW & FINALIZATION ---
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
