import streamlit as st
import pandas as pd
import time

# --- STATE MANAGEMENT ---
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
        df = pd.read_csv(uploaded_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        df.columns = df.columns.str.strip()
        st.session_state.inventory_df = df
        st.success("Master List Ready")

    # THE BUILD-ONLY EXPORT: This is the specific "Transaction Record"
    if st.session_state.build_log:
        st.divider()
        st.header("📝 Session Export")
        export_df = pd.DataFrame(st.session_state.build_log)
        
        st.download_button(
            label="📊 Download Build Record",
            data=export_df.to_csv(index=False).encode('latin1'),
            file_name=f"batch_report_{time.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        if st.button("Clear Session"):
            st.session_state.build_log = []
            st.rerun()

# --- MAIN WORK AREA ---
st.title("🧪 Flavor Build Station")

if st.session_state.inventory_df.empty:
    st.warning("Awaiting Master List upload...")
else:
    # Optional Batch Identifier to tag the entire export
    batch_ref = st.text_input("Batch / Project Reference", placeholder="e.g. Order #4451")
    
    sku_scan = st.text_input("Scan Product ID Barcode").strip()

    if sku_scan:
        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]

        if not matches.empty:
            col_main, col_info = st.columns([2, 1])
            
            with col_main:
                st.subheader("🎯 Current Bottle")
                selected_lot = st.selectbox("Select Lot ID", matches['Lot ID'].unique())
                active_row = matches[matches['Lot ID'] == selected_lot].iloc[0]
                
                st.info(f"**Description:** {active_row['Description']}")
                current_qty = float(active_row['Quantity'])
                
                # Weight Entry
                w_start = st.number_input("Weight BEFORE", value=current_qty)
                w_end = st.number_input("Weight AFTER", value=current_qty)
                
                if st.button("Log Usage", type="primary"):
                    st.session_state.build_log.append({
                        'Batch Ref': batch_ref,
                        'Product ID': sku_scan,
                        'Lot ID': selected_lot,
                        'Description': active_row['Description'],
                        'Weight Start': w_start,
                        'Weight End': w_end,
                        'Qty Consumed': round(w_start - w_end, 4),
                        'Time': time.strftime('%H:%M:%S')
                    })
                    st.toast("Bottle logged to Batch Record")

            with col_info:
                st.subheader("📚 Other Lots")
                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)
        else:
            st.error(f"SKU {sku_scan} not found.")

    # --- THE LIVE BUILD LOG ---
    if st.session_state.build_log:
        st.divider()
        st.subheader("📋 Items in Current Build")
        st.table(pd.DataFrame(st.session_state.build_log))
