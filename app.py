import streamlit as st
import pandas as pd
import time

# --- SESSION MEMORY ---
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'current_build' not in st.session_state:
    st.session_state.current_build = []
if 'permanent_history' not in st.session_state:
    st.session_state.permanent_history = []

st.set_page_config(page_title="Flavor Build App", layout="wide")

# --- SIDEBAR: GLOBAL DOWNLOAD ---
with st.sidebar:
    st.header("📊 Total Session Export")
    uploaded_file = st.file_uploader("Upload Master List", type=['csv'])
    
    if uploaded_file and st.session_state.inventory_df.empty:
        df = pd.read_csv(uploaded_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        df.columns = df.columns.str.strip()
        st.session_state.inventory_df = df

    if st.session_state.permanent_history:
        st.divider()
        st.subheader("Download Master History")
        # THIS DOWNLOADS EVERYTHING LOGGED IN THE SESSION
        history_df = pd.DataFrame(st.session_state.permanent_history)
        st.download_button(
            label="📥 DOWNLOAD FULL LOG (ALL BUILDS)",
            data=history_df.to_csv(index=False).encode('latin1'),
            file_name=f"full_session_log_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# --- MAIN WORK AREA ---
st.title("🧪 Flavor Build Station")

if st.session_state.inventory_df.empty:
    st.info("Please upload your Master List in the sidebar.")
else:
    batch_ref = st.text_input("Batch / Order Reference", placeholder="e.g. BATCH-505")
    sku_scan = st.text_input("Scan Product ID").strip()

    if sku_scan:
        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]

        if not matches.empty:
            col_main, col_info = st.columns([2, 1])
            with col_main:
                st.subheader("🎯 Active Bottle")
                selected_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                active_row = matches[matches['Lot ID'] == selected_lot].iloc[0]
                
                st.info(f"**Desc:** {active_row['Description']}")
                current_qty = float(active_row['Quantity'])
                w_start = st.number_input("Weight BEFORE", value=current_qty)
                w_end = st.number_input("Weight AFTER", value=current_qty)
                
                # BUTTON 1: LOG INDIVIDUAL BOTTLE
                if st.button("➕ Add Bottle to Build"):
                    st.session_state.current_build.append({
                        'Batch Ref': batch_ref,
                        'Product ID': sku_scan,
                        'Lot ID': selected_lot,
                        'Description': active_row['Description'],
                        'Start': w_start,
                        'End': w_end,
                        'Used': round(w_start - w_end, 4),
                        'Time': time.strftime('%H:%M:%S')
                    })
                    st.toast("Bottle added to current build.")

            with col_info:
                st.subheader("📚 SKU Inventory")
                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)

    # --- THE BUILD REVIEW & FINALIZATION ---
    if st.session_state.current_build:
        st.divider()
        st.subheader("📋 Current Build Review")
        st.table(pd.DataFrame(st.session_state.current_build))
        
        # BUTTON 2: FINALIZE THE BUILD
        if st.button("✅ FINALIZE BUILD & CLEAR SCREEN", type="primary", use_container_width=True):
            # Move items from Current Build to Permanent History
            st.session_state.permanent_history.extend(st.session_state.current_build)
            # Clear the current build staging area
            st.session_state.current_build = []
            st.success("Build finalized and added to master log!")
            st.rerun()

    # --- THE RUNNING SESSION LOG ---
    if st.session_state.permanent_history:
        st.divider()
        st.subheader("📜 Running Session Log (History)")
        st.dataframe(pd.DataFrame(st.session_state.permanent_history), use_container_width=True)
