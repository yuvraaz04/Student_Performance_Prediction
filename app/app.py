import os
import sys
import random
import time
import io
import csv
import uuid
from datetime import datetime
from io import BytesIO
from werkzeug.utils import secure_filename

# Ensure app directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, jsonify, send_file, Response
)
from database import (
    get_db_connection, create_tables, seed_default_accounts, seed_student_data
)
from ml_model import predict_student_performance
from sms_service import send_sms

app = Flask(__name__)
app.secret_key = "studentiq-secret-key-2026-production"

# Profile picture upload config
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads", "profile_pics")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure database tables and initial test records exist
create_tables()
seed_default_accounts()


@app.context_processor
def inject_user_profiles():
    current_user = None
    current_student = None
    current_teacher = None
    current_avatar = None
    current_name = None
    if "user_id" in session:
        try:
            conn = get_db_connection()
            current_user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
            role = session.get("role")
            if role == "student":
                current_student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
                if current_student:
                    current_name = current_student["name"]
                    if current_student["profile_pic"]:
                        current_avatar = url_for("static", filename=current_student["profile_pic"])
            elif role == "teacher":
                current_teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()
                if current_teacher:
                    current_name = current_teacher["name"]
                    if current_teacher["profile_pic"]:
                        current_avatar = url_for("static", filename=current_teacher["profile_pic"])
            conn.close()
        except Exception:
            pass
    return dict(
        current_user=current_user,
        current_student=current_student,
        current_teacher=current_teacher,
        current_avatar=current_avatar,
        current_name=current_name
    )


# =========================================================
# HELPER FUNCTIONS FOR REPORTS
# =========================================================

def generate_pdf_report(student, academic_records, attendance_records, feedback=None, prediction=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    student = dict(student) if student else {}
    feedback = dict(feedback) if feedback else None
    prediction = dict(prediction) if prediction else None

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'RepTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=20,
        leading=24, textColor=colors.HexColor('#4f46e5'), alignment=TA_CENTER
    )
    sub_style = ParagraphStyle(
        'RepSub', parent=styles['Normal'], fontName='Helvetica', fontSize=10,
        leading=14, textColor=colors.HexColor('#6b7280'), alignment=TA_CENTER
    )
    h2_style = ParagraphStyle(
        'RepH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12,
        leading=16, textColor=colors.HexColor('#1f2937'), spaceBefore=8, spaceAfter=6
    )

    story = []
    story.append(Paragraph("StudentIQ Academic Performance Report", title_style))
    story.append(Paragraph("Machine Learning Predictive Analytics System", sub_style))
    story.append(Spacer(1, 15))

    # Calculate Summary Stats
    marks_list = [r["marks"] for r in academic_records if r["marks"] is not None]
    avg_marks = round(sum(marks_list) / len(marks_list), 2) if marks_list else 0.0
    att_list = [r["percentage"] for r in attendance_records if r["percentage"] is not None]
    avg_att = round(sum(att_list) / len(att_list), 2) if att_list else 0.0

    # Student Info Table
    info_data = [
        ["Student Name", student["name"], "Department", str(student.get("department") or "MSc IT")],
        ["Student Email", str(student.get("email") or "N/A"), "Semester", f"Semester {student.get('semester') or 1}"],
        ["Generated Date", datetime.now().strftime("%B %d, %Y"), "Gender", str(student.get("gender") or "N/A")]
    ]
    info_table = Table(info_data, colWidths=[105, 155, 105, 155])
    info_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # Executive Summary Cards
    pred_score = prediction["predicted_score"] if prediction else round(avg_marks * 0.9 + avg_att * 0.1, 1)
    risk_lvl = prediction["risk_level"] if prediction else ("Low Risk" if avg_marks >= 75 else ("Moderate Risk" if avg_marks >= 50 else "High Risk"))

    summary_data = [
        ["Average Marks", "Attendance Rate", "Predicted Score", "Risk Assessment"],
        [f"{avg_marks}%", f"{avg_att}%", f"{pred_score}%", risk_lvl]
    ]
    sum_table = Table(summary_data, colWidths=[130, 130, 130, 130])
    sum_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, 1), 11),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8fafc')),
    ]))
    story.append(Paragraph("Executive Performance Summary", h2_style))
    story.append(sum_table)
    story.append(Spacer(1, 12))

    # Academic & Attendance Records
    story.append(Paragraph("Subject-Wise Performance & Attendance", h2_style))
    acad_data = [["Subject", "Marks Obtained", "Status", "Attendance %"]]
    att_map = {r["subject"]: r["percentage"] for r in attendance_records}
    for row in academic_records:
        m = row["marks"]
        status = "Distinction" if m >= 75 else ("Pass" if m >= 50 else "Needs Support")
        att_pct = f"{att_map.get(row['subject'], avg_att)}%"
        acad_data.append([row["subject"], f"{m}%", status, att_pct])

    if len(acad_data) == 1:
        acad_data.append(["No academic records available", "-", "-", "-"])

    subj_table = Table(acad_data, colWidths=[180, 110, 120, 110])
    subj_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e7ff')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#3730a3')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(subj_table)
    story.append(Spacer(1, 12))

    # Feedback & Insights
    story.append(Paragraph("Faculty Feedback & Predictive Insights", h2_style))
    recom = (prediction.get("recommendation") if prediction and prediction.get("recommendation")
             else "Maintain regular class attendance and study consistency to sustain performance.")
    feed_activity = feedback["activity"] if feedback else "Active engagement in coursework and practical labs."
    feed_remarks = feedback["remarks"] if feedback else "Demonstrates sound analytical understanding."

    feedback_data = [
        ["Class Participation", feed_activity],
        ["Faculty Remarks", feed_remarks],
        ["Predictive Action Plan", recom]
    ]
    fb_table = Table(feedback_data, colWidths=[150, 370])
    fb_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(fb_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("StudentIQ • Predictive Analytics & Student Performance System", sub_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_csv_report(student, academic_records, attendance_records, prediction=None):
    student = dict(student) if student else {}
    prediction = dict(prediction) if prediction else None
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["StudentIQ Academic Report"])
    writer.writerow(["Student Name", student.get("name", "")])
    writer.writerow(["Email", student.get("email", "")])
    writer.writerow(["Department", student.get("department", "")])
    writer.writerow(["Semester", student.get("semester", "")])
    writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])
    writer.writerow(["Subject", "Marks", "Attendance Percentage"])
    att_map = {r["subject"]: r["percentage"] for r in attendance_records}
    for r in academic_records:
        writer.writerow([r["subject"], r["marks"], f"{att_map.get(r['subject'], 'N/A')}%"])
    writer.writerow([])
    if prediction:
        writer.writerow(["Prediction Insights"])
        writer.writerow(["Predicted Exam Score", f"{prediction.get('predicted_score')}%"])
        writer.writerow(["Performance Level", prediction.get("performance_level")])
        writer.writerow(["Risk Level", prediction.get("risk_level")])
        writer.writerow(["Recommendation", prediction.get("recommendation")])
    output.seek(0)
    return output.getvalue()


def generate_otp():
    """Generate a secure 6-digit numeric OTP"""
    return f"{random.randint(100000, 999999)}"


# =========================================================
# AUTHENTICATION (LOGIN, REGISTER, LOGOUT)
# =========================================================

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("email", "").strip()
        typed_phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "student").strip().lower()

        conn = get_db_connection()
        user = conn.execute("""
            SELECT * FROM users
            WHERE (email = ? OR phone = ?) AND password = ? AND role = ?
        """, (identifier, identifier, password, role)).fetchone()

        if user:
            # Determine destination phone number
            if typed_phone:
                user_phone = typed_phone
                # Update user record with the typed mobile number
                conn.execute("UPDATE users SET phone = ? WHERE id = ?", (typed_phone, user["id"]))
                if user["role"] == "student":
                    conn.execute("UPDATE students SET phone = ? WHERE user_id = ?", (typed_phone, user["id"]))
                else:
                    conn.execute("UPDATE teachers SET phone = ? WHERE user_id = ?", (typed_phone, user["id"]))
                conn.commit()
            elif user["phone"]:
                user_phone = user["phone"]
            else:
                user_phone = None
                if user["role"] == "student":
                    st = conn.execute("SELECT phone FROM students WHERE user_id = ?", (user["id"],)).fetchone()
                    if st and st["phone"]:
                        user_phone = st["phone"]
                else:
                    tc = conn.execute("SELECT phone FROM teachers WHERE user_id = ?", (user["id"],)).fetchone()
                    if tc and tc["phone"]:
                        user_phone = tc["phone"]

            conn.close()

            if not user_phone:
                flash("Please enter your mobile phone number in the form below so we can send your SMS verification code.", "warning")
                return render_template("Student/login.html")

            # Generate OTP and store temporary login session
            otp_code = generate_otp()
            session["pending_login"] = {
                "user_id": user["id"],
                "role": user["role"],
                "email": user["email"],
                "phone": user_phone
            }
            session["login_otp"] = otp_code
            session["login_otp_time"] = time.time()

            # Dispatch real or simulated SMS via SMS Gateway
            send_sms(user_phone, otp_code)

            flash(f"A 6-digit verification code has been sent via SMS to {user_phone}. Please check your mobile phone.", "info")
            return redirect(url_for("verify_login_otp"))

        conn.close()
        flash("Invalid email or phone number, password, or role. Please try again.", "danger")
        return render_template("Student/login.html")

    # If already logged in, redirect to dashboard unless requesting account switch
    if "user_id" in session:
        if request.args.get("switch") == "1":
            session.clear()
            return render_template("Student/login.html")
        if session.get("role") == "teacher":
            return redirect(url_for("teacher_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("Student/login.html")


@app.route("/verify-login-otp", methods=["GET", "POST"])
def verify_login_otp():
    pending = session.get("pending_login")
    if not pending:
        flash("No pending login session found. Please sign in first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        actual_otp = session.get("login_otp")

        if not entered_otp or entered_otp != actual_otp:
            flash("Invalid verification code. Please check your SMS and try again.", "danger")
            return render_template(
                "Student/verify_otp.html",
                purpose="login",
                email=pending.get("email"),
                phone=pending.get("phone"),
                action_url=url_for("verify_login_otp"),
                resend_url=url_for("resend_login_otp")
            )

        # Successful OTP authentication
        session.pop("login_otp", None)
        session.pop("login_otp_time", None)
        user_info = session.pop("pending_login")

        session["user_id"] = user_info["user_id"]
        session["role"] = user_info["role"]
        session["email"] = user_info["email"]

        flash("Authentication successful! Welcome back.", "success")
        if user_info["role"] == "teacher":
            return redirect(url_for("teacher_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template(
        "Student/verify_otp.html",
        purpose="login",
        email=pending.get("email"),
        phone=pending.get("phone"),
        action_url=url_for("verify_login_otp"),
        resend_url=url_for("resend_login_otp")
    )


@app.route("/resend-login-otp")
def resend_login_otp():
    if "pending_login" not in session:
        flash("No pending login session found.", "warning")
        return redirect(url_for("login"))

    new_otp = generate_otp()
    session["login_otp"] = new_otp
    session["login_otp_time"] = time.time()
    phone = session["pending_login"].get("phone")
    send_sms(phone, new_otp)
    flash(f"A new verification code has been sent via SMS to {phone}.", "info")
    return redirect(url_for("verify_login_otp"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role", "teacher").strip().lower()
        if role == "student":
            flash("Student self-registration is disabled. Student accounts must be created by faculty.", "warning")
            return render_template("Student/register.html")

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        department = request.form.get("department", "Computer Science").strip() or "Computer Science"

        if not name or not email or not password or not phone:
            flash("Please fill in all required fields, including your mobile phone number.", "danger")
            return render_template("Student/register.html")

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ? OR (phone = ? AND phone != '')", (email, phone)).fetchone()
        conn.close()

        if existing:
            flash("An account with this email address or phone number already exists. Please login.", "danger")
            return render_template("Student/register.html")

        # Generate OTP and store registration data in pending session
        otp_code = generate_otp()
        session["pending_registration"] = {
            "role": "teacher",
            "name": name,
            "email": email,
            "phone": phone,
            "password": password,
            "department": department
        }
        session["reg_otp"] = otp_code
        session["reg_otp_time"] = time.time()

        send_sms(phone, otp_code)
        flash(f"A 6-digit verification code has been sent via SMS to {phone}. Please enter it below to complete registration.", "info")
        return redirect(url_for("verify_signup_otp"))

    return render_template("Student/register.html")


@app.route("/verify-signup-otp", methods=["GET", "POST"])
def verify_signup_otp():
    pending = session.get("pending_registration")
    if not pending:
        flash("No pending registration found. Please register first.", "warning")
        return redirect(url_for("register"))

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        actual_otp = session.get("reg_otp")

        if not entered_otp or entered_otp != actual_otp:
            flash("Invalid verification code. Please check your SMS and try again.", "danger")
            return render_template(
                "Student/verify_otp.html",
                purpose="signup",
                email=pending.get("email"),
                phone=pending.get("phone"),
                action_url=url_for("verify_signup_otp"),
                resend_url=url_for("resend_signup_otp")
            )

        # Valid OTP: commit faculty/teacher to database
        role = pending.get("role", "teacher")
        name = pending.get("name")
        email = pending.get("email")
        phone = pending.get("phone", "")
        password = pending.get("password")
        department = pending.get("department", "Computer Science")

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (email, phone, password, role)
                VALUES (?, ?, ?, ?)
            """, (email, phone, password, role))
            user_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO teachers (user_id, name, email, phone, department)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, name, email, phone, department))
            teacher_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO teacher_settings (teacher_id, compact_view, student_overview, evaluation_alerts, performance_alerts, risk_alerts)
                VALUES (?, 1, 1, 1, 1, 1)
            """, (teacher_id,))
            conn.commit()
            conn.close()

            session.pop("pending_registration", None)
            session.pop("reg_otp", None)
            session.pop("reg_otp_time", None)

            flash(f"Faculty account created successfully for {name}! Please sign in.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            conn.close()
            flash(f"Registration failed: {str(e)}", "danger")
            return render_template("Student/register.html")

    return render_template(
        "Student/verify_otp.html",
        purpose="signup",
        email=pending.get("email"),
        phone=pending.get("phone"),
        action_url=url_for("verify_signup_otp"),
        resend_url=url_for("resend_signup_otp")
    )


@app.route("/resend-signup-otp")
def resend_signup_otp():
    if "pending_registration" not in session:
        flash("No pending registration session found.", "warning")
        return redirect(url_for("register"))

    new_otp = generate_otp()
    session["reg_otp"] = new_otp
    session["reg_otp_time"] = time.time()
    phone = session["pending_registration"].get("phone")
    send_sms(phone, new_otp)
    flash(f"A new verification code has been sent via SMS to {phone}.", "info")
    return redirect(url_for("verify_signup_otp"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        typed_phone = request.form.get("phone", "").strip()
        if not identifier:
            flash("Please enter your email address, username, or phone number.", "danger")
            return render_template("Student/forgot_password.html")

        conn = get_db_connection()
        user = conn.execute("""
            SELECT * FROM users WHERE email = ? OR phone = ?
        """, (identifier, identifier)).fetchone()

        if not user:
            conn.close()
            flash("No account found matching that email address or phone number.", "danger")
            return render_template("Student/forgot_password.html")

        if typed_phone:
            user_phone = typed_phone
            conn.execute("UPDATE users SET phone = ? WHERE id = ?", (typed_phone, user["id"]))
            if user["role"] == "student":
                conn.execute("UPDATE students SET phone = ? WHERE user_id = ?", (typed_phone, user["id"]))
            else:
                conn.execute("UPDATE teachers SET phone = ? WHERE user_id = ?", (typed_phone, user["id"]))
            conn.commit()
        elif user["phone"]:
            user_phone = user["phone"]
        else:
            user_phone = None
            if user["role"] == "student":
                st = conn.execute("SELECT phone FROM students WHERE user_id = ?", (user["id"],)).fetchone()
                if st and st["phone"]:
                    user_phone = st["phone"]
            else:
                tc = conn.execute("SELECT phone FROM teachers WHERE user_id = ?", (user["id"],)).fetchone()
                if tc and tc["phone"]:
                    user_phone = tc["phone"]

        conn.close()

        if not user_phone:
            flash("Please enter your mobile phone number in the form below so we can send your password reset code.", "warning")
            return render_template("Student/forgot_password.html")

        otp_code = generate_otp()
        session["reset_user_id"] = user["id"]
        session["reset_email"] = user["email"]
        session["reset_phone"] = user_phone
        session["reset_otp"] = otp_code
        session["reset_otp_time"] = time.time()

        send_sms(user_phone, otp_code)
        flash(f"A password reset verification code has been sent via SMS to {user_phone}. Please check your phone.", "info")
        return redirect(url_for("reset_password"))

    return render_template("Student/forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "reset_user_id" not in session:
        flash("No active password reset session found. Please enter your email or phone number.", "warning")
        return redirect(url_for("forgot_password"))

    reset_phone = session.get("reset_phone", "")
    reset_email = session.get("reset_email", "")
    current_otp = session.get("reset_otp", "")

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not entered_otp or entered_otp != current_otp:
            flash("Invalid SMS verification code. Please check your SMS and try again.", "danger")
            return render_template(
                "Student/reset_password.html",
                phone=reset_phone,
                email=reset_email
            )

        if not new_password or not confirm_password:
            flash("Please enter and confirm your new password.", "danger")
            return render_template(
                "Student/reset_password.html",
                phone=reset_phone,
                email=reset_email
            )

        if new_password != confirm_password:
            flash("Passwords do not match. Please verify and try again.", "danger")
            return render_template(
                "Student/reset_password.html",
                phone=reset_phone,
                email=reset_email
            )

        conn = get_db_connection()
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, session["reset_user_id"]))
        conn.commit()
        conn.close()

        session.pop("reset_user_id", None)
        session.pop("reset_email", None)
        session.pop("reset_phone", None)
        session.pop("reset_otp", None)
        session.pop("reset_otp_time", None)

        flash("Your password has been reset successfully! You can now sign in.", "success")
        return redirect(url_for("login"))

    return render_template(
        "Student/reset_password.html",
        phone=reset_phone,
        email=reset_email
    )


@app.route("/resend-reset-otp")
def resend_reset_otp():
    if "reset_user_id" not in session:
        flash("No active password reset session found.", "warning")
        return redirect(url_for("forgot_password"))

    new_otp = generate_otp()
    session["reset_otp"] = new_otp
    session["reset_otp_time"] = time.time()
    phone = session.get("reset_phone")
    send_sms(phone, new_otp)
    flash(f"A new password reset code has been sent via SMS to {phone}.", "info")
    return redirect(url_for("reset_password"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out successfully.", "success")
    return redirect(url_for("login"))


# =========================================================
# STUDENT SIDE ROUTES
# =========================================================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("""
            SELECT * FROM students WHERE user_id = ?
        """, (session["user_id"],)).fetchone()

    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if not student:
        conn.close()
        return "Student profile not found. Please contact your administrator."

    # Average marks
    avg_marks_res = conn.execute("""
        SELECT AVG(marks) AS average_marks FROM academic_records WHERE student_id = ?
    """, (student["id"],)).fetchone()
    average_marks = avg_marks_res["average_marks"] if (avg_marks_res and avg_marks_res["average_marks"] is not None) else 75.0

    # Average attendance
    avg_att_res = conn.execute("""
        SELECT AVG(percentage) AS average_attendance FROM attendance WHERE student_id = ?
    """, (student["id"],)).fetchone()
    average_attendance = avg_att_res["average_attendance"] if (avg_att_res and avg_att_res["average_attendance"] is not None) else 85.0

    avg_marks = round(float(average_marks), 1)
    avg_att = round(float(average_attendance), 1)

    # Total students
    total_students = conn.execute("SELECT COUNT(*) AS total FROM students").fetchone()["total"]

    # Subject performance list
    academic_records = conn.execute("""
        SELECT subject, marks FROM academic_records WHERE student_id = ? ORDER BY marks DESC
    """, (student["id"],)).fetchall()

    # Attendance records
    attendance_records = conn.execute("""
        SELECT subject, total_classes, attended_classes, percentage FROM attendance WHERE student_id = ? ORDER BY subject ASC
    """, (student["id"],)).fetchall()

    # Latest prediction
    prediction = conn.execute("""
        SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1
    """, (student["id"],)).fetchone()

    conn.close()

    if prediction:
        pred_dict = dict(prediction)
        pred_inputs = {
            "attendance": float(pred_dict.get("attendance")) if pred_dict.get("attendance") is not None else avg_att,
            "study_hours": float(pred_dict.get("study_hours")) if pred_dict.get("study_hours") is not None else 15.0,
            "previous_marks": float(pred_dict.get("previous_marks")) if pred_dict.get("previous_marks") is not None else avg_marks,
            "sleep_duration": float(pred_dict.get("sleep_hours")) if pred_dict.get("sleep_hours") is not None else 7.0,
            "social_media": float(pred_dict.get("social_media_hours")) if pred_dict.get("social_media_hours") is not None else 2.0,
            "participation": "medium",
            "gender": student["gender"] or "Female"
        }
        pred_details = predict_student_performance(pred_inputs)
        if pred_dict.get("predicted_score") is not None:
            pred_details["predicted_score"] = round(float(pred_dict["predicted_score"]), 1)
        if pred_dict.get("performance_level"):
            pred_details["status"] = pred_dict["performance_level"]
            pred_details["performance_category"] = pred_dict["performance_level"]
        if pred_dict.get("risk_level"):
            pred_details["risk_level"] = pred_dict["risk_level"]
        pred_details["meets_85_threshold"] = (pred_details["predicted_score"] >= 85.0)
        pred_details["threshold"] = "85%+" if pred_details["meets_85_threshold"] else "<85%"
    else:
        pred_inputs = {
            "attendance": avg_att if avg_att > 0 else 85.0,
            "study_hours": 15.0,
            "previous_marks": avg_marks if avg_marks > 0 else 75.0,
            "sleep_duration": 7.0,
            "social_media": 2.0,
            "participation": "medium",
            "gender": student["gender"] or "Female"
        }
        pred_details = predict_student_performance(pred_inputs)

    predicted_score = pred_details["predicted_score"]
    performance_level = pred_details["status"]
    risk_level = pred_details["risk_level"]

    return render_template(
        "Student/dashboard.html",
        student=student,
        average_marks=avg_marks,
        average_attendance=avg_att,
        total_students=total_students,
        academic_records=academic_records,
        attendance_records=attendance_records,
        prediction=prediction,
        pred_details=pred_details,
        predicted_score=predicted_score,
        performance_level=performance_level,
        risk_level=risk_level
    )


@app.route("/students")
def students():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()

    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if not student:
        conn.close()
        return "Student profile not found. Please contact your administrator."

    # Academic & attendance averages
    avg_marks = conn.execute("SELECT AVG(marks) AS avg FROM academic_records WHERE student_id = ?", (student["id"],)).fetchone()["avg"] or 0.0
    avg_att = conn.execute("SELECT AVG(percentage) AS avg FROM attendance WHERE student_id = ?", (student["id"],)).fetchone()["avg"] or 0.0

    # Classmates in same department
    peers = conn.execute("""
        SELECT id, name, department, semester, gender FROM students
        WHERE department = ? AND id != ?
        LIMIT 6
    """, (student["department"], student["id"])).fetchall()

    # Subject performance
    subjects = conn.execute("SELECT subject, marks FROM academic_records WHERE student_id = ?", (student["id"],)).fetchall()

    # Latest prediction
    prediction = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student["id"],)).fetchone()
    conn.close()

    predicted_score = prediction["predicted_score"] if prediction else round(avg_marks * 0.9 + avg_att * 0.1, 1)

    return render_template(
        "Student/students.html",
        student=student,
        average_marks=round(avg_marks, 1),
        average_attendance=round(avg_att, 1),
        predicted_score=round(predicted_score, 1),
        peers=peers,
        subjects=subjects
    )


@app.route("/attendance")
def student_attendance():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "teacher":
        return redirect(url_for("teacher_attendance"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if not student:
        conn.close()
        return "Student profile not found. Please contact your administrator."

    # Fetch attendance records for this student
    attendance_records = conn.execute("""
        SELECT id, subject, total_classes, attended_classes, percentage
        FROM attendance
        WHERE student_id = ?
        ORDER BY subject ASC
    """, (student["id"],)).fetchall()

    # Sync any subjects from academic_records missing in attendance
    academic_subs = conn.execute("SELECT DISTINCT subject FROM academic_records WHERE student_id = ?", (student["id"],)).fetchall()
    existing_subs = {r["subject"] for r in attendance_records}
    added_new = False
    for asub in academic_subs:
        s_name = asub["subject"]
        if s_name and s_name not in existing_subs:
            conn.execute("""
                INSERT INTO attendance (student_id, subject, total_classes, attended_classes, percentage)
                VALUES (?, ?, 40, 35, 87.5)
            """, (student["id"], s_name))
            added_new = True

    if not attendance_records and not academic_subs:
        default_subs = [
            ("Python Programming", 40, 36, 90.0),
            ("Database Management", 40, 35, 87.5),
            ("Data Structures & Algorithms", 40, 34, 85.0),
            ("Web Technologies", 40, 32, 80.0),
            ("Software Engineering", 40, 37, 92.5)
        ]
        for sub_name, tot, att, pct in default_subs:
            conn.execute("""
                INSERT INTO attendance (student_id, subject, total_classes, attended_classes, percentage)
                VALUES (?, ?, ?, ?, ?)
            """, (student["id"], sub_name, tot, att, pct))
        added_new = True

    if added_new:
        conn.commit()
        attendance_records = conn.execute("""
            SELECT id, subject, total_classes, attended_classes, percentage
            FROM attendance
            WHERE student_id = ?
            ORDER BY subject ASC
        """, (student["id"],)).fetchall()

    # Calculate detailed statistics
    records_data = []
    total_held = 0
    total_taken = 0
    eligible_count = 0

    for r in attendance_records:
        t_held = int(r["total_classes"] or 0)
        t_taken = int(r["attended_classes"] or 0)
        t_missed = max(0, t_held - t_taken)
        pct = float(r["percentage"]) if r["percentage"] is not None else (round(t_taken / t_held * 100, 1) if t_held > 0 else 0.0)

        is_eligible = pct >= 75.0
        if is_eligible:
            eligible_count += 1
            margin = max(0, (4 * t_taken - 3 * t_held) // 3) if t_held > 0 else 0
            advice = f"Safe margin: can miss {margin} more class(es)" if margin > 0 else "On track (at threshold)"
        else:
            needed = max(1, 3 * t_held - 4 * t_taken) if t_held > 0 else 1
            advice = f"Shortage: need to attend next {needed} class(es)"

        records_data.append({
            "id": r["id"],
            "subject": r["subject"],
            "total_classes": t_held,
            "attended_classes": t_taken,
            "missed_classes": t_missed,
            "percentage": pct,
            "is_eligible": is_eligible,
            "advice": advice
        })
        total_held += t_held
        total_taken += t_taken

    total_missed = max(0, total_held - total_taken)
    overall_percentage = round((total_taken / total_held * 100), 1) if total_held > 0 else 0.0
    shortage_count = len(records_data) - eligible_count

    # Profile picture
    current_avatar = None
    u = conn.execute("SELECT profile_pic FROM users WHERE id = ?", (session.get("user_id", 0),)).fetchone()
    if u and u["profile_pic"]:
        current_avatar = url_for("static", filename=u["profile_pic"])
    elif student and student["profile_pic"]:
        current_avatar = url_for("static", filename=student["profile_pic"])

    conn.close()

    return render_template(
        "Student/attendance.html",
        student=student,
        current_avatar=current_avatar,
        attendance_records=records_data,
        total_classes_held=total_held,
        total_classes_taken=total_taken,
        total_classes_missed=total_missed,
        overall_percentage=overall_percentage,
        subjects_eligible=eligible_count,
        subjects_at_risk=shortage_count
    )


@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()

    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if not student:
        conn.close()
        return "Student profile not found. Please contact your administrator."

    # Records
    academic_records = conn.execute("SELECT subject, marks FROM academic_records WHERE student_id = ? ORDER BY marks DESC", (student["id"],)).fetchall()
    attendance_records = conn.execute("SELECT subject, total_classes, attended_classes, percentage FROM attendance WHERE student_id = ?", (student["id"],)).fetchall()

    marks_list = [r["marks"] for r in academic_records if r["marks"] is not None]
    avg_marks = round(sum(marks_list) / len(marks_list), 1) if marks_list else 0.0

    att_pct_list = [r["percentage"] for r in attendance_records if r["percentage"] is not None]
    avg_att = round(sum(att_pct_list) / len(att_pct_list), 1) if att_pct_list else 0.0

    total_classes = sum(r["total_classes"] for r in attendance_records if r["total_classes"]) or 200
    attended_classes = sum(r["attended_classes"] for r in attendance_records if r["attended_classes"]) or int(total_classes * (avg_att / 100))
    absent_classes = max(0, total_classes - attended_classes)

    strongest_subject = academic_records[0]["subject"] if academic_records else "Python"
    weakest_subject = academic_records[-1]["subject"] if academic_records else "Statistics"

    # Prediction
    prediction = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student["id"],)).fetchone()

    conn.close()

    if prediction:
        pred_dict = dict(prediction)
        pred_inputs = {
            "attendance": float(pred_dict.get("attendance")) if pred_dict.get("attendance") is not None else avg_att,
            "study_hours": float(pred_dict.get("study_hours")) if pred_dict.get("study_hours") is not None else 15.0,
            "previous_marks": float(pred_dict.get("previous_marks")) if pred_dict.get("previous_marks") is not None else avg_marks,
            "sleep_duration": float(pred_dict.get("sleep_hours")) if pred_dict.get("sleep_hours") is not None else 7.0,
            "social_media": float(pred_dict.get("social_media_hours")) if pred_dict.get("social_media_hours") is not None else 2.0,
            "participation": "medium",
            "gender": student["gender"] or "Female"
        }
        pred_details = predict_student_performance(pred_inputs)
        if pred_dict.get("predicted_score") is not None:
            pred_details["predicted_score"] = round(float(pred_dict["predicted_score"]), 1)
        if pred_dict.get("performance_level"):
            pred_details["status"] = pred_dict["performance_level"]
            pred_details["performance_category"] = pred_dict["performance_level"]
        if pred_dict.get("risk_level"):
            pred_details["risk_level"] = pred_dict["risk_level"]
        pred_details["meets_85_threshold"] = (pred_details["predicted_score"] >= 85.0)
        pred_details["threshold"] = "85%+" if pred_details["meets_85_threshold"] else "<85%"
    else:
        pred_inputs = {
            "attendance": avg_att if avg_att > 0 else 85.0,
            "study_hours": 15.0,
            "previous_marks": avg_marks if avg_marks > 0 else 75.0,
            "sleep_duration": 7.0,
            "social_media": 2.0,
            "participation": "medium",
            "gender": student["gender"] or "Female"
        }
        pred_details = predict_student_performance(pred_inputs)

    predicted_score = pred_details["predicted_score"]
    performance_level = pred_details["status"]
    risk_level = pred_details["risk_level"]

    return render_template(
        "Student/analytics.html",
        student=student,
        average_marks=avg_marks,
        average_attendance=avg_att,
        predicted_score=round(predicted_score, 1),
        performance_level=performance_level,
        risk_level=risk_level,
        pred_details=pred_details,
        academic_records=academic_records,
        attendance_records=attendance_records,
        total_classes=total_classes,
        attended_classes=attended_classes,
        absent_classes=absent_classes,
        strongest_subject=strongest_subject,
        weakest_subject=weakest_subject
    )


@app.route("/prediction", methods=["GET", "POST"])
def prediction():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    flash("Predictive analytics features are managed by faculty instructors. Please contact your instructor for performance forecasts.", "info")
    return redirect(url_for("dashboard"))


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """AJAX API endpoint for real-time ML prediction"""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form.to_dict()

    attendance_val = float(data.get("attendance") or 85)
    study_hours_val = float(data.get("studyHours") or data.get("study_hours") or 15)
    previous_marks_val = float(data.get("previousMarks") or data.get("previous_marks") or 75)
    sleep_duration_val = float(data.get("sleep_duration") or data.get("sleep_hours") or data.get("sleepHours") or 7.0)
    social_media_val = float(data.get("social_media") or data.get("social_media_usage") or data.get("socialMediaHours") or 2.0)
    participation_val = data.get("participation", "medium")
    gender_val = data.get("gender")

    conn = get_db_connection()
    target_student_id = data.get("student_id")
    if not target_student_id and session.get("role") == "student":
        student = conn.execute("SELECT id, gender FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
        if student:
            target_student_id = student["id"]
            if not gender_val and student["gender"]:
                gender_val = student["gender"]
    elif target_student_id and not gender_val:
        st_row = conn.execute("SELECT gender FROM students WHERE id = ?", (target_student_id,)).fetchone()
        if st_row and st_row["gender"]:
            gender_val = st_row["gender"]

    if not gender_val:
        gender_val = "Female"

    result = predict_student_performance({
        "attendance": attendance_val,
        "study_hours": study_hours_val,
        "previous_marks": previous_marks_val,
        "sleep_duration": sleep_duration_val,
        "social_media": social_media_val,
        "participation": participation_val,
        "gender": gender_val
    })

    if target_student_id:
        try:
            conn.execute("""
                INSERT INTO predictions
                (student_id, predicted_score, performance_level, risk_level, prediction_date, attendance, study_hours, previous_marks, sleep_hours, social_media_hours)
                VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?)
            """, (
                int(target_student_id),
                result["predicted_score"],
                result["status"],
                result["risk_level"],
                attendance_val,
                study_hours_val,
                previous_marks_val,
                sleep_duration_val,
                social_media_val
            ))
            conn.commit()
        except Exception:
            pass

    conn.close()
    result["success"] = True
    return jsonify(result)


@app.route("/reports")
def reports():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()

    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if not student:
        conn.close()
        return "Student profile not found. Please contact your administrator."

    # Fetch faculty-generated reports for this student
    reports_list = conn.execute("""
        SELECT r.id, r.report_type, r.generated_at, s.name as student_name,
               COALESCE(t.name, 'Faculty Instructor') as faculty_name
        FROM reports r
        JOIN students s ON r.student_id = s.id
        LEFT JOIN users u ON r.generated_by = u.id
        LEFT JOIN teachers t ON t.user_id = u.id
        WHERE r.student_id = ?
        ORDER BY r.generated_at DESC
    """, (student["id"],)).fetchall()

    # If student has no reports, create an initial official faculty report
    if not reports_list:
        teacher_user = conn.execute("SELECT id FROM users WHERE role = 'teacher' LIMIT 1").fetchone()
        t_uid = teacher_user["id"] if teacher_user else 1
        conn.execute("""
            INSERT INTO reports (student_id, generated_by, report_type, generated_at)
            VALUES (?, ?, 'Performance', datetime('now'))
        """, (student["id"], t_uid))
        conn.commit()
        reports_list = conn.execute("""
            SELECT r.id, r.report_type, r.generated_at, s.name as student_name,
                   COALESCE(t.name, 'Faculty Instructor') as faculty_name
            FROM reports r
            JOIN students s ON r.student_id = s.id
            LEFT JOIN users u ON r.generated_by = u.id
            LEFT JOIN teachers t ON t.user_id = u.id
            WHERE r.student_id = ?
            ORDER BY r.generated_at DESC
        """, (student["id"],)).fetchall()

    total_reports = len(reports_list)
    perf_reports = sum(1 for r in reports_list if r["report_type"] == "Performance")
    risk_reports = sum(1 for r in reports_list if "Risk" in r["report_type"] or "At-Risk" in r["report_type"])

    conn.close()

    return render_template(
        "Student/reports.html",
        student=student,
        reports=reports_list,
        total_reports=total_reports,
        performance_reports=perf_reports,
        risk_reports=risk_reports
    )


@app.route("/student/reports/generate", methods=["POST"])
def student_generate_report():
    if "user_id" not in session:
        return redirect(url_for("login"))

    report_type = request.form.get("report_type", "Performance")
    conn = get_db_connection()
    student = conn.execute("SELECT id FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not student:
        student = conn.execute("SELECT id FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if student:
        conn.execute("""
            INSERT INTO reports (student_id, generated_by, report_type, generated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (student["id"], session["user_id"], report_type))
        conn.commit()
        flash(f"{report_type} report recorded successfully!", "success")
    conn.close()

    return redirect(url_for("reports"))


@app.route("/student/reports/export")
@app.route("/student/reports/download/current")
def student_export_faculty_report():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if not student:
        conn.close()
        flash("Student profile not found.", "danger")
        return redirect(url_for("reports"))

    # Latest report generated by faculty for this student
    report = conn.execute("""
        SELECT r.*, s.name, s.email, s.department, s.semester, s.gender,
               COALESCE(t.name, 'Faculty Instructor') as faculty_name
        FROM reports r
        JOIN students s ON r.student_id = s.id
        LEFT JOIN users u ON r.generated_by = u.id
        LEFT JOIN teachers t ON t.user_id = u.id
        WHERE r.student_id = ?
        ORDER BY r.id DESC LIMIT 1
    """, (student["id"],)).fetchone()

    if not report:
        teacher_user = conn.execute("SELECT id FROM users WHERE role = 'teacher' LIMIT 1").fetchone()
        t_uid = teacher_user["id"] if teacher_user else 1
        conn.execute("""
            INSERT INTO reports (student_id, generated_by, report_type, generated_at)
            VALUES (?, ?, 'Performance', datetime('now'))
        """, (student["id"], t_uid))
        conn.commit()
        report = conn.execute("""
            SELECT r.*, s.name, s.email, s.department, s.semester, s.gender,
                   COALESCE(t.name, 'Faculty Instructor') as faculty_name
            FROM reports r
            JOIN students s ON r.student_id = s.id
            LEFT JOIN users u ON r.generated_by = u.id
            LEFT JOIN teachers t ON t.user_id = u.id
            WHERE r.id = last_insert_rowid()
        """).fetchone()

    academic_records = conn.execute("SELECT subject, marks FROM academic_records WHERE student_id = ? ORDER BY subject", (student["id"],)).fetchall()
    attendance_records = conn.execute("SELECT subject, percentage FROM attendance WHERE student_id = ? ORDER BY subject", (student["id"],)).fetchall()
    feedback = conn.execute("SELECT * FROM student_feedback WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student["id"],)).fetchone()
    prediction = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student["id"],)).fetchone()
    conn.close()

    export_format = request.args.get("format", "pdf").lower()
    if export_format == "csv":
        csv_data = generate_csv_report(report, academic_records, attendance_records, prediction)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=StudentIQ_{report['name']}_Faculty_Report.csv"}
        )

    pdf_buffer = generate_pdf_report(report, academic_records, attendance_records, feedback, prediction)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"StudentIQ_{report['name']}_Faculty_Report.pdf",
        mimetype="application/pdf"
    )


@app.route("/student/reports/download/<int:report_id>")
def download_student_report(report_id=None):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    report = conn.execute("""
        SELECT r.*, s.name, s.email, s.department, s.semester, s.gender,
               COALESCE(t.name, 'Faculty Instructor') as faculty_name
        FROM reports r
        JOIN students s ON r.student_id = s.id
        LEFT JOIN users u ON r.generated_by = u.id
        LEFT JOIN teachers t ON t.user_id = u.id
        WHERE r.id = ? AND (r.student_id = ? OR ? IS NULL)
    """, (report_id, student["id"] if student else 0, student["id"] if student else None)).fetchone()

    if not report:
        conn.close()
        flash("Faculty report not found.", "danger")
        return redirect(url_for("reports"))

    academic_records = conn.execute("SELECT subject, marks FROM academic_records WHERE student_id = ? ORDER BY subject", (report["student_id"],)).fetchall()
    attendance_records = conn.execute("SELECT subject, percentage FROM attendance WHERE student_id = ? ORDER BY subject", (report["student_id"],)).fetchall()
    feedback = conn.execute("SELECT * FROM student_feedback WHERE student_id = ? ORDER BY id DESC LIMIT 1", (report["student_id"],)).fetchone()
    prediction = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (report["student_id"],)).fetchone()
    conn.close()

    pdf_buffer = generate_pdf_report(report, academic_records, attendance_records, feedback, prediction)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"StudentIQ_{report['name']}_Faculty_Report.pdf",
        mimetype="application/pdf"
    )


@app.route("/student/reports/download/<int:report_id>/csv")
@app.route("/student/reports/download/csv")
def download_student_report_csv(report_id=None):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    if report_id:
        report = conn.execute("""
            SELECT r.*, s.name, s.email, s.department, s.semester, s.gender,
                   COALESCE(t.name, 'Faculty Instructor') as faculty_name
            FROM reports r
            JOIN students s ON r.student_id = s.id
            LEFT JOIN users u ON r.generated_by = u.id
            LEFT JOIN teachers t ON t.user_id = u.id
            WHERE r.id = ?
        """, (report_id,)).fetchone()
    else:
        report = conn.execute("""
            SELECT r.*, s.name, s.email, s.department, s.semester, s.gender,
                   COALESCE(t.name, 'Faculty Instructor') as faculty_name
            FROM reports r
            JOIN students s ON r.student_id = s.id
            LEFT JOIN users u ON r.generated_by = u.id
            LEFT JOIN teachers t ON t.user_id = u.id
            WHERE r.student_id = ?
            ORDER BY r.id DESC LIMIT 1
        """, (student["id"] if student else 0,)).fetchone()

    if not report:
        conn.close()
        flash("Faculty report not found.", "danger")
        return redirect(url_for("reports"))

    academic_records = conn.execute("SELECT subject, marks FROM academic_records WHERE student_id = ?", (report["student_id"],)).fetchall()
    attendance_records = conn.execute("SELECT subject, percentage FROM attendance WHERE student_id = ?", (report["student_id"],)).fetchall()
    prediction = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (report["student_id"],)).fetchone()
    conn.close()

    csv_data = generate_csv_report(report, academic_records, attendance_records, prediction)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=StudentIQ_{report['name']}_Faculty_Report.csv"}
    )


@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = None
    if session.get("role") == "student":
        student = conn.execute("SELECT * FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()

    if not student:
        student = conn.execute("SELECT * FROM students ORDER BY id ASC LIMIT 1").fetchone()

    user = conn.execute("SELECT * FROM users WHERE id = ?", (student["user_id"] if student and student["user_id"] else session["user_id"],)).fetchone()
    student_settings = conn.execute("SELECT * FROM student_settings WHERE student_id = ?", (student["id"],)).fetchone() if student else None
    conn.close()

    return render_template(
        "Student/settings.html",
        student=student,
        user=user,
        settings=student_settings
    )


@app.route("/student/settings/update", methods=["POST"])
def update_student_settings():
    if "user_id" not in session:
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    department = request.form.get("department", "").strip()
    semester = int(request.form.get("semester", 1) or 1)

    if not name or not email:
        flash("Name and email cannot be empty.", "danger")
        return redirect(url_for("settings"))

    file = request.files.get("profile_pic")
    pic_rel_path = None
    if file and file.filename and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        unique_name = f"student_{session['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(save_path)
        pic_rel_path = f"uploads/profile_pics/{unique_name}"

    conn = get_db_connection()
    if pic_rel_path:
        conn.execute("""
            UPDATE students SET name = ?, email = ?, department = ?, semester = ?, profile_pic = ?
            WHERE user_id = ?
        """, (name, email, department, semester, pic_rel_path, session["user_id"]))
        conn.execute("UPDATE users SET email = ?, profile_pic = ? WHERE id = ?", (email, pic_rel_path, session["user_id"]))
    else:
        conn.execute("""
            UPDATE students SET name = ?, email = ?, department = ?, semester = ?
            WHERE user_id = ?
        """, (name, email, department, semester, session["user_id"]))
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Profile details updated successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/student/settings/profile-pic", methods=["POST"])
def update_student_profile_pic():
    if "user_id" not in session:
        return redirect(url_for("login"))

    file = request.files.get("profile_pic")
    if not file or not file.filename:
        flash("Please select an image file to upload.", "warning")
        return redirect(url_for("settings"))

    if not allowed_file(file.filename):
        flash("Invalid image format. Allowed formats: PNG, JPG, JPEG, GIF, WEBP.", "danger")
        return redirect(url_for("settings"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    unique_name = f"student_{session['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(save_path)
    rel_path = f"uploads/profile_pics/{unique_name}"

    conn = get_db_connection()
    old_row = conn.execute("SELECT profile_pic FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
    if old_row and old_row["profile_pic"]:
        old_path = os.path.join(app.root_path, "static", old_row["profile_pic"])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    conn.execute("UPDATE students SET profile_pic = ? WHERE user_id = ?", (rel_path, session["user_id"]))
    conn.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (rel_path, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Profile picture updated successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/student/settings/profile-pic/remove", methods=["POST"])
def remove_student_profile_pic():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    old_row = conn.execute("SELECT profile_pic FROM students WHERE user_id = ?", (session["user_id"],)).fetchone()
    if old_row and old_row["profile_pic"]:
        old_path = os.path.join(app.root_path, "static", old_row["profile_pic"])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    conn.execute("UPDATE students SET profile_pic = NULL WHERE user_id = ?", (session["user_id"],))
    conn.execute("UPDATE users SET profile_pic = NULL WHERE id = ?", (session["user_id"],))
    conn.commit()
    conn.close()

    flash("Profile picture removed successfully.", "info")
    return redirect(url_for("settings"))


@app.route("/student/settings/password", methods=["POST"])
def update_student_password():
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_pwd = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm_pwd = request.form.get("confirm_password", "")

    if not current_pwd or not new_pwd:
        flash("All password fields are required.", "danger")
        return redirect(url_for("settings"))

    if new_pwd != confirm_pwd:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("settings"))

    conn = get_db_connection()
    user = conn.execute("SELECT password FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not user or user["password"] != current_pwd:
        conn.close()
        flash("Incorrect current password.", "danger")
        return redirect(url_for("settings"))

    conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_pwd, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Password updated successfully!", "success")
    return redirect(url_for("settings"))


# =========================================================
# TEACHER SIDE ROUTES
# =========================================================

@app.route("/teacher")
def teacher_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        return redirect(url_for("dashboard"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()

    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()
    teacher_name = teacher["name"] if teacher else "Faculty"

    avg_perf = conn.execute("SELECT AVG(marks) AS avg FROM academic_records").fetchone()["avg"] or 0.0
    avg_att = conn.execute("SELECT AVG(percentage) AS avg FROM attendance").fetchone()["avg"] or 0.0

    # Fetch each student with their latest prediction, average marks, and average attendance
    query = """
        SELECT s.id, s.name, s.department, s.semester, s.email, s.gender,
               p.predicted_score, p.risk_level, p.performance_level,
               ROUND(AVG(a.marks), 1) AS avg_marks,
               ROUND(AVG(att.percentage), 1) AS avg_attendance
        FROM students s
        LEFT JOIN (
            SELECT p1.student_id, p1.predicted_score, p1.risk_level, p1.performance_level
            FROM predictions p1
            JOIN (
                SELECT student_id, MAX(id) as max_id
                FROM predictions
                GROUP BY student_id
            ) p2 ON p1.student_id = p2.student_id AND p1.id = p2.max_id
        ) p ON s.id = p.student_id
        LEFT JOIN academic_records a ON s.id = a.student_id
        LEFT JOIN attendance att ON s.id = att.student_id
        GROUP BY s.id
        ORDER BY s.name ASC
    """
    students_data = conn.execute(query).fetchall()

    excellent_students = []
    average_students = []
    poor_students = []

    for s in students_data:
        if s["predicted_score"] is not None:
            score = round(float(s["predicted_score"]), 1)
            risk = s["risk_level"] or ("High Risk" if score < 50 else ("Moderate Risk" if score < 75 else "Low Risk"))
        elif s["avg_marks"] is not None:
            score = round(float(s["avg_marks"]), 1)
            risk = "High Risk" if score < 50 else ("Moderate Risk" if score < 75 else "Low Risk")
        else:
            score = 75.0
            risk = "Low Risk"

        initials = "".join([part[0].upper() for part in s["name"].split() if part][:2]) if s["name"] else "ST"

        student_dict = {
            "id": s["id"],
            "name": s["name"],
            "department": s["department"] or "General",
            "semester": s["semester"] or 1,
            "score": score,
            "risk_level": risk,
            "performance_level": s["performance_level"] or ("Needs Support" if score < 50 else ("Average Performance" if score < 75 else "Good Performance")),
            "average_attendance": s["avg_attendance"] if s["avg_attendance"] is not None else 85.0,
            "initials": initials
        }

        if risk == "High Risk" or score < 50 or "Needs Support" in (s["performance_level"] or ""):
            poor_students.append(student_dict)
        elif score >= 75:
            excellent_students.append(student_dict)
        else:
            average_students.append(student_dict)

    total_students = len(students_data)
    excellent_count = len(excellent_students)
    average_count = len(average_students)
    poor_count = len(poor_students)

    # Students requiring attention: all poor/high-risk students sorted by score ascending (lowest first)
    attention_students = sorted(poor_students, key=lambda x: x["score"])

    # Distribution percentages for chart
    total_cat = total_students if total_students > 0 else 1
    excellent_pct = round((excellent_count / total_cat) * 100)
    average_pct = round((average_count / total_cat) * 100)
    poor_pct = max(0, 100 - excellent_pct - average_pct) if total_students > 0 else 0

    semester_performance = conn.execute("""
        SELECT semester, AVG(marks) AS average_marks
        FROM academic_records GROUP BY semester ORDER BY semester
    """).fetchall()

    semester_labels = [f"Sem {row['semester']}" for row in semester_performance]
    semester_values = [round(row['average_marks'], 1) for row in semester_performance]

    pending_evaluations = conn.execute("""
        SELECT COUNT(*) AS count FROM students s
        WHERE NOT EXISTS (SELECT 1 FROM student_feedback sf WHERE sf.student_id = s.id)
    """).fetchone()["count"]

    conn.close()

    return render_template(
        "Teacher/teacher_dashboard.html",
        teacher=teacher,
        teacher_name=teacher_name,
        total_students=total_students,
        average_performance=round(avg_perf, 1),
        average_attendance=round(avg_att, 1),
        at_risk_students=poor_count,
        excellent_count=excellent_count,
        average_count=average_count,
        poor_count=poor_count,
        excellent_pct=excellent_pct,
        average_pct=average_pct,
        poor_pct=poor_pct,
        attention_students=attention_students,
        semester_labels=semester_labels,
        semester_values=semester_values,
        high_performance=excellent_count,
        average_performance_count=average_count,
        needs_support=poor_count,
        pending_evaluations=pending_evaluations
    )


@app.route("/teacher/students")
def teacher_students():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        return redirect(url_for("students"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()

    students_list = conn.execute("""
        SELECT
            s.id, s.name, s.email, s.phone, s.department, s.semester, s.gender, s.profile_pic,
            COALESCE(ROUND((SELECT AVG(marks) FROM academic_records WHERE student_id = s.id), 1), 75.0) AS average_marks,
            COALESCE(ROUND((SELECT AVG(percentage) FROM attendance WHERE student_id = s.id), 1), 85.0) AS average_attendance,
            p.predicted_score, p.risk_level, p.performance_level
        FROM students s
        LEFT JOIN (
            SELECT p1.student_id, p1.predicted_score, p1.risk_level, p1.performance_level
            FROM predictions p1
            JOIN (
                SELECT student_id, MAX(id) as max_id
                FROM predictions
                GROUP BY student_id
            ) p2 ON p1.student_id = p2.student_id AND p1.id = p2.max_id
        ) p ON s.id = p.student_id
        ORDER BY s.id
    """).fetchall()

    avg_overall_res = conn.execute("SELECT AVG(marks) as avg FROM academic_records").fetchone()
    avg_overall = round(avg_overall_res["avg"], 1) if avg_overall_res and avg_overall_res["avg"] else 78.0

    conn.close()

    return render_template(
        "Teacher/teacher_students.html",
        teacher=teacher,
        students=students_list,
        avg_overall=avg_overall
    )


@app.route("/teacher/students/<int:student_id>")
def teacher_student_detail(student_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        return redirect(url_for("students"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))
    return redirect(url_for("teacher_students", view=student_id))


@app.route("/api/teacher/student/<int:student_id>")
def api_teacher_student_details(student_id):
    if "user_id" not in session or session.get("role") != "teacher":
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({"error": "Student not found"}), 404

    # Latest prediction
    prediction = conn.execute("""
        SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1
    """, (student_id,)).fetchone()

    # Academic records
    academic_records = conn.execute("""
        SELECT subject, marks, semester FROM academic_records WHERE student_id = ? ORDER BY marks DESC
    """, (student_id,)).fetchall()

    # Attendance records
    attendance_records = conn.execute("""
        SELECT subject, total_classes, attended_classes, percentage FROM attendance WHERE student_id = ?
    """, (student_id,)).fetchall()

    # Evaluations / feedback
    evaluations = conn.execute("""
        SELECT sf.id, sf.activity, sf.knowledge, sf.personality, sf.suggestion, sf.remarks, t.name as teacher_name
        FROM student_feedback sf
        LEFT JOIN teachers t ON sf.teacher_id = t.id
        WHERE sf.student_id = ?
        ORDER BY sf.id DESC LIMIT 5
    """, (student_id,)).fetchall()

    marks_list = [r["marks"] for r in academic_records if r["marks"] is not None]
    avg_marks = round(sum(marks_list) / len(marks_list), 1) if marks_list else 75.0

    att_list = [r["percentage"] for r in attendance_records if r["percentage"] is not None]
    avg_att = round(sum(att_list) / len(att_list), 1) if att_list else 85.0

    conn.close()

    st_dict = dict(student)
    pred_dict = dict(prediction) if prediction else None

    if pred_dict and pred_dict.get("risk_level"):
        risk_lvl = pred_dict["risk_level"]
    elif avg_marks < 50:
        risk_lvl = "High Risk"
    elif avg_marks < 75:
        risk_lvl = "Medium Risk"
    else:
        risk_lvl = "Low Risk"

    return jsonify({
        "success": True,
        "student": st_dict,
        "average_marks": avg_marks,
        "average_attendance": avg_att,
        "risk_level": risk_lvl,
        "prediction": pred_dict,
        "academic_records": [dict(r) for r in academic_records],
        "attendance_records": [dict(r) for r in attendance_records],
        "evaluations": [dict(e) for e in evaluations]
    })


@app.route("/teacher/students/edit/<int:student_id>", methods=["POST"])
def teacher_edit_student(student_id):
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "MSc IT").strip()
    try:
        semester = int(request.form.get("semester", 1) or 1)
    except (ValueError, TypeError):
        semester = 1
    gender = request.form.get("gender", "Female").strip()

    if not name or not email:
        flash("Student name and email are required.", "danger")
        return redirect(url_for("teacher_students"))

    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        flash("Student record not found.", "danger")
        return redirect(url_for("teacher_students"))

    # Check for duplicate email among other users
    existing = conn.execute("""
        SELECT id FROM users 
        WHERE email = ? AND id != ?
    """, (email, student["user_id"] or 0)).fetchone()

    if existing:
        conn.close()
        flash("Another user account with this email address already exists.", "danger")
        return redirect(url_for("teacher_students"))

    conn.execute("""
        UPDATE students
        SET name = ?, email = ?, phone = ?, department = ?, semester = ?, gender = ?
        WHERE id = ?
    """, (name, email, phone, department, semester, gender, student_id))

    if student["user_id"]:
        conn.execute("""
            UPDATE users
            SET email = ?, phone = ?
            WHERE id = ?
        """, (email, phone, student["user_id"]))

    conn.commit()
    conn.close()

    flash(f"Student '{name}' updated successfully!", "success")
    return redirect(url_for("teacher_students"))


@app.route("/teacher/students/delete/<int:student_id>", methods=["POST"])
def teacher_delete_student(student_id):
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        flash("Student record not found.", "danger")
        return redirect(url_for("teacher_students"))

    student_name = student["name"]
    user_id = student["user_id"]

    conn.execute("DELETE FROM academic_records WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM predictions WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM reports WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM student_feedback WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM student_settings WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    if user_id:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    conn.commit()
    conn.close()

    flash(f"Student '{student_name}' and all associated records have been deleted.", "info")
    return redirect(url_for("teacher_students"))


@app.route("/teacher/students/add", methods=["POST"])
def teacher_add_student():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "MSc IT").strip()
    semester = int(request.form.get("semester", 1) or 1)
    gender = request.form.get("gender", "Female").strip()
    password = request.form.get("password", "1234").strip()

    if not name or not email:
        flash("Name and email are required to add a student.", "danger")
        return redirect(url_for("teacher_students"))

    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE email = ? OR (phone = ? AND phone != '')", (email, phone)).fetchone()
    if existing:
        conn.close()
        flash("A user with this email or phone number already exists.", "danger")
        return redirect(url_for("teacher_students"))

    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (email, phone, password, role) VALUES (?, ?, ?, ?)", (email, phone, password, "student"))
    user_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO students (user_id, name, email, phone, department, semester, gender)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, email, phone, department, semester, gender))
    student_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Seed records
    seed_student_data(student_id, semester=semester)

    flash(f"Student {name} enrolled successfully with phone {phone or 'N/A'}!", "success")
    return redirect(url_for("teacher_students"))


# =========================================================
# TEACHER ATTENDANCE MANAGEMENT ROUTES
# =========================================================

@app.route("/teacher/attendance")
def teacher_attendance():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        flash("Faculty attendance records are restricted to instructors. You have been directed to your attendance tracker.", "info")
        return redirect(url_for("student_attendance"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()

    search_query = request.args.get("search", "").strip()
    dept_filter = request.args.get("department", "").strip()
    sem_filter = request.args.get("semester", "").strip()
    highlight_id = request.args.get("highlight", type=int)
    highlight_subject = request.args.get("highlight_subject", "").strip()

    # Query attendance records with student details
    query = """
        SELECT att.id AS attendance_id, att.student_id, att.subject,
               att.total_classes, att.attended_classes, att.percentage, att.updated_at,
               s.name AS student_name, s.email AS student_email,
               s.department, s.semester
        FROM attendance att
        JOIN students s ON att.student_id = s.id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (s.name LIKE ? OR s.email LIKE ? OR att.subject LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term, term])

    if dept_filter:
        query += " AND s.department = ?"
        params.append(dept_filter)

    if sem_filter:
        try:
            query += " AND s.semester = ?"
            params.append(int(sem_filter))
        except ValueError:
            pass

    if highlight_id:
        query += " ORDER BY (CASE WHEN att.id = ? THEN 0 ELSE 1 END), COALESCE(att.updated_at, '') DESC, att.id DESC"
        params.append(highlight_id)
    elif highlight_subject:
        query += " ORDER BY (CASE WHEN att.subject = ? THEN 0 ELSE 1 END), COALESCE(att.updated_at, '') DESC, att.id DESC"
        params.append(highlight_subject)
    else:
        query += " ORDER BY COALESCE(att.updated_at, '') DESC, att.id DESC"
    attendance_records = conn.execute(query, params).fetchall()

    # All students list for Add Attendance modal
    students_list = conn.execute("SELECT id, name, department, semester FROM students ORDER BY name").fetchall()

    # Summary statistics across all records
    all_att = conn.execute("SELECT percentage FROM attendance").fetchall()
    total_records = len(all_att)
    if total_records > 0:
        valid_pcts = [r["percentage"] for r in all_att if r["percentage"] is not None]
        avg_overall = round(sum(valid_pcts) / len(valid_pcts), 1) if valid_pcts else 0.0
        high_att_count = sum(1 for p in valid_pcts if p >= 85)
        mod_att_count = sum(1 for p in valid_pcts if 75 <= p < 85)
        low_att_count = sum(1 for p in valid_pcts if p < 75)
    else:
        avg_overall = 0.0
        high_att_count = 0
        mod_att_count = 0
        low_att_count = 0

    # Unique departments & semesters for filtering
    departments = [r["department"] for r in conn.execute("SELECT DISTINCT department FROM students WHERE department IS NOT NULL AND department != '' ORDER BY department").fetchall()]
    semesters = [r["semester"] for r in conn.execute("SELECT DISTINCT semester FROM students WHERE semester IS NOT NULL ORDER BY semester").fetchall()]

    conn.close()

    return render_template(
        "Teacher/teacher_attendance.html",
        teacher=teacher,
        attendance_records=attendance_records,
        students=students_list,
        avg_overall=avg_overall,
        high_att_count=high_att_count,
        mod_att_count=mod_att_count,
        low_att_count=low_att_count,
        departments=departments,
        semesters=semesters,
        search_query=search_query,
        selected_dept=dept_filter,
        selected_sem=sem_filter,
        highlight_id=highlight_id,
        highlight_subject=highlight_subject
    )


@app.route("/teacher/attendance/add", methods=["POST"])
def teacher_attendance_add():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    student_id = request.form.get("student_id")
    subject = request.form.get("subject", "").strip()
    try:
        total_classes = int(request.form.get("total_classes", 40))
        attended_classes = int(request.form.get("attended_classes", 0))
    except (ValueError, TypeError):
        flash("Total classes and attended classes must be valid numbers.", "danger")
        return redirect(url_for("teacher_attendance"))

    if not student_id or not subject:
        flash("Student and Subject are required.", "danger")
        return redirect(url_for("teacher_attendance"))

    if total_classes <= 0:
        flash("Total classes must be greater than 0.", "danger")
        return redirect(url_for("teacher_attendance"))

    if attended_classes < 0 or attended_classes > total_classes:
        flash("Attended classes must be between 0 and total classes.", "danger")
        return redirect(url_for("teacher_attendance"))

    percentage = round((attended_classes / total_classes) * 100.0, 1)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attendance (student_id, subject, total_classes, attended_classes, percentage, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, subject, total_classes, attended_classes, percentage, now_str))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    flash(f"Attendance record for '{subject}' added successfully!", "success")
    return redirect(url_for("teacher_attendance", highlight=new_id))


@app.route("/teacher/attendance/update", methods=["POST"])
def teacher_attendance_update():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    attendance_id = request.form.get("attendance_id")
    subject = request.form.get("subject", "").strip()
    try:
        total_classes = int(request.form.get("total_classes", 40))
        attended_classes = int(request.form.get("attended_classes", 0))
    except (ValueError, TypeError):
        flash("Total and attended classes must be valid numbers.", "danger")
        return redirect(url_for("teacher_attendance"))

    if not attendance_id:
        flash("Invalid attendance record ID.", "danger")
        return redirect(url_for("teacher_attendance"))

    if total_classes <= 0:
        flash("Total classes must be greater than 0.", "danger")
        return redirect(url_for("teacher_attendance"))

    if attended_classes < 0 or attended_classes > total_classes:
        flash("Attended classes must be between 0 and total classes.", "danger")
        return redirect(url_for("teacher_attendance"))

    percentage = round((attended_classes / total_classes) * 100.0, 1)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    conn.execute("""
        UPDATE attendance
        SET subject = ?, total_classes = ?, attended_classes = ?, percentage = ?, updated_at = ?
        WHERE id = ?
    """, (subject, total_classes, attended_classes, percentage, now_str, attendance_id))
    conn.commit()
    conn.close()

    flash("Attendance record updated successfully!", "success")
    return redirect(url_for("teacher_attendance", highlight=attendance_id))


@app.route("/teacher/attendance/delete/<int:attendance_id>", methods=["POST"])
def teacher_attendance_delete(attendance_id):
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM attendance WHERE id = ?", (attendance_id,))
    conn.commit()
    conn.close()

    flash("Attendance record removed successfully.", "success")
    return redirect(url_for("teacher_attendance"))


@app.route("/teacher/attendance/mark-single", methods=["POST"])
def teacher_attendance_mark_single():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    attendance_id = request.form.get("attendance_id")
    status = request.form.get("status", "present").lower().strip()

    if not attendance_id:
        flash("Invalid attendance record.", "danger")
        return redirect(url_for("teacher_attendance"))

    conn = get_db_connection()
    rec = conn.execute("""
        SELECT att.*, s.name as student_name
        FROM attendance att
        JOIN students s ON att.student_id = s.id
        WHERE att.id = ?
    """, (attendance_id,)).fetchone()

    if not rec:
        conn.close()
        flash("Attendance record not found.", "danger")
        return redirect(url_for("teacher_attendance"))

    total = (rec["total_classes"] or 0) + 1
    attended = (rec["attended_classes"] or 0) + (1 if status == "present" else 0)
    percentage = round((attended / total) * 100.0, 1)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        UPDATE attendance
        SET total_classes = ?, attended_classes = ?, percentage = ?, updated_at = ?
        WHERE id = ?
    """, (total, attended, percentage, now_str, attendance_id))
    conn.commit()
    conn.close()

    flash(f"Marked {rec['student_name']} as {status.upper()} in {rec['subject']}! Now {attended}/{total} classes ({percentage}%).", "success")
    return redirect(url_for("teacher_attendance", highlight=attendance_id))


@app.route("/teacher/attendance/mark-class", methods=["POST"])
def teacher_attendance_mark_class():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    subject = request.form.get("subject", "").strip()
    if not subject:
        flash("Please select or enter a subject to mark class attendance.", "danger")
        return redirect(url_for("teacher_attendance"))

    all_student_ids = request.form.getlist("all_student_ids")
    present_student_ids = set(request.form.getlist("present_student_ids"))

    if not all_student_ids:
        flash("No students were selected for attendance.", "danger")
        return redirect(url_for("teacher_attendance"))

    conn = get_db_connection()
    present_count = 0
    absent_count = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for sid_str in all_student_ids:
        try:
            sid = int(sid_str)
        except ValueError:
            continue

        is_present = str(sid) in present_student_ids
        if is_present:
            present_count += 1
        else:
            absent_count += 1

        existing = conn.execute("""
            SELECT id, total_classes, attended_classes
            FROM attendance
            WHERE student_id = ? AND subject = ?
        """, (sid, subject)).fetchone()

        if existing:
            tot = (existing["total_classes"] or 0) + 1
            att = (existing["attended_classes"] or 0) + (1 if is_present else 0)
            pct = round((att / tot) * 100.0, 1)
            conn.execute("""
                UPDATE attendance
                SET total_classes = ?, attended_classes = ?, percentage = ?, updated_at = ?
                WHERE id = ?
            """, (tot, att, pct, now_str, existing["id"]))
        else:
            tot = 1
            att = 1 if is_present else 0
            pct = round((att / tot) * 100.0, 1)
            conn.execute("""
                INSERT INTO attendance (student_id, subject, total_classes, attended_classes, percentage, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sid, subject, tot, att, pct, now_str))

    conn.commit()
    conn.close()

    flash(f"Class attendance for '{subject}' recorded successfully! {present_count} Present, {absent_count} Absent out of {len(all_student_ids)} students.", "success")
    return redirect(url_for("teacher_attendance", highlight_subject=subject))


@app.route("/teacher/prediction", methods=["GET", "POST"])
def teacher_prediction():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        flash("Predictive analytics are managed by faculty instructors. You can view your performance under Analytics.", "info")
        return redirect(url_for("analytics"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()

    # Get all students with their average marks and attendance
    students_list = conn.execute("""
        SELECT
            s.id, s.name, s.email, s.department, s.semester, s.gender,
            COALESCE(ROUND((SELECT AVG(marks) FROM academic_records WHERE student_id = s.id), 1), 75.0) AS average_marks,
            COALESCE(ROUND((SELECT AVG(percentage) FROM attendance WHERE student_id = s.id), 1), 85.0) AS average_attendance
        FROM students s
        ORDER BY s.name
    """).fetchall()

    selected_student_id_raw = request.args.get("student_id") or request.form.get("student_id")
    selected_student_id = None
    selected_student = None
    latest_prediction = None

    if selected_student_id_raw:
        try:
            selected_student_id = int(selected_student_id_raw)
            for s in students_list:
                if s["id"] == selected_student_id:
                    selected_student = s
                    break
            if selected_student:
                latest_prediction = conn.execute("""
                    SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1
                """, (selected_student_id,)).fetchone()
        except (ValueError, TypeError):
            selected_student_id = None

    result = None
    if request.method == "POST":
        student_id_val = request.form.get("student_id")
        attendance_val = float(request.form.get("attendance") or 85.0)
        study_hours_val = float(request.form.get("studyHours") or request.form.get("study_hours") or 15.0)
        previous_marks_val = float(request.form.get("previousMarks") or request.form.get("previous_marks") or 75.0)
        sleep_duration_val = float(request.form.get("sleep_duration") or request.form.get("sleep_hours") or request.form.get("sleepHours") or 7.0)
        social_media_val = float(request.form.get("social_media") or request.form.get("social_media_usage") or request.form.get("socialMediaHours") or 2.0)
        participation_val = request.form.get("participation", "medium")
        gender_val = request.form.get("gender")
        if not gender_val and student_id_val:
            try:
                sid = int(student_id_val)
                st_row = conn.execute("SELECT gender FROM students WHERE id = ?", (sid,)).fetchone()
                if st_row and st_row["gender"]:
                    gender_val = st_row["gender"]
            except Exception:
                pass
        if not gender_val:
            gender_val = "Female"

        result = predict_student_performance({
            "attendance": attendance_val,
            "study_hours": study_hours_val,
            "previous_marks": previous_marks_val,
            "sleep_duration": sleep_duration_val,
            "social_media": social_media_val,
            "participation": participation_val,
            "gender": gender_val
        })

        if student_id_val:
            try:
                sid = int(student_id_val)
                conn.execute("""
                    INSERT INTO predictions
                    (student_id, predicted_score, performance_level, risk_level, prediction_date, attendance, study_hours, previous_marks, sleep_hours, social_media_hours)
                    VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?)
                """, (
                    sid,
                    result["predicted_score"],
                    result["status"],
                    result["risk_level"],
                    attendance_val,
                    study_hours_val,
                    previous_marks_val,
                    sleep_duration_val,
                    social_media_val
                ))
                conn.commit()
                latest_prediction = conn.execute("""
                    SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1
                """, (sid,)).fetchone()
            except Exception:
                pass

    conn.close()

    return render_template(
        "Teacher/teacher_prediction.html",
        teacher=teacher,
        students=students_list,
        selected_student=selected_student,
        selected_student_id=selected_student_id,
        latest_prediction=latest_prediction,
        result=result
    )


@app.route("/teacher/evaluation")
def teacher_evaluation():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        flash("Student evaluations are conducted by faculty instructors.", "info")
        return redirect(url_for("dashboard"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()
    students_list = conn.execute("SELECT id, name, email, department, semester FROM students ORDER BY name").fetchall()

    past_feedback = conn.execute("""
        SELECT sf.*, s.name as student_name, s.department
        FROM student_feedback sf
        JOIN students s ON sf.student_id = s.id
        ORDER BY sf.id DESC LIMIT 10
    """).fetchall()

    conn.close()

    return render_template(
        "Teacher/teacher_evaluation.html",
        teacher=teacher,
        students=students_list,
        past_feedback=past_feedback
    )


@app.route("/teacher/evaluation/submit", methods=["POST"])
def teacher_evaluation_submit():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    student_id = request.form.get("student_id")
    activity = request.form.get("activity")
    knowledge = request.form.get("knowledge")
    personality = request.form.get("personality")
    suggestion = request.form.get("suggestion")
    remarks = request.form.get("remarks", "")

    if not student_id:
        flash("Please select a student to evaluate.", "danger")
        return redirect(url_for("teacher_evaluation"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT id FROM teachers WHERE user_id = ? LIMIT 1", (session["user_id"],)).fetchone()
    teacher_id = teacher["id"] if teacher else 1

    conn.execute("""
        INSERT INTO student_feedback
        (student_id, teacher_id, activity, knowledge, personality, suggestion, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (student_id, teacher_id, activity, knowledge, personality, suggestion, remarks))
    conn.commit()
    conn.close()

    flash("Student evaluation submitted successfully!", "success")
    return redirect(url_for("teacher_evaluation"))


@app.route("/teacher/analytics")
def teacher_analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        return redirect(url_for("analytics"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()

    total_students = conn.execute("SELECT COUNT(*) AS total FROM students").fetchone()["total"]
    avg_performance = conn.execute("SELECT AVG(marks) AS avg FROM academic_records").fetchone()["avg"] or 0.0
    avg_attendance = conn.execute("SELECT AVG(percentage) AS avg FROM attendance").fetchone()["avg"] or 0.0

    student_performance = conn.execute("""
        SELECT s.id, s.name, AVG(a.marks) AS average_marks
        FROM students s LEFT JOIN academic_records a ON s.id = a.student_id
        GROUP BY s.id
    """).fetchall()

    high_risk, medium_risk, low_risk = 0, 0, 0
    for s in student_performance:
        m = s["average_marks"]
        if m is not None:
            if m < 50:
                high_risk += 1
            elif m < 75:
                medium_risk += 1
            else:
                low_risk += 1

    total_evaluations = conn.execute("SELECT COUNT(*) AS total FROM student_feedback").fetchone()["total"]
    completed_evaluations = conn.execute("SELECT COUNT(DISTINCT student_id) AS total FROM student_feedback").fetchone()["total"]
    pending_evaluations = max(0, total_students - completed_evaluations)

    subject_performance = conn.execute("""
        SELECT subject, AVG(marks) AS average_marks FROM academic_records
        GROUP BY subject ORDER BY average_marks DESC
    """).fetchall()
    subject_labels = [r["subject"] for r in subject_performance]
    subject_values = [round(r["average_marks"], 1) for r in subject_performance]

    class_performance = conn.execute("""
        SELECT semester, AVG(marks) AS average_marks FROM academic_records
        GROUP BY semester ORDER BY semester
    """).fetchall()
    class_labels = [f"Sem {r['semester']}" for r in class_performance]
    class_values = [round(r["average_marks"], 1) for r in class_performance]

    conn.close()

    return render_template(
        "Teacher/teacher_analytics.html",
        teacher=teacher,
        total_students=total_students,
        average_performance=round(avg_performance, 1),
        average_attendance=round(avg_attendance, 1),
        high_risk=high_risk,
        medium_risk=medium_risk,
        low_risk=low_risk,
        total_evaluations=total_evaluations,
        completed_evaluations=completed_evaluations,
        pending_evaluations=pending_evaluations,
        subject_labels=subject_labels,
        subject_values=subject_values,
        class_labels=class_labels,
        class_values=class_values
    )


@app.route("/teacher/reports")
def teacher_reports():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        return redirect(url_for("reports"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()

    total_reports = conn.execute("SELECT COUNT(*) AS total FROM reports").fetchone()["total"]
    performance_reports = conn.execute("SELECT COUNT(*) AS total FROM reports WHERE report_type = 'Performance'").fetchone()["total"]
    evaluation_reports = conn.execute("SELECT COUNT(*) AS total FROM reports WHERE report_type = 'Evaluation'").fetchone()["total"]

    at_risk_students = conn.execute("""
        SELECT COUNT(*) AS total FROM (
            SELECT student_id FROM academic_records GROUP BY student_id HAVING AVG(marks) < 50
        )
    """).fetchone()["total"]

    recent_reports = conn.execute("""
        SELECT r.id, r.student_id, r.report_type, r.generated_at, s.name AS student_name
        FROM reports r
        LEFT JOIN students s ON r.student_id = s.id
        ORDER BY r.generated_at DESC
        LIMIT 25
    """).fetchall()

    students_list = conn.execute("SELECT id, name, department, semester FROM students ORDER BY name").fetchall()

    conn.close()

    return render_template(
        "Teacher/teacher_reports.html",
        teacher=teacher,
        total_reports=total_reports,
        performance_reports=performance_reports,
        evaluation_reports=evaluation_reports,
        at_risk_students=at_risk_students,
        recent_reports=recent_reports,
        students=students_list
    )


@app.route("/teacher/reports/generate", methods=["POST"])
def generate_teacher_report():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    report_type = request.form.get("report_type", "Performance").strip()
    valid_types = ["Performance", "At-Risk", "Evaluation", "Class Performance"]
    if report_type not in valid_types:
        report_type = "Performance"

    student_id_val = request.form.get("student_id", "all").strip()

    conn = get_db_connection()

    if student_id_val == "all" or not student_id_val:
        if report_type == "At-Risk":
            # Target at-risk students (average marks < 50)
            students_list = conn.execute("""
                SELECT DISTINCT s.id, s.name FROM students s
                JOIN academic_records a ON s.id = a.student_id
                GROUP BY s.id HAVING AVG(a.marks) < 50
            """).fetchall()
            if not students_list:
                students_list = conn.execute("SELECT id, name FROM students ORDER BY id").fetchall()
        else:
            students_list = conn.execute("SELECT id, name FROM students ORDER BY id").fetchall()
    else:
        try:
            s_id = int(student_id_val)
            students_list = conn.execute("SELECT id, name FROM students WHERE id = ?", (s_id,)).fetchall()
        except ValueError:
            students_list = conn.execute("SELECT id, name FROM students ORDER BY id").fetchall()

    if not students_list:
        conn.close()
        flash("No registered students available to generate reports.", "warning")
        return redirect(url_for("teacher_reports"))

    count = 0
    for s in students_list:
        conn.execute("""
            INSERT INTO reports (student_id, generated_by, report_type, generated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (s["id"], session["user_id"], report_type))
        count += 1

    conn.commit()
    conn.close()

    flash(f"Successfully generated {count} {report_type} report(s)!", "success")
    return redirect(url_for("teacher_reports"))


@app.route("/teacher/reports/delete/<int:report_id>", methods=["POST"])
def delete_teacher_report(report_id):
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()

    flash("Report deleted successfully.", "info")
    return redirect(url_for("teacher_reports"))


@app.route("/teacher/reports/download/<int:report_id>")
def download_teacher_report(report_id):
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    report = conn.execute("""
        SELECT r.*, s.name, s.email, s.department, s.semester, s.gender
        FROM reports r JOIN students s ON r.student_id = s.id
        WHERE r.id = ?
    """, (report_id,)).fetchone()

    if not report:
        conn.close()
        return "Report not found", 404

    academic_records = conn.execute("SELECT subject, marks FROM academic_records WHERE student_id = ? ORDER BY subject", (report["student_id"],)).fetchall()
    attendance_records = conn.execute("SELECT subject, percentage FROM attendance WHERE student_id = ? ORDER BY subject", (report["student_id"],)).fetchall()
    feedback = conn.execute("SELECT * FROM student_feedback WHERE student_id = ? ORDER BY id DESC LIMIT 1", (report["student_id"],)).fetchone()
    prediction = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (report["student_id"],)).fetchone()
    conn.close()

    pdf_buffer = generate_pdf_report(report, academic_records, attendance_records, feedback, prediction)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"StudentIQ_{report['name']}_Performance_Report.pdf",
        mimetype="application/pdf"
    )


@app.route("/teacher/reports/download/<int:report_id>/csv")
def download_teacher_report_csv(report_id):
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    report = conn.execute("""
        SELECT r.*, s.name, s.email, s.department, s.semester, s.gender
        FROM reports r JOIN students s ON r.student_id = s.id
        WHERE r.id = ?
    """, (report_id,)).fetchone()

    if not report:
        conn.close()
        return "Report not found", 404

    academic_records = conn.execute("SELECT subject, marks FROM academic_records WHERE student_id = ?", (report["student_id"],)).fetchall()
    attendance_records = conn.execute("SELECT subject, percentage FROM attendance WHERE student_id = ?", (report["student_id"],)).fetchall()
    prediction = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (report["student_id"],)).fetchone()
    conn.close()

    csv_data = generate_csv_report(report, academic_records, attendance_records, prediction)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=StudentIQ_{report['name']}_Report.csv"}
    )


@app.route("/teacher/reports/export/all-students.csv")
def export_all_students_csv():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    students_list = conn.execute("""
        SELECT
            s.id, s.name, s.email, s.department, s.semester, s.gender,
            ROUND(AVG(a.marks), 1) AS average_marks,
            ROUND(AVG(att.percentage), 1) AS average_attendance
        FROM students s
        LEFT JOIN academic_records a ON s.id = a.student_id
        LEFT JOIN attendance att ON s.id = att.student_id
        GROUP BY s.id
        ORDER BY s.id
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID", "Full Name", "Email", "Department", "Semester", "Gender", "Average Marks", "Average Attendance %", "Risk Status"])

    for s in students_list:
        avg_m = s["average_marks"] or 0.0
        risk = "At Risk" if avg_m < 50 else ("Average" if avg_m < 75 else "Good")
        writer.writerow([
            s["id"], s["name"], s["email"], s["department"], s["semester"],
            s["gender"], avg_m, s["average_attendance"] or 0.0, risk
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=StudentIQ_All_Students_Summary.csv"}
    )


@app.route("/teacher/settings")
def teacher_settings():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") == "student":
        return redirect(url_for("settings"))
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    teacher = conn.execute("SELECT * FROM teachers WHERE user_id = ? LIMIT 1", (session["user_id"],)).fetchone()
    if not teacher:
        conn.close()
        return "Teacher profile not found.", 404

    settings_row = conn.execute("SELECT * FROM teacher_settings WHERE teacher_id = ? LIMIT 1", (teacher["id"],)).fetchone()
    if not settings_row:
        conn.execute("""
            INSERT INTO teacher_settings (teacher_id, compact_view, student_overview, evaluation_alerts, performance_alerts, risk_alerts)
            VALUES (?, 1, 1, 1, 1, 1)
        """, (teacher["id"],))
        conn.commit()
        settings_row = conn.execute("SELECT * FROM teacher_settings WHERE teacher_id = ? LIMIT 1", (teacher["id"],)).fetchone()

    conn.close()

    return render_template(
        "Teacher/teacher_settings.html",
        teacher=teacher,
        settings=settings_row
    )


@app.route("/teacher/settings/update", methods=["POST"])
def update_teacher_settings():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    department = request.form.get("department", "").strip()

    if not name or not email:
        flash("Name and email are required.", "danger")
        return redirect(url_for("teacher_settings"))

    file = request.files.get("profile_pic")
    pic_rel_path = None
    if file and file.filename and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        unique_name = f"teacher_{session['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(save_path)
        pic_rel_path = f"uploads/profile_pics/{unique_name}"

    conn = get_db_connection()
    if pic_rel_path:
        conn.execute("UPDATE teachers SET name = ?, email = ?, department = ?, profile_pic = ? WHERE user_id = ?", (name, email, department, pic_rel_path, session["user_id"]))
        conn.execute("UPDATE users SET email = ?, profile_pic = ? WHERE id = ?", (email, pic_rel_path, session["user_id"]))
    else:
        conn.execute("UPDATE teachers SET name = ?, email = ?, department = ? WHERE user_id = ?", (name, email, department, session["user_id"]))
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Teacher profile updated successfully!", "success")
    return redirect(url_for("teacher_settings"))


@app.route("/teacher/settings/profile-pic", methods=["POST"])
def update_teacher_profile_pic():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    file = request.files.get("profile_pic")
    if not file or not file.filename:
        flash("Please select an image file to upload.", "warning")
        return redirect(url_for("teacher_settings"))

    if not allowed_file(file.filename):
        flash("Invalid image format. Allowed formats: PNG, JPG, JPEG, GIF, WEBP.", "danger")
        return redirect(url_for("teacher_settings"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    unique_name = f"teacher_{session['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(save_path)
    rel_path = f"uploads/profile_pics/{unique_name}"

    conn = get_db_connection()
    old_row = conn.execute("SELECT profile_pic FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()
    if old_row and old_row["profile_pic"]:
        old_path = os.path.join(app.root_path, "static", old_row["profile_pic"])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    conn.execute("UPDATE teachers SET profile_pic = ? WHERE user_id = ?", (rel_path, session["user_id"]))
    conn.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (rel_path, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Teacher profile picture updated successfully!", "success")
    return redirect(url_for("teacher_settings"))


@app.route("/teacher/settings/profile-pic/remove", methods=["POST"])
def remove_teacher_profile_pic():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    old_row = conn.execute("SELECT profile_pic FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()
    if old_row and old_row["profile_pic"]:
        old_path = os.path.join(app.root_path, "static", old_row["profile_pic"])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    conn.execute("UPDATE teachers SET profile_pic = NULL WHERE user_id = ?", (session["user_id"],))
    conn.execute("UPDATE users SET profile_pic = NULL WHERE id = ?", (session["user_id"],))
    conn.commit()
    conn.close()

    flash("Profile picture removed successfully.", "info")
    return redirect(url_for("teacher_settings"))


@app.route("/teacher/settings/preferences", methods=["POST"])
def update_teacher_preferences():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    compact_view = 1 if request.form.get("compact_view") else 0
    student_overview = 1 if request.form.get("student_overview") else 0
    evaluation_alerts = 1 if request.form.get("evaluation_alerts") else 0
    performance_alerts = 1 if request.form.get("performance_alerts") else 0
    risk_alerts = 1 if request.form.get("risk_alerts") else 0

    conn = get_db_connection()
    teacher = conn.execute("SELECT id FROM teachers WHERE user_id = ?", (session["user_id"],)).fetchone()
    if teacher:
        conn.execute("""
            UPDATE teacher_settings
            SET compact_view = ?, student_overview = ?, evaluation_alerts = ?, performance_alerts = ?, risk_alerts = ?
            WHERE teacher_id = ?
        """, (compact_view, student_overview, evaluation_alerts, performance_alerts, risk_alerts, teacher["id"]))
        conn.commit()
    conn.close()

    flash("Preferences updated successfully!", "success")
    return redirect(url_for("teacher_settings"))


@app.route("/teacher/settings/change-password", methods=["POST"])
def change_teacher_password():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login"))

    current_pwd = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm_pwd = request.form.get("confirm_password", "")

    if not current_pwd or not new_pwd:
        flash("All password fields are required.", "danger")
        return redirect(url_for("teacher_settings"))

    if new_pwd != confirm_pwd:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("teacher_settings"))

    conn = get_db_connection()
    user = conn.execute("SELECT password FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not user or user["password"] != current_pwd:
        conn.close()
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("teacher_settings"))

    conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_pwd, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Password changed successfully!", "success")
    return redirect(url_for("teacher_settings"))


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True, port=5000)