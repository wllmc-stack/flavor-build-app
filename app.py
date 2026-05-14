import streamlit as st
import pandas as pd
import time

# --- SESSION MEMORY ---
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'build_log' not in st.session_state:
    st.session_state.build_log = []
# This tracks if we just finished a bottle to help clear the scanner
if 'last_scan' not in st.session_state:
    st.session_state.last_scan = ""

st.set_page_config(page_title="Flavor Build App", layout="wide")

# --- SIDEBAR: EXPORT ONLY ---
with st.sidebar:
    st.header("📦 Inventory Setup")
    uploaded_file = st.file_uploader("Upload Master List (CSV)", type=['csv'])
    
    if uploaded_file and st.session_state.inventory_df.empty:
        df = pd.read_csv(uploaded_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        df.columns = df.columns.str.strip()
        st.session_state.inventory_df = df

    if st.session_state.build_log:
        st.divider()
        st.header("📝 Session Export")
        export_df = pd.DataFrame(st.session_state.build_log)
        st.download_button(
            label="📊 Download Build Report",
            data=export_df.to_csv(index=False).encode('latin1'),
            file_name=f"build_report_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        if st.button("Undo Last Entry"):
            st.session_state.build_log.pop()
            st.rerun()

# --- MAIN WORK AREA ---
st.title("🧪 Flavor Build Station")

if st.session_state.inventory_df.empty:
    st.info("Please upload your Master List in the sidebar.")
else:
    batch_ref = st.text_input("Batch / Order Reference", placeholder="e.g. BATCH-505")
    
    # We use a key here so we can clear it programmatically
    sku_scan = st.text_input("Scan Product ID", key="barcode_input").strip()

    if sku_scan:
        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]

        if not matches.empty:
            col_main, col_info = st.columns([2, 1])
            
            with col_main:
                st.subheader("🎯 Active Bottle")
                selected_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                active_row = matches[matches['Lot ID'] == selected_lot].iloc[0]
                
                st.info(f"**Description:** {active_row['Description']}")
                
                current_qty = float(active_row['Quantity'])
                w_start = st.number_input("Weight BEFORE", value=current_qty)
                w_end = st.number_input("Weight AFTER", value=current_qty)
                
                # THE "COMPLETE & NEXT" BUTTON
                if st.button("✅ Complete Bottle & Next Scan", type="primary", use_container_width=True):
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
                    # Reset the scanner for the next bottle
                    st.session_state.barcode_input = ""
                    st.rerun()

            with col_info:
                st.subheader("📚 Other Lots")
                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)
        else:
            st.error(f"SKU '{sku_scan}' not found.")

    # --- THE LIVE BUILD LOG ---
    if st.session_state.build_log:
        st.divider()
        st.subheader("📋 Session Build Log")
        st.table(pd.DataFrame(st.session_state.build_log))
