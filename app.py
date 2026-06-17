import warnings
warnings.simplefilter(action='ignore', category=UserWarning)

import streamlit as st
import pandas as pd
import hid
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import random
from datetime import datetime
import requests
import os

# Windows Local Printing & Barcode Infrastructure Imports
import win32print
import win32ui
import win32con
import win32api 
from PIL import Image, ImageDraw, ImageFont, ImageWin
import barcode
from barcode.writer import ImageWriter

# --- 1. CONFIGURATION & CLOUD SETUP ---
JSON_FILE = 'flavor-production-logs-168ed7e988fe.json'
SHEET_ID = '1s9jY3ONcaD9f1cCIQIOasnnYlIcNrJmNUrY1qLtQGfc'

# Scale Hardware Constants
SCALE_VID = 0x2474
SCALE_PID = 0x0550

# Global columns layout standard alignment for our Inventory System Import Template
EXPORT_COLUMNS = [
    'Build ID', 'Description', 'Status', 'Product ID to produce', 'Lot ID to produce', 
    'Quantity to produce', 'Start date estimated', 'Start date actual', 
    'Complete date estimated', 'Complete date actual', 'Sublocation', 
    'Consume lot id', 'Consume sublocation', 'Consume product ID', 'Consume quantity', 'Notes/Variance'
]

def get_google_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
    return gspread.authorize(creds)

def load_users_from_sheet():
    try:
        client = get_google_client()
        sheet = client.open_by_key(SHEET_ID).worksheet("Users")
        data = sheet.get_all_records()
        return {str(row['Username']): str(row['Password']) for row in data}
    except Exception as e:
        st.error(f"Error loading user database: {e}")
        return {"Admin": "1234"}

def save_to_google_sheets(data_list):
    try:
        client = get_google_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        if not sheet.get_all_values():
            sheet.append_row(EXPORT_COLUMNS)
        for item in data_list:
            row = [item.get(col, "") for col in EXPORT_COLUMNS]
            sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Google Sheets Error: {e}")
        return False

def void_google_sheet_entry(row_index, user_name):
    try:
        client = get_google_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        actual_row = row_index + 2 
        sheet.update_cell(actual_row, 3, "VOIDED")
        sheet.update_cell(actual_row, 15, 0)
        old_notes = sheet.cell(actual_row, 16).value or ""
        new_note = f"{old_notes} | VOIDED by {user_name} at {time.strftime('%H:%M:%S')}"
        sheet.update_cell(actual_row, 16, new_note)
        return True
    except Exception as e:
        st.error(f"Void Error: {e}")
        return False

# --- SYSTEM LOCAL PRINTER DISCOVERY ENGINE ---
def discover_local_system_printers():
    try:
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        printer_names = [p[2] for p in printers]
        return sorted(printer_names)
    except Exception:
        return ["Default System Printer"]

# --- CENTRALIZED HARDWARE CONTROL ENGINE ---
def capture_hardware_weight():
    try:
        all_devs = hid.enumerate(SCALE_VID, SCALE_PID)
        if all_devs:
            dev = hid.device()
            dev.open_path(all_devs[0]['path'])
            for _ in range(15): report = dev.read(6)
            if report and len(report) >= 5:
                raw_w = report[4] + (report[5] << 8)
                scaling = report[3]
                factor = scaling - 256 if scaling > 128 else scaling
                weight = round(float(raw_w) * (10 ** factor), 4)
                dev.close()
                return weight
            dev.close()
            st.error("Scale returned an empty reading. Try resetting item.")
        else:
            st.error("Scale Not Detected. Verify physical USB connection path.")
    except Exception as e:
        st.error(f"Hardware Scale Error: {e}")
    return None

def cell_capture_callback(w_key, bottle_index):
    w_read = capture_hardware_weight()
    if w_read is not None:
        st.session_state[w_key] = w_read
        st.toast(f"✅ Bottle #{bottle_index + 1} Captured: {w_read:.4f} oz")

# --- UNIFIED DIRECT HARDWARE BYPASS PRINT ENGINE ---
def execute_label_print(target_printer, barcode_text, flavor_name, weight_oz):
    try:
        label_bitmap = Image.new('RGB', (640, 200), color=(255, 255, 255))
        canvas = ImageDraw.Draw(label_bitmap)
        
        try:
            font_flavor = ImageFont.truetype("arial.ttf", 32)  
            font_serial = ImageFont.truetype("arial.ttf", 34)  
        except:
            font_flavor = ImageFont.load_default()
            font_serial = ImageFont.load_default()
        
        midpoint_x = 350
        
        clean_flavor_string = str(flavor_name).strip().upper()
        canvas.text((midpoint_x, 10), clean_flavor_string[:26], fill=(0, 0, 0), font=font_flavor, anchor="mt")
        
        try:
            code128_engine = barcode.get('code128', str(barcode_text), writer=ImageWriter())
            barcode_raw_img = code128_engine.render(writer_options={"write_text": False, "quiet_zone": 1.0, "module_height": 5.0})
            barcode_resized = barcode_raw_img.resize((320, 55))
            label_bitmap.paste(barcode_resized, (midpoint_x - 160, 52))
        except Exception as barcode_err:
            canvas.text((midpoint_x, 60), "[BARCODE ERROR]", fill=(0, 0, 0), font=font_serial, anchor="mt")
        
        canvas.text((midpoint_x, 125), f"SERIAL: {barcode_text}", fill=(0, 0, 0), font=font_serial, anchor="mt")
        final_printed_bitmap = label_bitmap.rotate(90, expand=True)
        
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(str(target_printer))
        
        dc.StartDoc(f"Container Tracking - {barcode_text}")
        dc.StartPage()
        
        raw_width = dc.GetDeviceCaps(win32con.HORZRES)
        raw_height = dc.GetDeviceCaps(win32con.VERTRES)
        
        start_x = int(raw_width * 0.08)
        start_y = int(raw_height * 0.08)
        end_x = int(raw_width * 0.92)
        end_y = int(raw_height * 0.82)  
        
        dib = ImageWin.Dib(final_printed_bitmap)
        dib.draw(dc.GetHandleOutput(), (start_x, start_y, end_x, end_y))
        
        dc.EndPage()
        dc.EndDoc()
        st.toast("⚡ Polished Centered Barcode Label printed successfully!")
        return True
            
    except Exception as e:
        try:
            label_bitmap = Image.new('RGB', (500, 300), color=(255, 255, 255))
            canvas = ImageDraw.Draw(label_bitmap)
            canvas.text((30, 30), f"FLAVOR: {flavor_name[:32]}", fill=(0, 0, 0))
            canvas.text((30, 70), f"BARCODE: {barcode_text}", fill=(0, 0, 0))
            canvas.text((30, 110), f"WEIGHT: {weight_oz:.4f} OZ", fill=(0, 0, 0))
            label_bitmap.save(f"Label_Proof_{barcode_text}.bmp")
            st.toast(f"💾 Hardware queue unavailable: Saved image backup proof.", icon="📝")
            return True
        except:
            return False

# --- SESSION STATE MANAGEMENT ---
if 'inventory_df' not in st.session_state: st.session_state.inventory_df = pd.DataFrame()
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None
if 'breakdown_schedule_df' not in st.session_state: st.session_state.breakdown_schedule_df = None
if 'current_build' not in st.session_state: st.session_state.current_build = []
if 'breakdown_build' not in st.session_state: st.session_state.breakdown_build = []
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'scale_weight' not in st.session_state: st.session_state.scale_weight = 0.0

st.set_page_config(page_title="Flavor Production Hub", layout="wide")

# --- LOGIN SCREEN ---
if not st.session_state.authenticated:
    st.title("🔐 Flavor Production Login")
    USER_DB = load_users_from_sheet()
    with st.container(border=True):
        user = st.selectbox("Select Your Name", list(USER_DB.keys()))
        password = st.text_input("Enter Password", type="password")
        if st.button("Log In", use_container_width=True):
            if USER_DB.get(user) == password:
                st.session_state.authenticated = True
                st.session_state.user_name = user
                st.rerun()
            else: st.error("Incorrect password.")
    st.stop() 

# --- INTERFACE NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Live Build Station", "📦 Breakdown ID Printer", "📜 History & Void Review"])

# --- SHARED SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.success(f"✅ User: **{st.session_state.user_name}**")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()
    
    st.header("🖨️ Active Hardware Routing")
    system_printers = discover_local_system_printers()
    selected_hardware_printer = st.selectbox(
        "Select Active Label Printer", 
        system_printers,
        help="Choose your home Wi-Fi printer for weekend testing, or the shop DYMO 4XL on Monday."
    )
    
    st.divider()
    st.header("⚖️ Scale Connection")
    if st.button("🔄 CAPTURE CURRENT WEIGHT", type="primary", use_container_width=True):
        w = capture_hardware_weight()
        if w is not None:
            st.session_state.scale_weight = w
            st.toast(f"✅ Captured Master: {st.session_state.scale_weight} oz")
        
    st.divider()
    st.header("📂 Data Center")
    inv_file = st.file_uploader("Upload Inventory Master (CSV)", type=['csv'])
    if inv_file: 
        st.session_state.inventory_df = pd.read_csv(inv_file, dtype={'Product ID': str, 'Lot ID': str}, encoding='latin1')
        st.session_state.inventory_df.columns = st.session_state.inventory_df.columns.str.strip()
        if 'Product ID' in st.session_state.inventory_df.columns:
            st.session_state.inventory_df['Product ID'] = st.session_state.inventory_df['Product ID'].astype(str).str.strip().str.zfill(4)

    sch_file = st.file_uploader("Upload Line Schedule (Excel)", type=['xlsx'])
    if sch_file: st.session_state.schedule_df = pd.ExcelFile(sch_file)
    
    bd_file = st.file_uploader("Upload Breakdown Report (Excel)", type=['xlsx'])
    if bd_file:
        st.session_state.breakdown_schedule_df = pd.ExcelFile(bd_file)
        
    # --- MASTER END-OF-DAY EXPORT GENERATOR ENGINE ---
    st.divider()
    st.subheader("🏁 End of Shift Operations")
    if st.button("🔍 Compile Today's Sheet Rows"):
        try:
            client = get_google_client()
            ledger_sheet = client.open_by_key(SHEET_ID).sheet1
            all_rows = pd.DataFrame(ledger_sheet.get_all_records(), dtype=str)
            
            if not all_rows.empty:
                today_stamp = time.strftime('%m/%d/%Y')
                df_today = all_rows[all_rows['Start date actual'] == today_stamp].copy()
                
                if df_today.empty:
                    st.sidebar.warning("No records logged under today's date in cloud.")
                else:
                    st.sidebar.info(f"Found {len(df_today)} rows for today's export.")
                    
                    df_today['Product ID to produce'] = df_today['Product ID to produce'].astype(str).str.replace("B", "").str.zfill(4)
                    df_today['Product ID to produce'] = "B" + df_today['Product ID to produce']
                    
                    csv_export_bytes = df_today[EXPORT_COLUMNS].to_csv(index=False)
                    
                    st.sidebar.download_button(
                        label="📥 DOWNLOAD DAILY IMPORT FILE (.CSV)",
                        data=csv_export_bytes,
                        file_name=f"Master_Inventory_Import_{time.strftime('%Y_%m_%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            else:
                st.sidebar.error("Cloud database ledger is completely empty.")
        except Exception as ex:
            st.sidebar.error(f"Failed to compile cloud rows: {ex}")

# --- TAB 1: LIVE BUILD COMPOUNDING STATION ---
with tab1:
    st.title("🧪 Flavor Build Station")
    if st.session_state.inventory_df.empty or st.session_state.schedule_df is None:
        st.info("Awaiting Inventory and Compounding Schedule uploads in the sidebar...")
    else:
        col_options = st.session_state.inventory_df.columns.tolist()
        qty_key = "Quantity on hand units" if "Quantity on hand units" in col_options else "Quantity"
        
        all_tabs = st.session_state.schedule_df.sheet_names
        target_tabs = ['10 List', '30 List', '4oz List']
        relevant_tabs = [t for t in all_tabs if t in target_tabs]
        selected_tab = st.selectbox("Select Bottling Line", relevant_tabs)
        
        df_raw = st.session_state.schedule_df.parse(selected_tab)
        name_col = next((c for c in df_raw.columns if "Name" in str(c)), None)
        qty_col = next((c for c in df_raw.columns if "Qty" in str(c)), None)

        if name_col and qty_col:
            df_clean = df_raw[[name_col, qty_col]].copy().dropna(subset=[name_col])
            df_clean.columns = ['Name', 'Qty']
            df_clean['Qty'] = pd.to_numeric(df_clean['Qty'], errors='coerce').fillna(0)
            df_final = df_clean[df_clean['Qty'] > 0]
            
            selected_batch = st.selectbox("Select Assigned Batch", df_final['Name'].unique())
            batch_data = df_final[df_final['Name'] == selected_batch].iloc[0]
            
            full_code = str(batch_data['Name']).strip().split()[0]
            planned_qty = int(batch_data['Qty'])
            prefix = full_code[0]
            if prefix == '1': oz_per, size_label = 0.33814, "10mL"
            elif prefix == '3': oz_per, size_label = 1.01442, "30mL"
            elif prefix == '4': oz_per, size_label = 4.0, "4oz"
            else: oz_per, size_label = 1.0, "Unknown"

            target_oz = round(planned_qty * oz_per, 4)
            req_base_id = str(full_code[1:]).strip().zfill(4) if len(full_code) >= 5 else str(full_code).strip().zfill(4)
            
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.write(f"📦 **Planned Units:**\n### {planned_qty}")
            m2.write(f"📏 **Unit Size:**\n### {size_label}")
            m3.write(f"🎯 **Target Weight:**\n### {target_oz:.4f} oz")

            current_oz = sum(item['Consume quantity'] for item in st.session_state.current_build)
            remaining_oz = round(target_oz - current_oz, 4)
            
            st.write("---")
            cl, cr = st.columns(2)
            cl.write(f"⚖️ **Remaining Target Weight:**\n## {remaining_oz:.4f} oz")
            cr.write(f"🧪 **Total Logged Material:**\n## {current_oz:.4f} oz")

            st.warning(f"🛡️ **Safety Lock:** Scan Barcode or Base ID: **{req_base_id}**")
            scan_input = st.text_input("Scan Barcode / Container ID", key="main_scan_input").strip()

            if scan_input:
                is_serialized = "-" in scan_input
                scanned_base_id = scan_input.split("-")[0].strip().zfill(4) if is_serialized else scan_input.strip().zfill(4)
                
                if scanned_base_id == req_base_id:
                    matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == scanned_base_id]
                    col_m, col_i = st.columns([2, 1])
                    with col_m:
                        st.success("✅ Verification Match Confirmed")
                        computed_initial_w = 0.0
                        pulled_lot_id = "--- Select Lot ---"
                        
                        if is_serialized:
                            try:
                                client = get_google_client()
                                log_sheet = client.open_by_key(SHEET_ID).sheet1
                                logs_df = pd.DataFrame(log_sheet.get_all_records(), dtype=str)
                                
                                logs_df['Normalized_ID'] = logs_df['Consume product ID'].str.split("-").str[0].str.zfill(4)
                                if "-" in scan_input:
                                    logs_df['Normalized_ID'] = logs_df['Normalized_ID'] + "-" + logs_df['Consume product ID'].str.split("-").str[1]
                                    
                                normalized_scan_input = scanned_base_id + "-" + scan_input.split("-")[1]
                                matching_bottle = logs_df[logs_df['Normalized_ID'] == normalized_scan_input].iloc[-1]
                                
                                computed_initial_w = float(matching_bottle['Consume quantity'])
                                pulled_lot_id = matching_bottle['Consume lot id']
                                st.info(f"🧬 Smart Serial Detected. Auto-Pulled Lot: `{pulled_lot_id}`")
                            except:
                                st.error("⚠️ Serial record footprint not found in cloud. Reverting to structural selection.")
                        
                        lot_options = ["--- Select Lot ---"] + list(matches['Lot ID'].unique()) + ["MANUAL ENTRY"]
                        sel_lot = st.selectbox("Confirm Production Lot ID", lot_options, index=lot_options.index(pulled_lot_id) if pulled_lot_id in lot_options else 0)
                        
                        manual_lot = ""; initial_w = computed_initial_w
                        if sel_lot == "MANUAL ENTRY":
                            manual_lot = st.text_input("Enter Manual Lot Number").strip()
                            if not is_serialized: initial_w = st.number_input("Starting Weight (Manual)", value=0.0)
                        elif sel_lot != "--- Select Lot ---" and not is_serialized:
                            active = matches[matches['Lot ID'] == sel_lot].iloc[0]
                            initial_w = float(active[qty_key])

                        w_col1, w_col2 = st.columns(2)
                        w_before = w_col1.number_input("Weight BEFORE Container Movement", value=initial_w, format="%.4f")
                        w_after = w_col2.number_input("Weight AFTER (From Hardware Interface)", value=st.session_state.scale_weight, format="%.4f")
                        actual_used = round(w_before - w_after, 4)

                        if st.button("➕ Log Bottle Increment", use_container_width=True):
                            if sel_lot != "--- Select Lot ---":
                                alerts = []
                                if sel_lot == "MANUAL ENTRY": alerts.append("MANUAL LOT ENTRY")
                                if actual_used > remaining_oz: alerts.append(f"OVER-POUR ({actual_used:.4f} oz)")
                                
                                history_note = f"BATCH: {selected_batch}"
                                if alerts: history_note += " | " + " | ".join(alerts)

                                if not st.session_state.current_build:
                                    st.session_state.new_build_id = random.randint(100000, 999999)
                                
                                formatted_produce_sku = f"B{int(full_code):04d}" if full_code.isdigit() else f"B{full_code}"
                                formatted_consume_sku = f"{scanned_base_id}-{scan_input.split('-')[1]}" if is_serialized else scanned_base_id

                                st.session_state.current_build.append({
                                    'Build ID': st.session_state.new_build_id,
                                    'Description': f"{st.session_state.user_name} {size_label}",
                                    'Status': 'Completed',
                                    'Product ID to produce': formatted_produce_sku,
                                    'Lot ID to produce': '', 
                                    'Quantity to produce': planned_qty, 
                                    'Start date estimated': time.strftime('%m/%d/%Y'), 
                                    'Start date actual': time.strftime('%m/%d/%Y'),
                                    'Complete date estimated': time.strftime('%m/%d/%Y'), 
                                    'Complete date actual': time.strftime('%m/%d/%Y'),
                                    'Sublocation': 'Bottling', 
                                    'Consume lot id': str(manual_lot if sel_lot == "MANUAL ENTRY" else sel_lot),
                                    'Consume sublocation': 'Bottling', 
                                    'Consume product ID': formatted_consume_sku, 
                                    'Consume quantity': w_after if is_serialized else actual_used, 
                                    'Notes/Variance': history_note
                                })
                                st.session_state.scale_weight = 0.0 
                                st.rerun()
                    with col_i:
                        st.subheader("📚 Known Inventory")
                        if not matches.empty: st.dataframe(matches[['Lot ID', qty_key]], hide_index=True)
                else:
                    st.error("❌ Scan validation failed. Base ID match discrepancy.")

        if st.session_state.current_build:
            st.divider()
            st.subheader("📝 Live Build Review")
            review_df = pd.DataFrame(st.session_state.current_build)
            st.dataframe(review_df[['Consume product ID', 'Consume lot id', 'Consume quantity', 'Notes/Variance']], use_container_width=True, hide_index=True)
            
            final_units = st.number_input("Actual Units Produced (Final Count)", value=float(planned_qty), step=0.001, format="%.3f")
            
            if st.button("✅ FINALIZE & SAVE TO GOOGLE SHEETS", type="primary", use_container_width=True):
                for item in st.session_state.current_build: item['Quantity to produce'] = final_units
                if save_to_google_sheets(st.session_state.current_build):
                    st.session_state.current_build = []
                    st.success("🚀 Central Cloud Ledger Synchronized Successfully! Move to next product.")
                    time.sleep(1.5)
                    st.rerun()

# --- TAB 2: BREAKDOWN ID PRINTER STATION ---
with tab2:
    st.title("📦 Breakdown ID Printer")
    if st.session_state.breakdown_schedule_df is None or st.session_state.inventory_df.empty:
        st.info("Awaiting Breakdown Report Excel file in the sidebar to populate rows...")
    else:
        try:
            bd_df = st.session_state.breakdown_schedule_df.parse("Paste Info")
            bd_df.columns = bd_df.columns.str.strip()
            bd_df['Product ID'] = bd_df['Product ID'].astype(str).str.strip().str.zfill(4)
            
            active_breakdowns = bd_df[bd_df['Breakdown'].astype(str) == '1'].copy()
            active_breakdowns['Selector_Label'] = active_breakdowns['Product ID'] + " - " + active_breakdowns['Description']
            unique_labels = list(active_breakdowns['Selector_Label'].unique())
            
            bd_scan = st.text_input("Scan Source Gallon Barcode", key="bd_gallon_scan_input").strip().upper()
            
            default_index = 0
            if bd_scan:
                # Bulletproof scanner extraction: hunt for WSG or G anywhere to bypass hidden chars
                if "WSG" in bd_scan:
                    scanned_sku = bd_scan.split("WSG")[-1].zfill(4)
                elif "G" in bd_scan:
                    scanned_sku = bd_scan.split("G")[-1].zfill(4)
                else:
                    scanned_sku = ''.join(filter(str.isdigit, bd_scan)).zfill(4) if any(c.isdigit() for c in bd_scan) else bd_scan.zfill(4)
                
                matching_labels = [label for label in unique_labels if label.startswith(scanned_sku)]
                
                if matching_labels:
                    default_index = unique_labels.index(matching_labels[0])
                else:
                    st.error(f"⚠️ SKU {scanned_sku} was scanned, but it is not marked for breakdown on today's report. Please verify your paperwork.")
            
            selected_line = st.selectbox("Select Flavor Line to Process", unique_labels, index=default_index)
            
            if selected_line:
                line_data = active_breakdowns[active_breakdowns['Selector_Label'] == selected_line].iloc[0]
                bd_product_id = line_data['Product ID']
                bd_description = line_data['Description']
                bd_start16 = str(line_data['Start16'])
                
                with st.container(border=True):
                    c_id, c_desc, c_count = st.columns([1, 3, 1])
                    c_id.metric("SKU Base ID", bd_product_id)
                    c_desc.metric("Flavor Description", bd_description)
                    c_count.metric("Expected Shelf Inventory (Start16)", bd_start16)
                    
                    col_inputs_1, col_inputs_2, col_inputs_3, col_inputs_4 = st.columns(4)
                    
                    # Reverted to match the "G" format of the Master Inventory upload
                    lookup_gallon_id = f"G{bd_product_id}"
                    inv_matches = st.session_state.inventory_df[st.session_state.inventory_df['Product ID'] == lookup_gallon_id]
                    lot_list = list(inv_matches['Lot ID'].unique()) if not inv_matches.empty else []
                    
                    selected_bulk_lot = col_inputs_1.selectbox("Source Gallon Lot Number", ["--- Select Lot ---"] + lot_list + ["MANUAL ENTRY"], key="bd_lot_select")
                    
                    if selected_bulk_lot == "MANUAL ENTRY":
                        selected_bulk_lot = col_inputs_1.text_input("Key Manual Gallon Lot #", key="bd_manual_lot")
                        
                    gallons_processed = col_inputs_2.number_input("Gallons Being Broken Down", min_value=0.1, max_value=20.0, value=1.0, step=0.1)
                    build_qty_input = col_inputs_3.number_input("Build Quantity Value Field", value=0.0, step=0.001, format="%.3f")
                    num_bottles = col_inputs_4.number_input("Total Bottles Created (Labels Needed)", min_value=1, max_value=50, value=8, step=1)
                    
                st.divider()
                
                st.subheader("📋 Generated Label Manifest Preview")
                
                cache_key = f"bd_serials_{bd_product_id}"
                if cache_key not in st.session_state or len(st.session_state[cache_key]) != num_bottles:
                    st.session_state[cache_key] = [f"{bd_product_id}-{random.randint(100000, 999999)}" for _ in range(num_bottles)]
                
                active_serials = st.session_state[cache_key]
                
                preview_data = [{"Bottle #": i+1, "Generated Barcode": serial, "Flavor": bd_description} for i, serial in enumerate(active_serials)]
                st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)
                
                st.divider()

                if st.button("🔥 FINALIZE TRACKING BATCH & SPIT DYMO LABELS", type="primary", use_container_width=True):
                    if selected_bulk_lot == "--- Select Lot ---" or not selected_bulk_lot:
                        st.error("Cannot finalize log execution path: A valid master source Lot identifier must be assigned.")
                    else:
                        st.session_state.breakdown_build = []
                        for serial in active_serials:
                            formatted_produce_sku = f"B{bd_product_id}"
                            
                            st.session_state.breakdown_build.append({
                                'Build ID': random.randint(100000, 999999),
                                'Description': f"{st.session_state.user_name} Breakdown",
                                'Status': 'Completed',
                                'Product ID to produce': formatted_produce_sku,
                                'Lot ID to produce': '', 
                                'Quantity to produce': build_qty_input, 
                                'Start date estimated': time.strftime('%m/%d/%Y'), 
                                'Start date actual': time.strftime('%m/%d/%Y'),
                                'Complete date estimated': time.strftime('%m/%d/%Y'), 
                                'Complete date actual': time.strftime('%m/%d/%Y'),
                                'Sublocation': 'Bottling', 
                                'Consume lot id': str(selected_bulk_lot),
                                'Consume sublocation': 'Bottling', 
                                'Consume product ID': serial, 
                                'Consume quantity': 0.0,
                                'Notes/Variance': f"BREAKDOWN BATCH | Source Gallons: {gallons_processed}"
                            })

                        for item in st.session_state.breakdown_build:
                            execute_label_print(
                                target_printer=selected_hardware_printer,
                                barcode_text=item['Consume product ID'],
                                flavor_name=bd_description,
                                weight_oz=0.0
                            )
                            
                        if save_to_google_sheets(st.session_state.breakdown_build):
                            st.session_state.breakdown_build = []
                            del st.session_state[cache_key] 
                            st.success(f"🚀 Successfully printed {num_bottles} labels and registered to Central Database.")
                            time.sleep(2.0)
                            st.rerun()
        except Exception as err:
            st.error(f"Error reading Breakdown Data Layout configuration fields: {err}")

# --- TAB 3: MASTER HISTORY & AUDIT REVIEW ---
with tab3:
    st.header("📜 Daily Production History")
    if st.button("🔄 Refresh Master History Log Pipeline"):
        st.rerun()
    
    try:
        client = get_google_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        all_logs = pd.DataFrame(sheet.get_all_records(), dtype=str)
        
        if not all_logs.empty:
            today_str = time.strftime('%m/%d/%Y')
            daily_logs = all_logs[all_logs['Start date actual'] == today_str].copy()
            
            if daily_logs.empty:
                st.info("No transaction tracking signatures found recorded under today's system parameters.")
            else:
                for idx, row in daily_logs.iterrows():
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([1.5, 3, 1, 1])
                        c1.markdown(f"**ID:** {row['Build ID']}\n\n**Operator:** {row['Description']}")
                        
                        raw_note = row['Notes/Variance']
                        if "BATCH:" in raw_note:
                            display_name = raw_note.split('|')[0].replace("BATCH: ", "")
                        elif "BREAKDOWN" in raw_note:
                            display_name = f"🛠️ Container Breakdown Processing"
                        else:
                            display_name = "Standard Transaction Signature"
                        
                        c2.markdown(f"### {display_name}") 
                        c2.markdown(f"**SKU/Barcode:** `{row['Consume product ID']}` | **Lot:** `{row['Consume lot id']}`")
                        
                        try:
                            val_float = float(row['Consume quantity'])
                            c3.metric("Amount Used / Weight", f"{val_float:.4f} oz")
                        except:
                            c3.metric("Amount Used / Weight", f"{row['Consume quantity']} oz")
                        
                        if row['Status'] == "VOIDED":
                            c4.error("🚫 VOIDED")
                        else:
                            if c4.button("🗑️ Void", key=f"void_{idx}"):
                                if void_google_sheet_entry(idx, st.session_state.user_name):
                                    st.toast("✅ Entry Voided")
                                    time.sleep(1)
                                    st.rerun()
        else:
            st.info("The central production log ledger is currently blank.")
    except Exception as e:
        st.error(f"System tracking error reading history elements: {e}")
