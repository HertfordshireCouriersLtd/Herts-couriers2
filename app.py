import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

DB_FILE = "herts_couriers_v3.db"
COMPANY_EMAIL = "info@hertfordshirecouriersltd.co.uk"
OFFICE_PHONE = "01462-675328"

# ==========================================
# DATABASE SCHEMAS & INITIALISATION
# ==========================================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # User Profiles (Licence and Holiday metadata)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                last_licence_check TEXT NOT NULL, -- YYYY-MM-DD
                licence_approved INTEGER DEFAULT 1, -- 1=True, 0=Locked Out
                holiday_entitlement INTEGER DEFAULT 28,
                holiday_taken INTEGER DEFAULT 0
            )
        """)
        
        # Extended Duty & Shift Time Logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_name TEXT NOT NULL,
                date TEXT NOT NULL,
                activity_type TEXT NOT NULL, -- Driving, Warehouse, Waiting, Lunch
                start_time TEXT NOT NULL,
                end_time TEXT,
                cumulative_driving_mins INTEGER DEFAULT 0,
                alert_triggered INTEGER DEFAULT 0
            )
        """)
        
        # Structured Defect Audit Reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS defects_v3 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_name TEXT NOT NULL,
                date TEXT NOT NULL,
                check_type TEXT NOT NULL, -- Morning / End of Shift
                mileage INTEGER NOT NULL,
                clean_inside TEXT NOT NULL,
                clean_outside TEXT NOT NULL,
                straps_count INTEGER NOT NULL,
                has_trolley TEXT NOT NULL,
                doors_locked TEXT NOT NULL,
                tyre_tread TEXT NOT NULL,
                fuel_full TEXT NOT NULL,
                fuel_photo_bytes BLOB,
                photo_in_bytes BLOB,
                photo_out_bytes BLOB
            )
        """)

        # Leave Planning & Absence Audit
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leave_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_name TEXT NOT NULL,
                leave_type TEXT NOT NULL, -- Holiday, Sickness, Absence
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                days_requested INTEGER NOT NULL,
                status TEXT NOT NULL -- Approved, Automatically Rejected
            )
        """)
        
        # Seed test profile if database is completely fresh
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users VALUES ('driver1', 'Driver', '2026-01-15', 1, 28, 4)")
            cursor.execute("INSERT INTO users VALUES ('manager1', 'Manager', '2026-01-01', 1, 28, 0)")
        conn.commit()

init_db()

# ==========================================
# SIMULATED INTERFACE NOTIFICATIONS / EMAILS
# ==========================================
def simulate_email(to_address, subject, message):
    st.toast(f"📧 **Email Sent to {to_address}**\n\n*Subject:* {subject}\n\n{message}", icon="✉️")

# ==========================================
# STREAMLIT UI ARCHITECTURE
# ==========================================
st.markdown(
    """
    <style>
    .stButton>button { border-radius: 6px; font-weight: bold; }
    div.stButton > button:first-child { background-color: #2e7d32; color: white; } /* Default Green */
    .emergency-btn > divAndButton > button { background-color: #c62828 !important; color: white !important; }
    </style>
    """, 
    unsafe_map=True
)

st.title("🚚 Hertfordshire Couriers Ltd")
st.caption(f"Fleet Safety & Operations Network Portal • Helpline: {OFFICE_PHONE}")

# Sidebar Identity Frame
st.sidebar.header("🔐 Secure Access Profile")
login_user = st.sidebar.text_input("Username Profile", value="driver1").strip()

with sqlite3.connect(DB_FILE) as conn:
    user_record = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(login_user,))

if user_record.empty:
    st.error("Access profile error. Please input a valid database identity code (e.g., 'driver1' or 'manager1').")
    st.stop()

user_role = user_record.iloc[0]['role']
last_check_date = datetime.strptime(user_record.iloc[0]['last_licence_check'], "%Y-%m-%d")
next_review_due = last_check_date + timedelta(days=182) # 6 months
days_until_review = (next_review_due - datetime.now()).days
licence_state = user_record.iloc[0]['licence_approved']

# Global Licence Enforcement Engine
if days_until_review <= 0 and licence_state == 1:
    # Notice window expired; check manager validation status
    licence_state = 0
    with sqlite3.connect(DB_FILE) as conn:
        conn.cursor().execute("UPDATE users SET licence_approved = 0 WHERE username = ?", (login_user,))
        conn.commit()

# ==========================================
# HARD CORE LOCKOUT GATES
# ==========================================
if licence_state == 0 and user_role != "Manager":
    st.error("⛔ **CRITICAL LICENCE EXCLUSION: LOCKOUT ACTIVATED**")
    st.warning("Your 6-month driving credentials review date has passed without verification.")
    st.info(f"You are strictly barred from logging time or moving vehicles. Call the office immediately at **{OFFICE_PHONE}**.")
    simulate_email(COMPANY_EMAIL, f"Driver Lockout Alert: {login_user}", f"Driver {login_user} was blocked due to overdue licence check.")
    st.stop()

if days_until_review == 0 and user_role != "Manager":
    st.warning(f"⚠️ **48-Hour Urgent Notification**: Your mandatory licence review is due. Please contact administration within 48 hours to avoid account lockout.")

# ==========================================
# ROUTING MAIN COMPONENT FRAMES
# ==========================================
if user_role == "Driver":
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    with sqlite3.connect(DB_FILE) as conn:
        has_morning_check = not pd.read_sql_query("SELECT 1 FROM defects_v3 WHERE driver_name = ? AND date = ? AND check_type = 'Morning'", conn, params=(login_user, current_date)).empty
        active_activity = pd.read_sql_query("SELECT * FROM activities WHERE driver_name = ? AND date = ? AND end_time IS NULL LIMIT 1", conn, params=(login_user, current_date))
        total_driving_df = pd.read_sql_query("SELECT SUM(cumulative_driving_mins) as total FROM activities WHERE driver_name = ? AND date = ? AND activity_type = 'Driving'", conn, params=(login_user, current_date))
    
    total_driving_mins = total_driving_df.iloc[0]['total'] if total_driving_df.iloc[0]['total'] else 0
    
    # 1. MORNING MANDATORY GATING SHEET
    if not has_morning_check:
        st.error("🛑 **Mandatory Inspection Blockade**")
        st.info("Company regulations dictate a complete vehicle safety check and mileage capture before any shift metrics unlock.")
        
        with st.form("morning_walkaround"):
            st.subheader("📋 Morning Walkaround Inspection Protocol")
            mil = st.number_input("Vehicle Starting Mileage", min_value=0, step=1)
            reg = st.text_input("Vehicle Registration Mark (VRM)").upper()
            cl_in = st.selectbox("Interior Cleanliness", ["Excellent", "Fair", "Requires Attention"])
            cl_out = st.selectbox("Exterior Cleanliness", ["Clean", "Dirty - Clean Required"])
            straps = st.number_input("Count of Restraining Straps present (Min 5 required)", min_value=0, step=1)
            trolley = st.radio("One Heavy-Duty Transport Trolley Present?", ["Yes", "No"])
            locks = st.radio("All Security Load Compartment Doors Lock Correctly?", ["Yes", "No"])
            tread = st.radio("Tyre Tread Depth and Pressures Visually Roadworthy?", ["Yes", "No"])
            fuel = st.radio("Fuel Level: Completely Full Tank?", ["Yes", "No"])
            
            fuel_file = st.file_uploader("Upload Fuel Gauge Photo (Mandatory if Tank Not Full)", type=["jpg","png"])
            photo_in = st.file_uploader("Upload Inside Vehicle Capture Frame", type=["jpg","png"])
            photo_out = st.file_uploader("Upload Exterior Asset Perimeter Capture", type=["jpg","png"])
            
            if st.form_submit_button("Lock & Submit Inspection Assets"):
                if not reg or straps < 5 or trolley == "No" or tread == "No":
                    st.error("🚨 Safety non-compliance or field omission. Ensure vehicle has 5 straps, 1 trolley, valid tires, and a VRM entry.")
                else:
                    with sqlite3.connect(DB_FILE) as conn:
                        conn.cursor().execute("""
                            INSERT INTO defects_v3 (driver_name, date, check_type, mileage, clean_inside, clean_outside, straps_count, has_trolley, doors_locked, tyre_tread, fuel_full)
                            VALUES (?, ?, 'Morning', ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (login_user, current_date, mil, cl_in, cl_out, straps, trolley, locks, tread, fuel))
                        conn.commit()
                    st.success("Vehicle parameters stored safely. Driver interface features unlocked.")
                    st.rerun()
        st.stop()

    # 2. RUNTIME ACTIVE DUTY CONTROLLER 
    st.header("⚡ Active Duty Tracking Unit")
    
    # 10-Hour Driving Limit Intercept
    if total_driving_mins >= 570: # 9 hours 30 mins
        st.error("🚨 **CRITICAL SAFETY REACH WARNING: MAXIMUM DRIVING CAPACITY REACHED**")
        st.markdown(
            f"""
            Hertfordshire Couriers Ltd policy strictly dictates a maximum driving boundary. 