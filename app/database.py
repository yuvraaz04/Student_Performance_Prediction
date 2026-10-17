import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            profile_pic TEXT,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # 2. Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            profile_pic TEXT,
            department TEXT,
            semester INTEGER,
            gender TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 3. Teachers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            profile_pic TEXT,
            department TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 4. Academic records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS academic_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            marks REAL,
            semester INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # 5. Attendance
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT,
            total_classes INTEGER,
            attended_classes INTEGER,
            percentage REAL,
            updated_at DATETIME,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # 6. Teacher feedback
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            activity TEXT,
            knowledge TEXT,
            personality TEXT,
            suggestion TEXT,
            remarks TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    """)

    # 7. Predictions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            predicted_score REAL,
            performance_level TEXT,
            risk_level TEXT,
            prediction_date TEXT,
            attendance REAL,
            study_hours REAL,
            previous_marks REAL,
            assignment_score REAL,
            sleep_hours REAL,
            social_media_hours REAL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # 8. Reports
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            generated_by INTEGER,
            report_type TEXT,
            generated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # 9. Teacher preferences
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER UNIQUE NOT NULL,
            compact_view INTEGER DEFAULT 1,
            student_overview INTEGER DEFAULT 1,
            evaluation_alerts INTEGER DEFAULT 1,
            performance_alerts INTEGER DEFAULT 1,
            risk_alerts INTEGER DEFAULT 1,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    """)

    # 10. Student preferences
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER UNIQUE NOT NULL,
            email_notifications INTEGER DEFAULT 1,
            report_alerts INTEGER DEFAULT 1,
            prediction_alerts INTEGER DEFAULT 1,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # Auto-migrate columns if tables existed from an earlier schema
    def _add_col(table, col, col_type):
        cols = [c[1] for c in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

    for c in ["attendance", "study_hours", "previous_marks", "assignment_score", "sleep_hours", "social_media_hours"]:
        _add_col("predictions", c, "REAL")
    for c in ["attendance_rating", "discipline_rating"]:
        _add_col("student_feedback", c, "INTEGER")
    for c in ["risk_level", "recommendation"]:
        _add_col("student_feedback", c, "TEXT")
    for tbl in ["users", "students", "teachers"]:
        _add_col(tbl, "phone", "TEXT")
        _add_col(tbl, "profile_pic", "TEXT")
    _add_col("attendance", "updated_at", "DATETIME")

    conn.commit()
    conn.close()


def cleanup_test_students():
    """Remove accumulated dummy test students and test teachers from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Find test students to remove (do not delete seeded system accounts)
    test_students = cursor.execute("""
        SELECT id, user_id FROM students
        WHERE (name LIKE 'Test%'
           OR name LIKE 'Student\\_%' ESCAPE '\\'
           OR email LIKE '%@test.edu'
           OR email LIKE '%@studentiq.edu')
           AND email NOT IN ('student@gmail.com', 'teacher@gmail.com', 'aa@gmail.com', 'ys@gmail.com', 'kavita_risk@example.com', 'd@gmail.com')
    """).fetchall()

    test_student_ids = [s["id"] for s in test_students]
    test_user_ids = [s["user_id"] for s in test_students if s["user_id"] is not None]

    if test_student_ids:
        placeholders = ",".join("?" for _ in test_student_ids)
        cursor.execute(f"DELETE FROM academic_records WHERE student_id IN ({placeholders})", test_student_ids)
        cursor.execute(f"DELETE FROM attendance WHERE student_id IN ({placeholders})", test_student_ids)
        cursor.execute(f"DELETE FROM predictions WHERE student_id IN ({placeholders})", test_student_ids)
        cursor.execute(f"DELETE FROM reports WHERE student_id IN ({placeholders})", test_student_ids)
        cursor.execute(f"DELETE FROM student_feedback WHERE student_id IN ({placeholders})", test_student_ids)
        cursor.execute(f"DELETE FROM student_settings WHERE student_id IN ({placeholders})", test_student_ids)
        cursor.execute(f"DELETE FROM students WHERE id IN ({placeholders})", test_student_ids)

    if test_user_ids:
        placeholders_u = ",".join("?" for _ in test_user_ids)
        cursor.execute(f"DELETE FROM users WHERE id IN ({placeholders_u})", test_user_ids)

    # Also remove any dangling test teacher accounts
    test_teachers = cursor.execute("""
        SELECT id, user_id FROM teachers
        WHERE name LIKE 'Dr. Test%' OR email LIKE '%@test.edu'
    """).fetchall()
    if test_teachers:
        t_ids = [t["id"] for t in test_teachers]
        t_u_ids = [t["user_id"] for t in test_teachers if t["user_id"] is not None]
        cursor.execute(f"DELETE FROM teacher_settings WHERE teacher_id IN ({','.join('?' for _ in t_ids)})", t_ids)
        cursor.execute(f"DELETE FROM teachers WHERE id IN ({','.join('?' for _ in t_ids)})", t_ids)
        if t_u_ids:
            cursor.execute(f"DELETE FROM users WHERE id IN ({','.join('?' for _ in t_u_ids)})", t_u_ids)

    conn.commit()
    conn.close()


def seed_student_data(student_id, semester=1):
    """Seed initial academic records, attendance, and settings for a newly registered student."""
    conn = get_db_connection()
    cursor = conn.cursor()

    existing_records = cursor.execute(
        "SELECT COUNT(*) FROM academic_records WHERE student_id = ?", (student_id,)
    ).fetchone()[0]

    if existing_records == 0:
        subjects = [
            ("Python Programming", 82.0, 40, 37, 92.5),
            ("Database Management", 78.0, 40, 35, 87.5),
            ("Data Science", 85.0, 40, 36, 90.0),
            ("Big Data Analytics", 74.0, 40, 32, 80.0),
            ("Statistics", 79.0, 40, 34, 85.0),
        ]

        for subj, marks, total_c, att_c, pct in subjects:
            cursor.execute(
                """
                INSERT INTO academic_records (student_id, subject, marks, semester)
                VALUES (?, ?, ?, ?)
            """,
                (student_id, subj, marks, semester),
            )

            cursor.execute(
                """
                INSERT INTO attendance (student_id, subject, total_classes, attended_classes, percentage)
                VALUES (?, ?, ?, ?, ?)
            """,
                (student_id, subj, total_c, att_c, pct),
            )

        # Initial prediction
        cursor.execute(
            """
            INSERT INTO predictions
            (student_id, predicted_score, performance_level, risk_level, prediction_date, attendance, study_hours, previous_marks, assignment_score)
            VALUES (?, 80.0, 'Good Performance', 'Low Risk', datetime('now'), 87.0, 4.0, 79.6, 82.0)
        """,
            (student_id,),
        )

        # Initial report
        cursor.execute(
            """
            INSERT INTO reports (student_id, generated_by, report_type, generated_at)
            VALUES (?, 1, 'Performance', datetime('now'))
        """,
            (student_id,),
        )

        # Initial student settings
        cursor.execute(
            """
            INSERT OR IGNORE INTO student_settings (student_id, email_notifications, report_alerts, prediction_alerts)
            VALUES (?, 1, 1, 1)
        """,
            (student_id,),
        )

        conn.commit()

    conn.close()


def seed_default_accounts():
    """Ensure baseline student and teacher accounts exist with phone numbers."""
    create_tables()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Default Student
    student_user = cursor.execute(
        "SELECT id FROM users WHERE email = ?", ("student@gmail.com",)
    ).fetchone()
    if not student_user:
        cursor.execute(
            """
            INSERT INTO users (email, phone, password, role)
            VALUES (?, ?, ?, ?)
        """,
            ("student@gmail.com", "+91 91234 56789", "1234", "student"),
        )
        student_user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO students (user_id, name, email, phone, department, semester, gender)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (student_user_id, "Shreya Solanki", "student@gmail.com", "+91 91234 56789", "MSc IT", 3, "Female"),
        )
        student_id = cursor.lastrowid
        conn.commit()
        seed_student_data(student_id, semester=3)
    else:
        cursor.execute("UPDATE users SET phone = COALESCE(phone, '+91 91234 56789') WHERE id = ?", (student_user["id"],))
        cursor.execute("UPDATE students SET phone = COALESCE(phone, '+91 91234 56789') WHERE user_id = ?", (student_user["id"],))
        conn.commit()
        student = cursor.execute(
            "SELECT id FROM students WHERE user_id = ?", (student_user["id"],)
        ).fetchone()
        if student:
            seed_student_data(student["id"], semester=3)

    # 2. Default Teacher
    teacher_user = cursor.execute(
        "SELECT id FROM users WHERE email = ?", ("teacher@gmail.com",)
    ).fetchone()
    if not teacher_user:
        cursor.execute(
            """
            INSERT INTO users (email, phone, password, role)
            VALUES (?, ?, ?, ?)
        """,
            ("teacher@gmail.com", "+91 98765 43210", "12345", "teacher"),
        )
        teacher_user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO teachers (user_id, name, email, phone, department)
            VALUES (?, ?, ?, ?, ?)
        """,
            (teacher_user_id, "Prof. Jonathan Davis", "teacher@gmail.com", "+91 98765 43210", "Computer Science & AI"),
        )
        teacher_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO teacher_settings (teacher_id, compact_view, student_overview, evaluation_alerts, performance_alerts, risk_alerts)
            VALUES (?, 1, 1, 1, 1, 1)
        """,
            (teacher_id,),
        )
        conn.commit()
    else:
        cursor.execute("UPDATE users SET phone = COALESCE(phone, '+91 98765 43210') WHERE id = ?", (teacher_user["id"],))
        cursor.execute("UPDATE teachers SET phone = COALESCE(phone, '+91 98765 43210') WHERE user_id = ?", (teacher_user["id"],))
        conn.commit()

    conn.close()


if __name__ == "__main__":
    create_tables()
    cleanup_test_students()
    seed_default_accounts()
    print("Database tables initialized, test students cleaned, and verified successfully!")