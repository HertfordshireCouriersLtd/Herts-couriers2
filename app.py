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
col_acc, col_dec = st.columns(2)if col_acc.button("🟩 ACCEPT COMPANY B&B STAY OFFER"):simulate_email(COMPANY_EMAIL, "B&B Stay Request Accepted", f"Driver {login_user} has accepted a overnight rest stay package.")st.success("Lodging offer confirmed. The office has been dispatched confirmation details.")if col_dec.button("🟥 DECLINE OFFER (EMERGENCY ONLY)"):simulate_email(COMPANY_EMAIL, "B&B Stay Request REJECTED", f"Driver {login_user} declined overnight accommodation option!")st.warning("Rejection noticed filed with transport manager records.")if not active_activity.empty:current_duty = active_activity.iloc[0]['activity_type']started_at = active_activity.iloc[0]['start_time']st.success(f"Current Operational Mode: {current_duty} (Tracked since {started_at})")# Real-time tracking conditional guidanceif current_duty == "Waiting for next job":st.info("⏳ Operational Directive: Max limit for standby mode is 45 minutes. Alert the logistics dispatcher immediately if waiting extends past this.")if st.button("🟥 STOP CURRENT ACTIVITY & RECORD TIME", use_container_width=True):now_str = datetime.now().strftime("%H:%M:%S")start_dt = datetime.strptime(started_at, "%H:%M:%S")end_dt = datetime.strptime(now_str, "%H:%M:%S")delta_mins = int((end_dt - start_dt).total_seconds() / 60)with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("""UPDATE activities SET end_time = ?, cumulative_driving_mins = ?WHERE id = ?""", (now_str, delta_mins if current_duty == "Driving" else 0, active_activity.iloc[0]['id']))conn.commit()# Post-activity alertsif current_duty == "Driving" and (total_driving_mins + delta_mins) >= 540: # 9 Hours thresholdsimulate_email(COMPANY_EMAIL, "Driver Approaching 10H Limit", f"Warning: Driver {login_user} has reached {total_driving_mins + delta_mins} minutes driving.")st.rerun()else:st.subheader("Select Status Change Transition:")cols = st.columns(5)if cols[0].button("🚚 Driving Time"):with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("INSERT INTO activities (driver_name, date, activity_type, start_time) VALUES (?, ?, 'Driving', ?)", (login_user, current_date, datetime.now().strftime("%H:%M:%S")))conn.commit()st.rerun()if cols[1].button("📦 Warehouse Duties"):with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("INSERT INTO activities (driver_name, date, activity_type, start_time) VALUES (?, ?, 'Warehouse', ?)", (login_user, current_date, datetime.now().strftime("%H:%M:%S")))conn.commit()st.rerun()if cols[2].button("⏳ Waiting For Job"):with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("INSERT INTO activities (driver_name, date, activity_type, start_time) VALUES (?, ?, 'Waiting for next job', ?)", (login_user, current_date, datetime.now().strftime("%H:%M:%S")))conn.commit()simulate_email(COMPANY_EMAIL, "Driver Status: Waiting for Next Job", f"Driver {login_user} has toggled standby waiting status.")st.rerun()if cols[3].button("🥪 Unpaid Lunch Break"):with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("INSERT INTO activities (driver_name, date, activity_type, start_time) VALUES (?, ?, 'Lunch', ?)", (login_user, current_date, datetime.now().strftime("%H:%M:%S")))conn.commit()st.rerun()if cols[4].button("🏁 Terminate Shift"):st.subheader("Shift Conclusion Safety Verification")with st.form("end_shift_defects"):end_mil = st.number_input("Vehicle Ending Mileage", min_value=0, step=1)end_notes = st.text_area("Detail any mechanical shifts, new tyre wears, or route anomalies:")if st.form_submit_button("File Shift Wrap Up"):with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("""INSERT INTO defects_v3 (driver_name, date, check_type, mileage, clean_inside, clean_outside, straps_count, has_trolley, doors_locked, tyre_tread, fuel_full, details)VALUES (?, ?, 'End of Shift', ?, 'Passed', 'Passed', 5, 'Yes', 'Yes', 'Yes', 'Yes', ?)""", (login_user, current_date, end_mil, end_notes))conn.commit()st.success("Shift records closed securely. Drive safe!")st.stop()# 3. LEAVE PLANNING & STATUTORY BENEFITS HUBst.markdown("---")st.header("📅 Leave, Sickness & Entitlement Hub")st.metric("Remaining UK Statutory Holiday Allowance Balance", f"{user_record.iloc[0]['holiday_entitlement']} Days")with st.form("leave_request_form"):st.subheader("Book New Time Off Request")l_type = st.selectbox("Category", ["Holiday", "Sickness", "Absence"])start_l = st.date_input("First Date of Leave Period")end_l = st.date_input("Last Date of Leave Period")if st.form_submit_button("Process Leave Application"):days_diff = (start_l - datetime.now().date()).daystotal_days = (end_l - start_l).days + 1if l_type == "Holiday" and days_diff < 14:# Automatic system breach rejection rulewith sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("INSERT INTO leave_records (driver_name, leave_type, start_date, end_date, days_requested, status) VALUES (?, ?, ?, ?, ?, 'Automatically Rejected')", (login_user, l_type, str(start_l), str(end_l), total_days))conn.commit()st.error("❌ Application Automatically Rejected: Less than 14 days operational notice provided.")simulate_email(login_user, "Holiday Request Notice Failure", "Your leave application was denied due to the 14-day notice criteria. Please speak directly to the Director for manual authorisation codes.")else:with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("INSERT INTO leave_records (driver_name, leave_type, start_date, end_date, days_requested, status) VALUES (?, ?, ?, ?, ?, 'Approved')", (login_user, l_type, str(start_l), str(end_l), total_days))if l_type == "Holiday":conn.cursor().execute("UPDATE users SET holiday_entitlement = holiday_entitlement - ?, holiday_taken = holiday_taken + ? WHERE username = ?", (total_days, total_days, login_user))conn.commit()st.success("🎉 Leave allocation request processed successfully.")st.rerun()==========================================3. EXECUTIVE MANAGEMENT ARCHITECTURE==========================================elif user_role == "Manager":st.header("🎛️ Central Management Hub")m_tab1, m_tab2, m_tab3 = st.tabs(["📊 Compliance Auditing", "🔧 Vehicle Inspection Sheets", "📅 Leave Accounts Ledger"])with m_tab1:st.subheader("Daily Non-Compliance Inspection Alerts")# Find drivers who haven't completed a walkaround check todaywith sqlite3.connect(DB_FILE) as conn:all_drivers = pd.read_sql_query("SELECT username FROM users WHERE role = 'Driver'", conn)logged_today = pd.read_sql_query("SELECT DISTINCT driver_name FROM defects_v3 WHERE date = ?", conn, params=(datetime.now().strftime("%Y-%m-%d"),))compliant = logged_today['driver_name'].tolist()for d in all_drivers['username']:if d not in compliant:st.error(f"🚨 NON-COMPLIANCE WARNING: Driver {d} has not filed a Morning Defect Report today!")if st.button(f"Send Warning Notification to {d}"):simulate_email(d, "CRITICAL: Missing Defect Report Check", "You are operating outside procedure bounds. File your inspection layout inside the app immediately.")with m_tab2:st.subheader("Master Fleet Inspection Audit Log")with sqlite3.connect(DB_FILE) as conn:df_m_defects = pd.read_sql_query("SELECT * FROM defects_v3", conn)st.dataframe(df_m_defects, use_container_width=True)st.subheader("Verify/Approve Overdue Driver Licences")target_driver = st.text_input("Input Driver Account Code to Authorise")if st.button("🟩 Approve Driver Licence Validity (6 Months Extension)"):with sqlite3.connect(DB_FILE) as conn:conn.cursor().execute("UPDATE users SET last_licence_check = ?, licence_approved = 1 WHERE username = ?", (datetime.now().strftime("%Y-%m-%d"), target_driver))conn.commit()st.success(f"Driver account {target_driver} unlocked and verified.")with m_tab3:st.subheader("Corporate Fleet Leave Ledger")with sqlite3.connect(DB_FILE) as conn:df_m_leave = pd.read_sql_query("SELECT * FROM leave_records", conn)st.dataframe(df_m_leave, use_container_width=True)
