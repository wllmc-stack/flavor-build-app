import streamlit as st
import pandas as pd
import time

# --- 1. INITIALIZATION (The App's Memory) ---
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'build_records' not in st.session_state:
    st.session_state.build_records = []

st.set_page_config(page_title="Flavor Build App", layout="wide")

# --- 2. SIDEBAR (Import & Export) ---
with st.sidebar:
    st.header("Inventory Management")
    uploaded_file = st.file_uploader("Upload Master List", type=['csv'])
    if uploaded_file and st.session_state.inventory_df.empty:
        # Load data as strings to keep leading zeros (0054)
        df = pd.read_csv(uploaded_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        df.columns = df.columns.str.strip()
        st.session_state.inventory_df = df
        st.success("Master List Loaded")

    # --- THE BUILD-ONLY EXPORT ---
    if st.session_state.build_records:
        st.divider()
        st.header("Batch Export")
        # This only pulls from the session's work, not the whole master list
        batch_df = pd.DataFrame(st.session_state.build_records)
        
        st.download_button(
            label="💾 Download Build Report Only",
            data=batch_df.to_csv(index=False).encode('latin1'),
            file_name=f"build_report_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="This file contains only the bottles you processed in this session."
        )

# --- 3. MAIN WORKFLOW ---
st.title("🧪 Flavor Build Station")

if st.session_state.inventory_df.empty:
    st.info("Please upload your Master List in the sidebar to begin.")
else:
    # BATCH IDENTIFIER (Good for tracking which order these bottles belong to)
    batch_id = st.text_input("Enter Batch / Order Number", placeholder="e.g., BATCH-202").strip()

    # SCANNER INPUT
    sku_scan = st.text_input("Scan Product ID").strip()

    if sku_scan:
        df = st.session_state.inventory_df
        matches = df[df['Product ID'] == sku_scan]

        if not matches.empty:
            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader("🎯 Scanned Bottle")
                sel_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                
                st.write(f"**Description:** {active['Description']}")
                current_qty = float(active['Quantity'])
                
                # Input usage
                w_start = st.number_input("Weight Before Pouring", value=current_qty)
                w_end = st.number_input("Weight After Pouring", value=current_qty)
                
                if st.button("➕ Log this Bottle"):
                    st.session_state.build_records.append({
                        'Batch ID': batch_id,
                        'Product ID': sku_scan,
                        'Lot ID': sel_lot,
                        'Description': active['Description'],
                        'Start Weight': w_start,
                        'Final Weight': w_end,
                        'Consumed': round(w_start - w_end, 4),
                        'Timestamp': time.strftime('%H:%M:%S')
                    })
                    st.toast(f"Logged {sel_lot} to Build!")

            with col_right:
                st.subheader("📚 SKU Context (Other Lots)")
                # Shows other options so they can find nearly-empty bottles
                st.dataframe(matches[['Lot ID', 'Quantity']], use_container_width=True, hide_index=True)
        else:
            st.error(f"SKU '{sku_scan}' not found in Master List.")

    # --- 4. THE LIVE LOG (Show what we've done) ---
    if st.session_state.build_records:
        st.divider()
        st.subheader("📋 Session Build Log")
        st.table(pd.DataFrame(st.session_state.build_records))
