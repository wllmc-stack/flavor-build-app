import streamlit as st
import pandas as pd
import time

# --- SESSION STATE INITIALIZATION ---
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'build_queue' not in st.session_state:
    st.session_state.build_queue = []
# This tracks EVERY successful commit in the current session
if 'session_history' not in st.session_state:
    st.session_state.session_history = []

st.set_page_config(page_title="Flavor Build App", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Admin Controls")
    uploaded_file = st.file_uploader("Upload Master List", type=['csv'])
    if uploaded_file and st.session_state.inventory_df.empty:
        df = pd.read_csv(uploaded_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        df.columns = df.columns.str.strip()
        st.session_state.inventory_df = df

    st.divider()
    
    # BATCH EXPORT: Only visible if items have been committed
    if st.session_state.session_history:
        st.header("Session Export")
        export_df = pd.DataFrame(st.session_state.session_history)
        
        # We only export the critical transaction data
        csv_output = export_df.to_csv(index=False).encode('latin1')
        st.download_button(
            label="📊 Export Build Records Only",
            data=csv_output,
            file_name=f"build_report_{time.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# --- MAIN WORKFLOW ---
# ... (Scanner and Dual-Window code remains here) ...

# --- COMMIT LOGIC ---
if st.session_state.build_queue:
    st.divider()
    st.subheader("Final Review")
    st.table(pd.DataFrame(st.session_state.build_queue))
    
    if st.button("🔥 COMMIT & LOG BUILD", type="primary", use_container_width=True):
        main_df = st.session_state.inventory_df
        
        for item in st.session_state.build_queue:
            # 1. Update the local Master List copy
            mask = (main_df['Product ID'] == item['Product ID']) & (main_df['Lot ID'] == item['Lot ID'])
            main_df.loc[mask, 'Quantity'] = item['Final']
            
            # 2. Add to Session History with a Timestamp
            item['Timestamp'] = time.strftime('%H:%M:%S')
            st.session_state.session_history.append(item)
        
        # 3. Cleanup
        st.session_state.inventory_df = main_df
        st.session_state.build_queue = []
        st.success("Changes logged to Session Report.")
        st.rerun()