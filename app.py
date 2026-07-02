import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime

DB_FILE = "herts_couriers.db"

# ==========================================
# DATABASE INITIALISATION
# ==========================================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Shifts table tracking start and finish times
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_name TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                status TEXT DEFAULT 'Not Started'
            )
        """)
        # Defect reports table tracking pre-work and post-work checks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS defects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                driver_name TEXT NOT NULL,
                vehicle_reg TEXT NOT NULL,
                date TEXT NOT NULL,
                check_type TEXT NOT NULL, -- 'Pre-Work' or 'End of Shift'
                has_defects TEXT NOT NULL,
                details TEXT,
                resolved_status TEXT DEFAULT 'Open'
            )
        """)
        conn.commit()

init_db()

# ==========================================
# APP LAYOUT & CONFIGURATION
# ==========================================
st.set_page_config(page_title="Hertfordshire Couriers Portal", page_icon="🚚", layout="wide")
st.title("🚚 Hertfordshire Couriers Ltd")
st.subheader("Driver Operations & Fleet Safety Portal")

# Sidebar Login System
st.sidebar.header("🔐 Secure Access")
user_role = st.sidebar.selectbox("Access Level", ["Driver Portal", "Management Dashboard"])
user_name = st.sidebar.text_input("Name", value="Driver Admin" if user_role == "Management Dashboard" else "John Smith")

current_date = datetime.now().strftime("%Y-%m-%d")

# ==========================================
# 1. DRIVER PORTAL INTERFACE
# ==========================================
if user_role == "Driver Portal":
    
    # Check database to see driver's progress for today
    with sqlite3.connect(DB_FILE) as conn:
        has_pre_defect = not pd.read_sql_query("SELECT 1 FROM defects WHERE driver_name = ? AND date = ? AND check_type = 'Pre-Work'", conn, params=(user_name, current_date)).empty
        shift_data = pd.read_sql_query("SELECT status, start_time, end_time FROM shifts WHERE driver_name = ? AND date = ?", conn, params=(user_name, current_date))
    
    if shift_data.empty:
        shift_status = "Not Started"
    else:
        shift_status = shift_data.iloc[0]['status']

    # Step-by-Step UI Guidance
    st.info(f"Welcome back, **{user_name}**. Today's Date: `{current_date}`")
    
    # STEP 1: MANDATORY PRE-WORK DEFECT CHECK
    st.markdown("### 🛑 Step 1: Pre-Work Walkaround Inspection")
    if has_pre_defect:
        st.success("✅ Pre-work defect report submitted successfully for today.")
    else:
        st.warning("⚠️ You must complete your vehicle inspection before starting your shift time.")
        with st.form("pre_work_defect"):
            veh_reg = st.text_input("Vehicle Registration (Plate)").upper()
            defects_found = st.radio("Are any defects present before starting?", ["No Defects", "Defects Identified"])
            defect_desc = st.text_area("Provide details of pre-existing defects (if any)")
            
            if st.form_submit_button("Submit Pre-Work Inspection"):
                if not veh_reg:
                    st.error("Please enter your vehicle registration.")
                else:
                    with sqlite3.connect(DB_FILE) as conn:
                        conn.cursor().execute(
                            "INSERT INTO defects (driver_name, vehicle_reg, date, check_type, has_defects, details) VALUES (?, ?, ?, ?, ?, ?)",
                            (user_name, veh_reg, current_date, "Pre-Work", defects_found, defect_desc if defects_found == "Defects Identified" else "None")
                        )
                        conn.commit()
                    st.success("Inspection logged. Shift tracking unlocked!")
                    st.rerun()

    # STEP 2: SHIFT CLOCK-IN / CLOCK-OUT
    st.markdown("### 🕒 Step 2: Shift Time Tracking")
    
    # Disable tracking if pre-work check is missing
    disable_shift = not has_pre_defect
    
    col1, col2 = st.columns(2)
    
    with col1:
        if shift_status == "Not Started":
            if st.button("🚀 Start Shift & Record Time", disabled=disable_shift, use_container_width=True):
                now_time = datetime.now().strftime("%H:%M:%S")
                with sqlite3.connect(DB_FILE) as conn:
                    conn.cursor().execute(
                        "INSERT INTO shifts (driver_name, date, start_time, status) VALUES (?, ?, ?, 'Active')",
                        (user_name, current_date, now_time)
                    )
                    conn.commit()
                st.success(f"Shift started at {now_time}")
                st.rerun()
        elif shift_status in ["Active", "Completed"]:
            st.metric("Shift Start Time", shift_data.iloc[0]['start_time'])

    with col2:
        if shift_status == "Active":
            if st.button("🛑 Finish Shift & Record Time", use_container_width=True):
                now_time = datetime.now().strftime("%H:%M:%S")
                with sqlite3.connect(DB_FILE) as conn:
                    conn.cursor().execute(
                        "UPDATE shifts SET end_time = ?, status = 'Completed' WHERE driver_name = ? AND date = ?",
                        (now_time, user_name, current_date)
                    )
                    conn.commit()
                st.success(f"Shift closed at {now_time}")
                st.rerun()
        elif shift_status == "Completed":
            st.metric("Shift Finish Time", shift_data.iloc[0]['end_time'])
            st.success("🎉 Shift completed for today. Thank you!")

    # STEP 3: END OF SHIFT DEFECT UPDATES
    if shift_status == "Completed":
        st.markdown("### 🔧 Step 3: End of Shift Vehicle Status Updates")
        with sqlite3.connect(DB_FILE) as conn:
            has_post_defect = not pd.read_sql_query("SELECT 1 FROM defects WHERE driver_name = ? AND date = ? AND check_type = 'End of Shift'", conn, params=(user_name, current_date)).empty
        
        if has_post_defect:
            st.success("✅ End of shift updates recorded.")
        else:
            st.info("Log any new defects or changes that occurred during your shift below.")
            with st.form("post_work_defect"):
                post_defects = st.radio("Did any new defects occur during your routes today?", ["No New Defects", "New Defects to Report"])
                post_desc = st.text_area("Describe any updates or changes (e.g. tyre wear notice, new stone chip)")
                
                if st.form_submit_button("Submit End of Shift Update"):
                    with sqlite3.connect(DB_FILE) as conn:
                        # Fetch original registration used in the morning
                        reg_query = pd.read_sql_query("SELECT vehicle_reg FROM defects WHERE driver_name = ? AND date = ? LIMIT 1", conn, params=(user_name, current_date))
                        active_reg = reg_query.iloc[0]['vehicle_reg'] if not reg_query.empty else "UNKNOWN"
                        
                        conn.cursor().execute(
                            "INSERT INTO defects (driver_name, vehicle_reg, date, check_type, has_defects, details) VALUES (?, ?, ?, ?, ?, ?)",
                            (user_name, active_reg, current_date, "End of Shift", post_defects, post_desc if post_defects == "New Defects to Report" else "None")
                        )
                        conn.commit()
                    st.success("End of shift update saved.")
                    st.rerun()

# ==========================================
# 2. MANAGEMENT DASHBOARD INTERFACE
# ==========================================
elif user_role == "Management Dashboard":
    st.markdown("### 📊 Live Management Monitoring Station")
    
    tab1, tab2 = st.tabs(["🕒 Driver Timesheets", "🔧 Maintenance & Defect Tracking"])
    
    with tab1:
        st.subheader("Driver Daily Shift Logs")
        with sqlite3.connect(DB_FILE) as conn:
            df_shifts = pd.read_sql_query("SELECT driver_name as [Driver], date as [Date], start_time as [Start Time], end_time as [Finish Time], status as [Shift Status] FROM shifts ORDER BY date DESC", conn)
        if not df_shifts.empty:
            st.dataframe(df_shifts, use_container_width=True)
        else:
            st.info("No active driver shifts logged in the system yet.")

    with tab2:
        st.subheader("Reported Fleet Defect Records")
        with sqlite3.connect(DB_FILE) as conn:
            df_defects = pd.read_sql_query("SELECT id, driver_name as [Driver], vehicle_reg as [Reg], date as [Date], check_type as [Inspection Type], has_defects as [Status], details as [Defect Details], resolved_status as [Action State] FROM defects", conn)
        
        if not df_defects.empty:
            st.dataframe(df_defects, use_container_width=True)
            
            # Action controls to fix issues
            st.markdown("---")
            st.subheader("Update Defect Workshop Status")
            with st.form("action_form"):
                target_id = st.selectbox("Select Report ID to Update", df_defects['id'].tolist())
                next_action = st.selectbox("Set Maintenance Status", ["Open", "In Workshop", "Resolved / Roadworthy"])
                if st.form_submit_button("Update Records"):
                    with sqlite3.connect(DB_FILE) as conn:
                        conn.cursor().execute("UPDATE defects SET resolved_status = ? WHERE id = ?", (next_action, target_id))
                        conn.commit()
