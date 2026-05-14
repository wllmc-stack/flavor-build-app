import streamlit as st
import pandas as pd
import time

# --- STATE MANAGEMENT ---
# These keep track of your data while the browser tab is open
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'build_log' not in st.session_state:
    st.session_state.build_log = []

st.set_page_config(page_title="Flavor Build App", layout="wide")

# --- SIDEBAR: LOGISTICS & EXPORT ---
with st.sidebar:
    st.header("📦 Inventory Setup")
    uploaded_file = st.file_uploader("Upload Master List (CSV)", type=['csv'])
    
    if uploaded_file and st.session_state.inventory_df.empty:
        # We use str for IDs to prevent Excel from dropping leading zeros
        df = pd.read_csv(uploaded_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        df.columns = df.columns.str.strip()
        st.session_state.inventory_df = df
        st.success("Master List Loaded")

    # THE BUILD-ONLY EXPORT
    if st.session_state.build_log:
        st.divider()
        st.header("📝 Session Export")
        export_df = pd.DataFrame(st.session_state.build_log)
        
        st.download_button(
            label="📊 Download Build Record",
            data=export_df.to_csv(index=False).encode('latin1'),
            file_name=f"build_report_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Click here to download ONLY the items processed in this session."
        )
        
        if st.button("Undo Last Scan"):
            st.session_state.build_log.pop()
            st.rerun()

# --- MAIN WORK AREA ---
st.title("🧪 Flavor Build Station")

if st.session_state.inventory_df.empty:
    st.info("Awaiting Master List upload in the sidebar...")
else:
    # A reference field so you know which order this data belongs to
    batch_ref = st.text_input("Batch / Order Reference", placeholder="e.g. BATCH-505")
    
    sku_scan = st.text_input("Scan Product ID").strip()

    if sku_scan:
        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]

        if not matches.empty:
            col_main, col_info = st.columns([2, 1])
            
            with col_main:
                st.subheader("🎯 Current Bottle")
                selected_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                active_row = matches[matches['Lot ID'] == selected_lot].iloc[0]
                
                st.info(f"**Description:** {active_row['Description']}")
                
                # We pull the current quantity as the default starting weight
                current_qty = float(active_row['Quantity'])
                
                w_start = st.number_input("Weight BEFORE", value=current_qty)
                w_end = st.number_input("Weight AFTER", value=current_qty)
                
                if st.button("Log this Bottle", type="primary"):
                    st.session_state.build_log.append({
                        'Batch Ref': batch_ref,
                        'Product ID': sku_scan,
                        'Lot ID': selected_lot,
                        'Description': active_row['Description'],
                        'Weight Start': w_start,
                        'Weight End': w_end,
                        'Used': round(w_start - w_end, 4),
                        'Time': time.strftime('%H:%M:%S')
                    })
                    st.toast("Bottle added to session log!")

            with col_info:
                st.subheader("📚 Other Lots")
                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)
        else:
            st.error(f"SKU '{sku_scan}' not found in the master list.")

    # --- THE LIVE BUILD LOG ---
    if st.session_state.build_log:
        st.divider()
        st.subheader("📋 Session Build Log (Items Processed Today)")
        st.table(pd.DataFrame(st.session_state.build_log))
