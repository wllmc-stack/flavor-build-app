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

# --- SIDEBAR ---
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
        history_df = pd.DataFrame(st.session_state.permanent_history)
        st.download_button(
            label="📥 DOWNLOAD FULL LOG",
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
    # --- HEADER INPUTS ---
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        batch_ref = st.text_input("Batch / Order Reference", placeholder="Batch #")
    with col_b:
        prod_produce = st.text_input("Product to Produce", placeholder="Final Flavor")
    with col_c:
        prod_consume = st.text_input("Product to Consume", placeholder="Target Ingredient")
    
    st.divider()
    
    # SCANNER INPUT
    sku_scan = st.text_input("Scan Ingredient Barcode").strip()

    if sku_scan:
        matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]

        if not matches.empty:
            # VISUAL STATUS CARD
            st.warning(f"🔨 **Current Build:** {prod_produce} | 🌾 **Using Ingredient:** {prod_consume}")
            
            col_main, col_info = st.columns([2, 1])
            with col_main:
                st.subheader("🎯 Active Bottle")
                selected_lot = st.selectbox("Confirm Lot ID", matches['Lot ID'].unique())
                active_row = matches[matches['Lot ID'] == selected_lot].iloc[0]
                
                st.info(f"**Desc:** {active_row['Description']}")
                current_qty = float(active_row['Quantity'])
                
                c1, c2 = st.columns(2)
                with c1:
                    w_start = st.number_input("Weight BEFORE", value=current_qty)
                with c2:
                    w_end = st.number_input("Weight AFTER", value=current_qty)
                
                if st.button("➕ Add Bottle to Build", type="secondary", use_container_width=True):
                    st.session_state.current_build.append({
                        'Batch Ref': batch_ref,
                        'Product to Produce': prod_produce,
                        'Product to Consume': prod_consume,
                        'Product ID': sku_scan,
                        'Lot ID': selected_lot,
                        'Description': active_row['Description'],
                        'Start Weight': w_start,
                        'End Weight': w_end,
                        'Used': round(w_start - w_end, 4),
                        'Time': time.strftime('%H:%M:%S')
                    })
                    st.toast("Added!")

            with col_info:
                st.subheader("📚 SKU Inventory")
                st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)
        else:
            st.error(f"SKU '{sku_scan}' not found.")

    # --- THE BUILD REVIEW & FINALIZATION ---
    if st.session_state.current_build:
        st.divider()
        st.subheader("📋 Current Build Review")
        st.table(pd.DataFrame(st.session_state.current_build))
        
        if st.button("✅ FINALIZE BUILD & CLEAR SCREEN", type="primary", use_container_width=True):
            st.session_state.permanent_history.extend(st.session_state.current_build)
            st.session_state.current_build = []
            st.success("Build finalized and added to master log!")
            st.rerun()

    # --- THE RUNNING SESSION LOG ---
    if st.session_state.permanent_history:
        st.divider()
        st.subheader("📜 Running Session Log (History)")
        st.dataframe(pd.DataFrame(st.session_state.permanent_history), use_container_width=True)
