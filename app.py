import streamlit as st
import pandas as pd
import time
import random

# --- 1. USER DATABASE ---
USER_DB = {
    "Admin": "1234",
    "Mike": "5678",
    "Sarah": "9012",
    "Production_Station_1": "bottling2024"
}

# --- SESSION MEMORY ---
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = pd.DataFrame()
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
if 'current_build' not in st.session_state:
    st.session_state.current_build = []
if 'permanent_history' not in st.session_state:
    st.session_state.permanent_history = []
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

st.set_page_config(page_title="Flavor Build", layout="wide")

# --- LOGIN SCREEN ---
if not st.session_state.authenticated:
    st.title("🔐 Flavor Build Login")
    with st.container(border=True):
        user = st.selectbox("Select Your Name", list(USER_DB.keys()))
        password = st.text_input("Enter Password", type="password")
        if st.button("Log In", use_container_width=True):
            if USER_DB.get(user) == password:
                st.session_state.authenticated = True
                st.session_state.user_name = user
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop() 

# --- SIDEBAR ---
with st.sidebar:
    st.success(f"✅ User: **{st.session_state.user_name}**")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()
    
    st.divider()

    # --- SCALE HARDWARE CONFIGURATION ---
    st.header("⚖️ Scale Settings")
    
    SCALE_PROFILES = {
        "Standard Digital (9600)": {"baud": 9600, "cmd": "W\n"},
        "Ohaus Defender (2400)": {"baud": 2400, "cmd": "P\n"},
        "Mettler Toledo (MT-SICS)": {"baud": 9600, "cmd": "SI\n"},
        "Manual Entry": {"baud": None, "cmd": None}
    }

    selected_model = st.selectbox("Select Station Scale", list(SCALE_PROFILES.keys()))
    port_input = st.text_input("USB Port", value="COM3")
    
    # Save selection to session state
    st.session_state.scale_settings = {
        "port": port_input,
        "baud": SCALE_PROFILES[selected_model]["baud"],
        "cmd": SCALE_PROFILES[selected_model]["cmd"]
    }

    st.divider()
    st.header("📂 Data Center")
    inv_file = st.file_uploader("Upload Inventory (CSV)", type=['csv'])
    if inv_file:
        st.session_state.inventory_df = pd.read_csv(inv_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')

    sch_file = st.file_uploader("Upload Schedule (Excel)", type=['xlsx'])
    if sch_file:
        st.session_state.schedule_df = pd.ExcelFile(sch_file)

    if st.session_state.permanent_history:
        st.divider()
        st.header("📥 Export Data")
        export_df = pd.DataFrame(st.session_state.permanent_history)
        
        final_cols = [
            'Build ID', 'Description', 'Status', 'Product ID to produce', 'Lot ID to produce', 
            'Quantity to produce', 'Start date estimated', 'Start date actual', 
            'Complete date estimated', 'Complete date actual', 'Sublocation', 
            'Consume lot id', 'Consume sublocation', 'Consume product ID', 'Consume quantity', 'Notes/Variance'
        ]
        
        st.download_button(label="📊 DOWNLOAD CSV", data=export_df[final_cols].to_csv(index=False).encode('latin1'),
            file_name=f"flavor_build_{time.strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True, type="primary")
        
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
        
        if len(batch_options) > 0:
            selected_batch = st.selectbox("Select Assigned Batch", batch_options)
            batch_data = df_final[df_final['Name'] == selected_batch].iloc[0]
            
            full_name = str(batch_data['Name']).strip()
            full_code = full_name.split()[0]
            planned_qty = int(batch_data['Qty'])
            
            prefix = full_code[0]
            if prefix == '1': oz_per, size_label = 0.33814, "10mL"
            elif prefix == '3': oz_per, size_label = 1.01442, "30mL"
            elif prefix == '4': oz_per, size_label = 4.0, "4oz"
            else: oz_per, size_label = 1.0, "Unknown"

            target_oz = round(planned_qty * oz_per, 4)
            req_base_id = full_code[1:] if len(full_code) >= 5 else full_code
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Planned Units", f"{planned_qty}")
            c2.metric("📏 Unit Size", size_label)
            c3.metric("🎯 Target Oz", f"{target_oz} oz")

            current_oz = sum(item['Consume quantity'] for item in st.session_state.current_build)
            remaining_oz = round(target_oz - current_oz, 4)
            
            cl, cr = st.columns(2)
            cl.metric("⚖️ Remaining", f"{remaining_oz} oz")
            cr.metric("🧪 Logged", f"{current_oz} oz")

            st.warning(f"🛡️ **Safety Lock:** Scan Base ID: **{req_base_id}**")
            sku_scan = st.text_input("Scan Barcode").strip()

            if sku_scan:
                if sku_scan != req_base_id:
                    st.error(f"❌ Incorrect ID: Expected **{req_base_id}**.")
                else:
                    matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == sku_scan]
                    
                    col_m, col_i = st.columns([2, 1])
                    with col_m:
                        st.success("✅ Validated")
                        lot_options = ["--- Select Lot ---"] + list(matches['Lot ID'].unique()) + ["MANUAL ENTRY"]
                        sel_lot = st.selectbox("Confirm Lot ID", lot_options)
                        
                        manual_lot = ""
                        initial_w = 0.0
                        
                        if sel_lot == "MANUAL ENTRY":
                            manual_lot = st.text_input("Enter Manual Lot Number").strip()
                            initial_w = st.number_input("Starting Weight (Manual)", value=0.0)
                        elif sel_lot != "--- Select Lot ---":
                            active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                            initial_w = float(active['Quantity'])

                        w_col1, w_col2 = st.columns(2)
                        w_before = w_col1.number_input("Weight BEFORE", value=initial_w)
                        w_after = w_col2.number_input("Weight AFTER", value=0.0)
                        
                        actual_used = round(w_before - w_after, 4)

                        if st.button("➕ Log Bottle", use_container_width=True):
                            if sel_lot == "--- Select Lot ---":
                                st.error("Please select a valid Lot ID.")
                            elif sel_lot == "MANUAL ENTRY" and not manual_lot:
                                st.error("Manual entry requires a Lot Number.")
                            else:
                                alerts = []
                                if sel_lot == "MANUAL ENTRY": alerts.append("MANUAL LOT ENTRY")
                                if actual_used > remaining_oz: alerts.append(f"OVER-POUR ({actual_used} oz)")
                                
                                st.session_state.temp_entry = {
                                    'final_lot': manual_lot if sel_lot == "MANUAL ENTRY" else sel_lot,
                                    'actual_used': actual_used,
                                    'notes': " | ".join(alerts),
                                    'full_code': full_code,
                                    'req_base_id': req_base_id,
                                    'size_label': size_label
                                }
                                
                                if alerts:
                                    st.session_state.show_confirm = True
                                else:
                                    if not st.session_state.current_build:
                                        st.session_state.new_build_id = random.randint(100000, 999999)
                                    
                                    st.session_state.current_build.append({
                                        'Build ID': st.session_state.new_build_id,
                                        'Description': f"{st.session_state.user_name} {size_label}",
                                        'Status': 'Completed',
                                        'Product ID to produce': f"B{full_code}",
                                        'Lot ID to produce': '', 'Quantity to produce': 0, 
                                        'Start date estimated': time.strftime('%m/%d/%Y'), 'Start date actual': time.strftime('%m/%d/%Y'),
                                        'Complete date estimated': time.strftime('%m/%d/%Y'), 'Complete date actual': time.strftime('%m/%d/%Y'),
                                        'Sublocation': 'Bottling', 'Consume lot id': st.session_state.temp_entry['final_lot'],
                                        'Consume sublocation': 'Bottling', 'Consume product ID': req_base_id,
                                        'Consume quantity': actual_used, 'Notes/Variance': ""
                                    })
                                    st.rerun()

                        # --- POP-UP VERIFICATION WINDOW ---
                        if st.session_state.get('show_confirm', False):
                            st.divider()
                            with st.container(border=True):
                                st.markdown("<h1 style='text-align: center; color: red;'>⚠️ ATTENTION REQUIRED ⚠️</h1>", unsafe_allow_html=True)
                                st.markdown(f"<h3 style='text-align: center;'>Detected: {st.session_state.temp_entry['notes']}</h3>", unsafe_allow_html=True)
                                st.error("### YOU ARE LOGGING AN EXCEPTION. PROCEED WITH CAUTION.")
                                
                                c_y, c_n = st.columns(2)
                                if c_y.button("🚨 YES - CONFIRM AND LOG ENTRY 🚨", use_container_width=True, type="primary"):
                                    if not st.session_state.current_build:
                                        st.session_state.new_build_id = random.randint(100000, 999999)
                                    
                                    e = st.session_state.temp_entry
                                    st.session_state.current_build.append({
                                        'Build ID': st.session_state.new_build_id,
                                        'Description': f"{st.session_state.user_name} {e['size_label']}",
                                        'Status': 'Completed', 'Product ID to produce': f"B{e['full_code']}",
                                        'Lot ID to produce': '', 'Quantity to produce': 0, 
                                        'Start date estimated': time.strftime('%m/%d/%Y'), 'Start date actual': time.strftime('%m/%d/%Y'),
                                        'Complete date estimated': time.strftime('%m/%d/%Y'), 'Complete date actual': time.strftime('%m/%d/%Y'),
                                        'Sublocation': 'Bottling', 'Consume lot id': e['final_lot'],
                                        'Consume sublocation': 'Bottling', 'Consume product ID': e['req_base_id'],
                                        'Consume quantity': e['actual_used'], 'Notes/Variance': e['notes']
                                    })
                                    st.session_state.show_confirm = False
                                    st.rerun()
                                if c_n.button("🛑 NO - CANCEL AND RE-ENTER 🛑", use_container_width=True):
                                    st.session_state.show_confirm = False
                                    st.rerun()

                    with col_i:
                        st.subheader("📚 Known Inventory")
                        st.dataframe(matches[['Lot ID', 'Quantity']], hide_index=True)

            if st.session_state.current_build:
                st.divider()
                st.subheader("📝 Live Build Review")
                live_review_df = pd.DataFrame(st.session_state.current_build)
                st.dataframe(live_review_df[['Consume product ID', 'Consume lot id', 'Consume quantity', 'Notes/Variance']], use_container_width=True, hide_index=True)

# --- REVIEW & FINALIZATION ---
if st.session_state.current_build:
    st.divider()
    st.subheader("📋 Finalize Build")
    final_units = st.number_input("Actual Units Produced (Final Count)", value=planned_qty)
    if st.button("✅ FINALIZE & SAVE BATCH", type="primary", use_container_width=True):
        for item in st.session_state.current_build:
            item['Quantity to produce'] = final_units
        st.session_state.permanent_history.extend(st.session_state.current_build)
        st.session_state.current_build = []
        st.success("Batch Saved to Log!")
        st.rerun()

if st.session_state.permanent_history:
    st.divider()
    st.subheader("📜 Running Day Log")
    st.dataframe(pd.DataFrame(st.session_state.permanent_history), use_container_width=True)
