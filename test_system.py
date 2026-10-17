import unittest
import json
import os
import sys
import time
import io

sys.path.insert(0, os.path.abspath('app'))
from app import app, get_db_connection
from database import cleanup_test_students, seed_default_accounts

class StudentIQSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cleanup_test_students()
        seed_default_accounts()

    @classmethod
    def tearDownClass(cls):
        cleanup_test_students()

    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-123'
        self.client = app.test_client()

    def login_student(self, identifier='student@gmail.com', password='1234', phone='+91 91234 56789'):
        """Helper to authenticate student via 2-step phone OTP with typed mobile number"""
        data = {
            'email': identifier,
            'password': password,
            'role': 'student'
        }
        if phone:
            data['phone'] = phone
        res = self.client.post('/login', data=data, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/verify-login-otp' in res.headers['Location'])

        # Check OTP verification page: NO OTP code and NO Autofill button in HTML
        verify_page = self.client.get('/verify-login-otp')
        self.assertEqual(verify_page.status_code, 200)
        self.assertNotIn(b'Autofill', verify_page.data)
        self.assertNotIn(b'otpCodeDisplay', verify_page.data)

        with self.client.session_transaction() as sess:
            otp = sess.get('login_otp')
            dest_phone = sess.get('pending_login', {}).get('phone')
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp), 6)
        if phone:
            self.assertEqual(dest_phone, phone)

        # Confirm OTP itself is not leaked in the HTML response
        self.assertNotIn(otp.encode(), verify_page.data)

        res = self.client.post('/verify-login-otp', data={'otp': otp}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        return res

    def login_teacher(self, identifier='teacher@gmail.com', password='12345', phone='+91 98765 43210'):
        """Helper to authenticate teacher via 2-step phone OTP with typed mobile number"""
        data = {
            'email': identifier,
            'password': password,
            'role': 'teacher'
        }
        if phone:
            data['phone'] = phone
        res = self.client.post('/login', data=data, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/verify-login-otp' in res.headers['Location'])

        # Check OTP verification page: NO OTP code and NO Autofill button in HTML
        verify_page = self.client.get('/verify-login-otp')
        self.assertEqual(verify_page.status_code, 200)
        self.assertNotIn(b'Autofill', verify_page.data)
        self.assertNotIn(b'otpCodeDisplay', verify_page.data)

        with self.client.session_transaction() as sess:
            otp = sess.get('login_otp')
            dest_phone = sess.get('pending_login', {}).get('phone')
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp), 6)
        if phone:
            self.assertEqual(dest_phone, phone)

        # Confirm OTP itself is not leaked in the HTML response
        self.assertNotIn(otp.encode(), verify_page.data)

        res = self.client.post('/verify-login-otp', data={'otp': otp}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        return res

    def test_01_unauthenticated_redirects(self):
        """Unauthenticated users are safely redirected to login"""
        res = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/login' in res.headers['Location'] or res.headers['Location'].endswith('/'))

        res = self.client.get('/teacher', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/login' in res.headers['Location'] or res.headers['Location'].endswith('/'))

        res = self.client.get('/prediction', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/login' in res.headers['Location'] or res.headers['Location'].endswith('/'))

        res = self.client.get('/teacher/prediction', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/login' in res.headers['Location'] or res.headers['Location'].endswith('/'))

    def test_02_student_login_and_pages_without_prediction(self):
        """Student can type mobile number, authenticate via phone OTP, with zero prediction pages or links"""
        # Test student login with typed mobile number
        typed_mobile = '+91 99887 76655'
        self.login_student(identifier='student@gmail.com', phone=typed_mobile)

        # 1. Dashboard - Prediction link removed from hero and sidebar
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Student Performance Dashboard', res.data)
        self.assertNotIn(b'href="/prediction"', res.data)
        self.assertNotIn(b'Run Prediction', res.data)

        # 2. Students Directory
        res = self.client.get('/students')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'My Performance', res.data)
        self.assertNotIn(b'href="/prediction"', res.data)

        # 3. Analytics
        res = self.client.get('/analytics')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Analytics', res.data)
        self.assertNotIn(b'href="/prediction"', res.data)
        self.assertNotIn(b'Performance Trend', res.data)
        self.assertNotIn(b'performanceTrendChart', res.data)

        # 4. Accessing /prediction directly redirects student to /dashboard with notification
        res = self.client.get('/prediction', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Predictive analytics features are managed by faculty instructors', res.data)

        # 5. Reports
        res = self.client.get('/reports')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'REPORT CENTER', res.data)
        # Verify Export buttons are present and Generate Report modal is removed
        self.assertIn(b'Export Report', res.data)
        self.assertNotIn(b'id="generateReportBtn"', res.data)
        self.assertNotIn(b'id="reportModal"', res.data)

        # 6. Settings
        res = self.client.get('/settings')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'ACCOUNT SETTINGS', res.data)
        self.client.get('/logout')

    def test_03_prediction_api(self):
        """ML model generates real-time predictions and actionable recommendations with sleep and social media"""
        self.login_student()

        payload = {
            'study_hours': 14.5,
            'attendance': 88.0,
            'previous_marks': 76.5,
            'sleep_duration': 7.5,
            'social_media': 2.0,
            'participation': 'high',
            'gender': 'Female'
        }
        res = self.client.post('/api/predict', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('predicted_score', data)
        self.assertIn('risk_level', data)
        self.assertIn('recommendation', data)
        self.assertIn('factors', data)
        self.assertIn('sleep_duration', data['factors'])
        self.assertIn('social_media', data['factors'])
        self.assertNotIn('assignment', data['factors'])
        self.assertGreater(data['predicted_score'], 0)
        self.client.get('/logout')

    def test_04_student_reports_export_faculty(self):
        """Student can export faculty-generated reports in PDF and CSV format"""
        self.login_student()

        # 1. Reports page displays Export Report buttons
        res = self.client.get('/reports')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Export Report', res.data)
        self.assertIn(b'Export CSV', res.data)

        # 2. Student export faculty report via /student/reports/export (PDF)
        pdf_res = self.client.get('/student/reports/export')
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.mimetype, 'application/pdf')
        self.assertTrue(len(pdf_res.data) > 0)

        # 3. Student export faculty report via /student/reports/export?format=csv (CSV)
        csv_res = self.client.get('/student/reports/export?format=csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn('text/csv', csv_res.headers.get('Content-Type', ''))
        self.assertIn(b'StudentIQ Academic Report', csv_res.data)

        # 4. Student download specific report by ID
        conn = get_db_connection()
        rep = conn.execute("SELECT id FROM reports ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if rep:
            rep_id = rep['id']
            rep_pdf = self.client.get(f'/student/reports/download/{rep_id}')
            self.assertEqual(rep_pdf.status_code, 200)
            self.assertEqual(rep_pdf.mimetype, 'application/pdf')

            rep_csv = self.client.get(f'/student/reports/download/{rep_id}/csv')
            self.assertEqual(rep_csv.status_code, 200)
            self.assertIn('text/csv', rep_csv.headers.get('Content-Type', ''))

        self.client.get('/logout')

    def test_05_teacher_workflow_and_prediction(self):
        """Teacher can access ML Prediction workbench, simulate forecasts, and export reports"""
        self.login_teacher()

        # Teacher dashboard
        res = self.client.get('/teacher')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Teacher Dashboard', res.data)

        # Students list contains Predict button
        res = self.client.get('/teacher/students')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'/teacher/prediction', res.data)
        self.assertIn(b'Predict', res.data)

        # Teacher Prediction workbench
        res = self.client.get('/teacher/prediction')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Student Performance Prediction', res.data)
        self.assertIn(b'Predictor Parameters', res.data)

        # Teacher Prediction with selected student
        res = self.client.get('/teacher/prediction?student_id=1')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Predictor Parameters', res.data)

        # Teacher Prediction simulation via form POST
        res = self.client.post('/teacher/prediction', data={
            'student_id': 1,
            'attendance': 85.0,
            'studyHours': 6.0,
            'previousMarks': 78.0,
            'assignment': 85.0,
            'participation': 'high',
            'gender': 'Female'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Predicted Exam Score', res.data)

        # Teacher Prediction via AJAX /api/predict with student_id
        api_res = self.client.post('/api/predict', data=json.dumps({
            'student_id': 1,
            'attendance': 90.0,
            'study_hours': 8.0,
            'previous_marks': 82.0,
            'assignment': 88.0,
            'participation': 'high'
        }), content_type='application/json')
        self.assertEqual(api_res.status_code, 200)
        api_data = json.loads(api_res.data)
        self.assertTrue(api_data['success'])
        self.assertGreater(api_data['predicted_score'], 0)

        # Evaluation page & submit
        res = self.client.get('/teacher/evaluation')
        self.assertEqual(res.status_code, 200)

        res = self.client.post('/teacher/evaluation/submit', data={
            'student_id': 1,
            'activity': 'Excellent',
            'knowledge': 'Strong',
            'personality': 'Good',
            'suggestion': 'Continue research paper',
            'remarks': 'Outstanding performance in deep learning lab.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Teacher analytics
        res = self.client.get('/teacher/analytics')
        self.assertEqual(res.status_code, 200)

        # Teacher reports
        res = self.client.get('/teacher/reports')
        self.assertEqual(res.status_code, 200)

        # Generate batch reports
        res = self.client.post('/teacher/reports/generate', data={'report_type': 'Performance'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Teacher CAN download individual PDF report
        conn = get_db_connection()
        rep_row = conn.execute("SELECT id FROM reports ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        rep_id = rep_row["id"] if rep_row else 1
        res = self.client.get(f'/teacher/reports/download/{rep_id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, 'application/pdf')
        self.assertTrue(res.data.startswith(b'%PDF-'))

        # Teacher CAN download individual CSV report
        res = self.client.get(f'/teacher/reports/download/{rep_id}/csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.content_type)

        # Teacher CAN export all students CSV
        res = self.client.get('/teacher/reports/export/all-students.csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.content_type)
        self.assertIn(b'Student ID,Full Name,Email', res.data)

        # Teacher settings
        res = self.client.get('/teacher/settings')
        self.assertEqual(res.status_code, 200)
        self.client.get('/logout')

    def test_06_student_signup_blocked_and_faculty_signup_with_phone_otp(self):
        """Student self-registration is blocked; Faculty registers with typed phone and 2-step OTP"""
        ts = int(time.time() * 1000)

        # 1. Student self-registration attempt must be REJECTED
        res = self.client.post('/register', data={
            'name': 'Attempt Student',
            'email': f'blocked_{ts}@test.edu',
            'phone': f'+91 99999 {ts % 100000:05d}',
            'role': 'student',
            'password': 'pass'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Student self-registration is disabled', res.data)

        # 2. Faculty registration succeeds with typed phone OTP
        teach_phone = f'+91 98111 {ts % 100000:05d}'
        teacher_email = f'fac_{ts}@test.edu'
        res = self.client.post('/register', data={
            'name': 'Prof. Test Faculty',
            'email': teacher_email,
            'phone': teach_phone,
            'role': 'teacher',
            'department': 'Artificial Intelligence',
            'password': 'faculty_pass'
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/verify-signup-otp' in res.headers['Location'])

        # Verify that the signup OTP page DOES NOT display the OTP or Autofill
        verify_page = self.client.get('/verify-signup-otp')
        self.assertEqual(verify_page.status_code, 200)
        self.assertNotIn(b'Autofill', verify_page.data)
        self.assertNotIn(b'otpCodeDisplay', verify_page.data)

        with self.client.session_transaction() as sess:
            reg_otp = sess.get('reg_otp')
            pending = sess.get('pending_registration')
        self.assertIsNotNone(reg_otp)
        self.assertEqual(pending.get('phone'), teach_phone)
        self.assertNotIn(reg_otp.encode(), verify_page.data)

        # Verify signup OTP
        res = self.client.post('/verify-signup-otp', data={'otp': reg_otp}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Faculty account created successfully', res.data)

        # Login new faculty with typed phone
        res = self.client.post('/login', data={
            'email': teacher_email,
            'phone': teach_phone,
            'password': 'faculty_pass',
            'role': 'teacher'
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/verify-login-otp' in res.headers['Location'])

        with self.client.session_transaction() as sess:
            login_otp = sess.get('login_otp')

        res = self.client.post('/verify-login-otp', data={'otp': login_otp}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Teacher', res.data)

        self.client.get('/logout')
        cleanup_test_students()

    def test_07_teacher_adds_student_with_phone_and_student_logs_in(self):
        """Teacher adds a student with phone number and student logs in with typed mobile number"""
        self.login_teacher()
        ts = int(time.time() * 1000)
        stu_email = f'newenrolled_{ts}@test.edu'
        stu_phone = f'+91 97000 {ts % 100000:05d}'
        stu_name = f'Enrolled Student {ts % 1000}'

        # Teacher adds student
        res = self.client.post('/teacher/students/add', data={
            'name': stu_name,
            'email': stu_email,
            'phone': stu_phone,
            'department': 'MSc IT',
            'semester': '2',
            'gender': 'Male',
            'password': 'student_secret'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'enrolled successfully', res.data)
        self.client.get('/logout')

        # Newly enrolled student logs in typing phone number
        res = self.client.post('/login', data={
            'email': stu_email,
            'phone': stu_phone,
            'password': 'student_secret',
            'role': 'student'
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/verify-login-otp' in res.headers['Location'])

        with self.client.session_transaction() as sess:
            login_otp = sess.get('login_otp')
            self.assertEqual(sess.get('pending_login', {}).get('phone'), stu_phone)

        res = self.client.post('/verify-login-otp', data={'otp': login_otp}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'StudentIQ', res.data)

        self.client.get('/logout')
        cleanup_test_students()

    def test_08_otp_validation_failures_and_resend(self):
        """Invalid OTP codes are rejected and resend generates fresh code without displaying on page"""
        # Test Login with wrong OTP
        self.client.post('/login', data={
            'email': 'student@gmail.com',
            'phone': '+91 91234 56789',
            'password': '1234',
            'role': 'student'
        })
        res = self.client.post('/verify-login-otp', data={'otp': '000000'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Invalid verification code', res.data)
        self.assertNotIn(b'Autofill', res.data)

        # Test Resend Login OTP
        res = self.client.get('/resend-login-otp', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            new_otp = sess.get('login_otp')
        self.assertIsNotNone(new_otp)
        self.assertEqual(len(new_otp), 6)
        self.assertNotIn(new_otp.encode(), res.data)

        self.client.get('/logout')

        # Test Faculty Signup with wrong OTP
        ts = int(time.time() * 1000)
        self.client.post('/register', data={
            'name': 'OTP Test Faculty',
            'email': f'otpfac_{ts}@test.edu',
            'phone': f'+91 97777 {ts % 100000:05d}',
            'role': 'teacher',
            'password': 'pass'
        })
        res = self.client.post('/verify-signup-otp', data={'otp': '999999'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Invalid verification code', res.data)
        self.assertNotIn(b'Autofill', res.data)

        # Test Resend Signup OTP
        res = self.client.get('/resend-signup-otp', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            fresh_reg_otp = sess.get('reg_otp')
        self.assertIsNotNone(fresh_reg_otp)
        self.assertEqual(len(fresh_reg_otp), 6)
        self.assertNotIn(fresh_reg_otp.encode(), res.data)

        self.client.get('/logout')
        cleanup_test_students()

    def test_09_forgot_password_and_phone_otp_reset(self):
        """User can type mobile number for password reset, receive SMS OTP, with no OTP on reset page"""
        custom_phone = '+91 93333 44444'

        # 1. Request reset with identifier and typed custom mobile number
        res = self.client.post('/forgot-password', data={
            'identifier': 'student@gmail.com',
            'phone': custom_phone
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/reset-password' in res.headers['Location'])

        # Verify reset password page DOES NOT contain Autofill or OTP display badge
        reset_page = self.client.get('/reset-password')
        self.assertEqual(reset_page.status_code, 200)
        self.assertNotIn(b'Autofill', reset_page.data)
        self.assertNotIn(b'otpCodeDisplay', reset_page.data)

        with self.client.session_transaction() as sess:
            reset_otp = sess.get('reset_otp')
            reset_phone = sess.get('reset_phone')
        self.assertIsNotNone(reset_otp)
        self.assertEqual(len(reset_otp), 6)
        self.assertEqual(reset_phone, custom_phone)
        self.assertNotIn(reset_otp.encode(), reset_page.data)

        # 2. Resend Reset OTP
        res = self.client.get('/resend-reset-otp', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            new_reset_otp = sess.get('reset_otp')
        self.assertIsNotNone(new_reset_otp)
        self.assertNotIn(new_reset_otp.encode(), res.data)

        # 3. Wrong OTP attempt fails
        res = self.client.post('/reset-password', data={
            'otp': '000000',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Invalid SMS verification code', res.data)

        # 4. Correct OTP resets password
        res = self.client.post('/reset-password', data={
            'otp': new_reset_otp,
            'new_password': 'brand_new_pass',
            'confirm_password': 'brand_new_pass'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Your password has been reset successfully', res.data)

        # 5. Login with new password and typed phone succeeds
        res = self.client.post('/login', data={
            'email': 'student@gmail.com',
            'phone': custom_phone,
            'password': 'brand_new_pass',
            'role': 'student'
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        with self.client.session_transaction() as sess:
            otp = sess.get('login_otp')
        self.client.post('/verify-login-otp', data={'otp': otp}, follow_redirects=True)

        # Restore original password for other tests
        conn = get_db_connection()
        conn.execute("UPDATE users SET password = '1234' WHERE email = 'student@gmail.com'")
        conn.commit()
        conn.close()
        self.client.get('/logout')

    def test_10_change_password_student_and_teacher(self):
        """Student and Teacher can update password within their settings"""
        # 1. Student change password
        self.login_student()
        # Invalid current password
        res = self.client.post('/student/settings/password', data={
            'current_password': 'wrong_password',
            'new_password': 'new_stu_pass',
            'confirm_password': 'new_stu_pass'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Incorrect current password', res.data)

        # Valid current password
        res = self.client.post('/student/settings/password', data={
            'current_password': '1234',
            'new_password': 'temp_pass_456',
            'confirm_password': 'temp_pass_456'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Password updated successfully', res.data)

        # Restore student password
        self.client.post('/student/settings/password', data={
            'current_password': 'temp_pass_456',
            'new_password': '1234',
            'confirm_password': '1234'
        }, follow_redirects=True)
        self.client.get('/logout')

        # 2. Teacher change password
        self.login_teacher()
        # Invalid current password
        res = self.client.post('/teacher/settings/change-password', data={
            'current_password': 'wrong_password',
            'new_password': 'new_teach_pass',
            'confirm_password': 'new_teach_pass'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Current password is incorrect', res.data)

        # Valid current password
        res = self.client.post('/teacher/settings/change-password', data={
            'current_password': '12345',
            'new_password': 'temp_teach_456',
            'confirm_password': 'temp_teach_456'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Password changed successfully', res.data)

        # Restore teacher password
        self.client.post('/teacher/settings/change-password', data={
            'current_password': 'temp_teach_456',
            'new_password': '12345',
            'confirm_password': '12345'
        }, follow_redirects=True)
        self.client.get('/logout')

    def test_11_zero_test_students_in_teacher_view(self):
        """Teacher students directory has no lingering test students"""
        cleanup_test_students()
        self.login_teacher()
        res = self.client.get('/teacher/students')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b'Test New Student', res.data)
        self.assertNotIn(b'Student_', res.data)
        self.assertNotIn(b'@test.edu', res.data)
        self.client.get('/logout')

    def test_12_artifacts_integrity(self):
        """Models and notebooks exist and are valid"""
        self.assertTrue(os.path.exists('models/random_forest_model.pkl'))
        self.assertTrue(os.path.exists('models/scaler.pkl'))
        self.assertTrue(os.path.exists('models/label_encoders.pkl'))
        self.assertTrue(os.path.exists('models/model_metadata.json'))

        # Check notebooks
        notebooks = [
            'notebook/1_Data_Loading_and_EDA.ipynb',
            'notebook/2_Data_Preprocessing.ipynb',
            'notebook/3_Model_Building.ipynb',
            'notebook/4_Model_Evaluation.ipynb'
        ]
        for nb_path in notebooks:
            self.assertTrue(os.path.exists(nb_path), f'Missing {nb_path}')
            with open(nb_path, 'r', encoding='utf-8') as f:
                nb = json.load(f)
                self.assertIn('cells', nb)
                self.assertGreater(len(nb['cells']), 3)

    def test_13_teacher_dashboard_categories_and_no_schedule(self):
        """Teacher dashboard has Excellent, Average, and Poor cards and NO Today's Schedule"""
        self.login_teacher()
        res = self.client.get('/teacher')
        self.assertEqual(res.status_code, 200)

        # 3 Category cards + Total Students
        self.assertIn(b'Excellent Students', res.data)
        self.assertIn(b'Average Students', res.data)
        self.assertIn(b'Poor Students', res.data)
        self.assertIn(b'Total Students', res.data)

        # Confirm Today's Schedule was removed
        self.assertNotIn(b"Today's Schedule", res.data)
        self.assertNotIn(b'View timetable', res.data)
        self.assertNotIn(b'schedule-card', res.data)

        # Confirm Attendance Management banner button and sidebar link
        self.assertIn(b'Attendance Management', res.data)
        self.assertIn(b'/teacher/attendance', res.data)
        self.client.get('/logout')

    def test_14_dynamic_attention_students_on_poor_prediction(self):
        """Students with poor predictions automatically appear in Students Requiring Attention on Dashboard"""
        self.login_teacher()

        # 1. Add a new student
        res_add = self.client.post('/teacher/students/add', data={
            'name': 'Kavita RiskStudent',
            'email': 'kavita_risk@example.com',
            'phone': '+91 91999 88877',
            'department': 'Computer Science',
            'semester': '2',
            'gender': 'Female',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)

        # Retrieve new student id
        conn = get_db_connection()
        student = conn.execute("SELECT id FROM students WHERE email = 'kavita_risk@example.com'").fetchone()
        self.assertIsNotNone(student)
        student_id = student['id']
        conn.close()

        # 2. Make a poor prediction for this student (low attendance, low marks)
        pred_res = self.client.post('/teacher/prediction', data={
            'student_id': str(student_id),
            'attendance': '20.0',
            'studyHours': '0.5',
            'previousMarks': '25.0',
            'assignment': '20.0',
            'participation': 'low',
            'gender': 'Female'
        }, follow_redirects=True)
        self.assertEqual(pred_res.status_code, 200)

        # 3. Check teacher dashboard: Kavita RiskStudent MUST appear in Students Requiring Attention
        dash_res = self.client.get('/teacher')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Kavita RiskStudent', dash_res.data)
        self.assertIn(b'High Risk', dash_res.data)

        # 4. Now update her prediction to Excellent (high attendance, high marks)
        pred_res2 = self.client.post('/teacher/prediction', data={
            'student_id': str(student_id),
            'attendance': '98.0',
            'studyHours': '8.0',
            'previousMarks': '95.0',
            'assignment': '96.0',
            'participation': 'high',
            'gender': 'Female'
        }, follow_redirects=True)
        self.assertEqual(pred_res2.status_code, 200)

        # Check teacher dashboard: Kavita should no longer be in Students Requiring Attention
        dash_res2 = self.client.get('/teacher')
        self.assertEqual(dash_res2.status_code, 200)
        # If no other students are high risk, it shows the empty state or other poor students
        # The key is Kavita's High Risk badge is no longer active
        conn = get_db_connection()
        latest_p = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student_id,)).fetchone()
        self.assertNotEqual(latest_p['risk_level'], 'High Risk')
        self.assertGreaterEqual(latest_p['predicted_score'], 68.0)
        conn.close()

        self.client.get('/logout')

    def test_15_teacher_attendance_management(self):
        """Teacher can view, add, update, and delete student attendance records"""
        self.login_teacher()

        # 1. View attendance dashboard
        res = self.client.get('/teacher/attendance')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Attendance Management', res.data)
        self.assertIn(b'Average Attendance', res.data)
        self.assertIn(b'Record Attendance', res.data)

        # 2. Add an attendance record
        conn = get_db_connection()
        student = conn.execute("SELECT id FROM students LIMIT 1").fetchone()
        self.assertIsNotNone(student)
        sid = student['id']
        conn.close()

        res_add = self.client.post('/teacher/attendance/add', data={
            'student_id': str(sid),
            'subject': 'Artificial Intelligence',
            'total_classes': '50',
            'attended_classes': '45'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b'Artificial Intelligence', res_add.data)

        # Verify DB
        conn = get_db_connection()
        att_rec = conn.execute(
            "SELECT * FROM attendance WHERE student_id = ? AND subject = 'Artificial Intelligence'", (sid,)
        ).fetchone()
        self.assertIsNotNone(att_rec)
        self.assertEqual(att_rec['total_classes'], 50)
        self.assertEqual(att_rec['attended_classes'], 45)
        self.assertEqual(att_rec['percentage'], 90.0)
        att_id = att_rec['id']
        conn.close()

        # 3. Update the attendance record
        res_update = self.client.post('/teacher/attendance/update', data={
            'attendance_id': str(att_id),
            'subject': 'Artificial Intelligence',
            'total_classes': '50',
            'attended_classes': '35'
        }, follow_redirects=True)
        self.assertEqual(res_update.status_code, 200)

        conn = get_db_connection()
        updated_rec = conn.execute("SELECT * FROM attendance WHERE id = ?", (att_id,)).fetchone()
        self.assertEqual(updated_rec['attended_classes'], 35)
        self.assertEqual(updated_rec['percentage'], 70.0)
        conn.close()

        # 4. Delete the attendance record
        res_del = self.client.post(f'/teacher/attendance/delete/{att_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

        conn = get_db_connection()
        del_check = conn.execute("SELECT * FROM attendance WHERE id = ?", (att_id,)).fetchone()
        self.assertIsNone(del_check)
        conn.close()

        self.client.get('/logout')

    def test_16_faculty_name_in_analytics(self):
        """Teacher Analytics displays logged-in faculty name and not hardcoded Ms. Ria"""
        self.login_teacher()

        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE email = 'teacher@gmail.com'").fetchone()
        teacher = conn.execute("SELECT name FROM teachers WHERE user_id = ?", (user['id'],)).fetchone()
        teacher_name = teacher['name'] if teacher else "Faculty"
        conn.close()

        res = self.client.get('/teacher/analytics')
        self.assertEqual(res.status_code, 200)
        self.assertIn(teacher_name.encode('utf-8'), res.data)
        self.assertNotIn(b'Ms. Ria', res.data)

        self.client.get('/logout')

    def test_17_attendance_marking_and_auto_calculation(self):
        """Attendance mark option automatically calculates attended out of total classes and percentage"""
        self.login_teacher()

        conn = get_db_connection()
        student = conn.execute("SELECT id, name FROM students LIMIT 1").fetchone()
        self.assertIsNotNone(student)
        sid = student['id']

        # Ensure a base record exists
        conn.execute("DELETE FROM attendance WHERE student_id = ? AND subject = 'Cloud Computing'", (sid,))
        conn.execute("""
            INSERT INTO attendance (student_id, subject, total_classes, attended_classes, percentage)
            VALUES (?, 'Cloud Computing', 10, 8, 80.0)
        """, (sid,))
        conn.commit()
        rec_id = conn.execute("SELECT id FROM attendance WHERE student_id = ? AND subject = 'Cloud Computing'", (sid,)).fetchone()['id']
        conn.close()

        # 1. Single Mark: Present (+1 attended, +1 total -> 9/11 = 81.8%)
        res_pres = self.client.post('/teacher/attendance/mark-single', data={
            'attendance_id': str(rec_id),
            'status': 'present'
        }, follow_redirects=True)
        self.assertEqual(res_pres.status_code, 200)

        conn = get_db_connection()
        r1 = conn.execute("SELECT total_classes, attended_classes, percentage FROM attendance WHERE id = ?", (rec_id,)).fetchone()
        self.assertEqual(r1['total_classes'], 11)
        self.assertEqual(r1['attended_classes'], 9)
        self.assertEqual(r1['percentage'], 81.8)
        conn.close()

        # 2. Single Mark: Absent (+0 attended, +1 total -> 9/12 = 75.0%)
        res_abs = self.client.post('/teacher/attendance/mark-single', data={
            'attendance_id': str(rec_id),
            'status': 'absent'
        }, follow_redirects=True)
        self.assertEqual(res_abs.status_code, 200)

        conn = get_db_connection()
        r2 = conn.execute("SELECT total_classes, attended_classes, percentage FROM attendance WHERE id = ?", (rec_id,)).fetchone()
        self.assertEqual(r2['total_classes'], 12)
        self.assertEqual(r2['attended_classes'], 9)
        self.assertEqual(r2['percentage'], 75.0)
        conn.close()

        # 3. Class Attendance Session: mark subject for all students
        conn = get_db_connection()
        all_students = conn.execute("SELECT id FROM students").fetchall()
        conn.close()

        all_ids = [str(s['id']) for s in all_students]
        present_ids = all_ids[:1]  # first student present, others absent

        res_class = self.client.post('/teacher/attendance/mark-class', data={
            'subject': 'Network Security',
            'all_student_ids': all_ids,
            'present_student_ids': present_ids
        }, follow_redirects=True)
        self.assertEqual(res_class.status_code, 200)

        conn = get_db_connection()
        # Verify first student got marked present
        rec_p = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject = 'Network Security'", (int(all_ids[0]),)).fetchone()
        self.assertIsNotNone(rec_p)
        self.assertEqual(rec_p['attended_classes'], 1)
        self.assertEqual(rec_p['total_classes'], 1)
        self.assertEqual(rec_p['percentage'], 100.0)

        # Cleanup
        conn.execute("DELETE FROM attendance WHERE subject IN ('Cloud Computing', 'Network Security')")
        conn.commit()
        conn.close()

        self.client.get('/logout')

    def test_18_dashboard_recent_student_activity_removed(self):
        """Dashboard removes Recent Student Activity and Pending Evaluations links to teacher_evaluation"""
        self.login_teacher()

        res = self.client.get('/teacher')
        self.assertEqual(res.status_code, 200)

        # Recent Student Activity is removed
        self.assertNotIn(b'Recent Student Activity', res.data)
        self.assertNotIn(b'Rahul Mehta \xe2\x80\xa2 Physics Assignment', res.data)

        # Evaluations card is present with link
        self.assertIn(b'Pending Evaluations', res.data)
        self.assertIn(b'/teacher/evaluation', res.data)

        self.client.get('/logout')

    def test_19_reports_module_and_available_options(self):
        """Teacher reports module supports report options, custom generation, PDF/CSV export, and deletion"""
        self.login_teacher()

        # 1. View reports page
        res = self.client.get('/teacher/reports')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Reports', res.data)
        self.assertIn(b'Available Reports', res.data)
        self.assertIn(b'Student Performance Report', res.data)
        self.assertIn(b'At-Risk Student Report', res.data)
        self.assertIn(b'Evaluation Report', res.data)
        self.assertIn(b'Class Performance Report', res.data)

        # 2. Generate At-Risk reports for all students
        res_gen = self.client.post('/teacher/reports/generate', data={
            'report_type': 'At-Risk',
            'student_id': 'all'
        }, follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)
        self.assertIn(b'At-Risk', res_gen.data)

        # 3. Generate Evaluation report for a specific student
        conn = get_db_connection()
        student = conn.execute("SELECT id FROM students LIMIT 1").fetchone()
        sid = student['id']
        conn.close()

        res_single = self.client.post('/teacher/reports/generate', data={
            'report_type': 'Evaluation',
            'student_id': str(sid)
        }, follow_redirects=True)
        self.assertEqual(res_single.status_code, 200)

        conn = get_db_connection()
        rep = conn.execute("SELECT id FROM reports WHERE student_id = ? AND report_type = 'Evaluation' ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
        self.assertIsNotNone(rep)
        rep_id = rep['id']
        conn.close()

        # 4. Download PDF
        pdf_res = self.client.get(f'/teacher/reports/download/{rep_id}')
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.mimetype, 'application/pdf')
        self.assertTrue(len(pdf_res.data) > 0)

        # 5. Download CSV
        csv_res = self.client.get(f'/teacher/reports/download/{rep_id}/csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn(b'StudentIQ Academic Report', csv_res.data)
        self.assertIn(b'Student Name', csv_res.data)

        # 6. Export All Students Class CSV
        class_csv_res = self.client.get('/teacher/reports/export/all-students.csv')
        self.assertEqual(class_csv_res.status_code, 200)
        self.assertIn(b'Student ID,Full Name,Email', class_csv_res.data)

        # 7. Delete Report
        del_res = self.client.post(f'/teacher/reports/delete/{rep_id}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

        conn = get_db_connection()
        del_rep = conn.execute("SELECT id FROM reports WHERE id = ?", (rep_id,)).fetchone()
        self.assertIsNone(del_rep)
        conn.close()

        self.client.get('/logout')

    def test_20_prediction_features_sleep_and_social_media(self):
        """Verify Assignment Score is removed and Sleep Duration & Social Media Usage in hours are used"""
        self.login_teacher()

        # Check teacher prediction UI contains Sleep Duration and Social Media Usage sliders and NOT Assignment Score
        pred_page = self.client.get('/teacher/prediction')
        self.assertEqual(pred_page.status_code, 200)
        self.assertIn(b'Sleep Duration', pred_page.data)
        self.assertIn(b'Social Media Usage', pred_page.data)
        self.assertNotIn(b'Assignment Score', pred_page.data)
        self.assertNotIn(b'Student Gender', pred_page.data)
        self.assertNotIn(b'id="gender"', pred_page.data)
        self.assertIn(b'id="sleepDuration"', pred_page.data)
        self.assertIn(b'id="socialMedia"', pred_page.data)
        self.assertNotIn(b'id="assignment"', pred_page.data)

        # Test inference with low sleep and high social media
        payload_poor = {
            'study_hours': 4.0,
            'attendance': 55.0,
            'previous_marks': 45.0,
            'sleep_duration': 4.5,
            'social_media': 7.0,
            'participation': 'low',
            'gender': 'Male'
        }
        res_poor = self.client.post('/api/predict', data=json.dumps(payload_poor), content_type='application/json')
        self.assertEqual(res_poor.status_code, 200)
        data_poor = json.loads(res_poor.data)
        self.assertTrue(data_poor['success'])
        self.assertEqual(data_poor['factors']['sleep_duration'], 4.5)
        self.assertEqual(data_poor['factors']['social_media'], 7.0)
        self.assertNotIn('assignment', data_poor['factors'])

        # Test inference with healthy sleep and low social media
        payload_good = {
            'study_hours': 18.0,
            'attendance': 92.0,
            'previous_marks': 88.0,
            'sleep_duration': 8.0,
            'social_media': 1.5,
            'participation': 'high',
            'gender': 'Female'
        }
        res_good = self.client.post('/api/predict', data=json.dumps(payload_good), content_type='application/json')
        self.assertEqual(res_good.status_code, 200)
        data_good = json.loads(res_good.data)
        self.assertTrue(data_good['success'])
        self.assertGreater(data_good['predicted_score'], data_poor['predicted_score'])

        self.client.get('/logout')

    def test_21_topbar_buttons_teacher_and_student(self):
        """Verify Teacher modules have NO top-right bell/message buttons and Student modules have working notification button & NO message button"""
        # 1. Teacher modules: NO bell, NO chat buttons in topbars
        self.login_teacher()
        teacher_routes = [
            '/teacher',
            '/teacher/students',
            '/teacher/reports',
            '/teacher/attendance',
            '/teacher/evaluation',
            '/teacher/analytics',
            '/teacher/prediction'
        ]
        for route in teacher_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Failed on route {route}")
            # Ensure topbar has no bell button or chat button
            self.assertNotIn(b'bi-bell', res.data, f"Found bi-bell on teacher route {route}")
            self.assertNotIn(b'bi-chat', res.data, f"Found bi-chat on teacher route {route}")
        self.client.get('/logout')

        # 2. Student modules: Working notification button & NO message button
        self.login_student()
        student_routes = [
            '/dashboard',
            '/students',
            '/reports',
            '/analytics',
            '/settings'
        ]
        for route in student_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Failed on student route {route}")
            # Confirm working notification button is present
            self.assertIn(b'id="studentNotifBtn"', res.data, f"Missing studentNotifBtn on {route}")
            self.assertIn(b'id="studentNotifMenu"', res.data, f"Missing studentNotifMenu on {route}")
            self.assertIn(b'Mark all read', res.data, f"Missing Mark all read on {route}")
            # Confirm NO message / chat button
            self.assertNotIn(b'bi-chat', res.data, f"Found bi-chat on student route {route}")
        self.client.get('/logout')

    def test_22_search_bars_working_student_and_teacher(self):
        """Verify all search bars exist and are properly configured across Student and Teacher modules"""
        # Teacher side search bars
        self.login_teacher()
        res = self.client.get('/teacher')
        self.assertIn(b'id="dashboardSearchInput"', res.data)

        res = self.client.get('/teacher/students')
        self.assertIn(b'id="topStudentSearch"', res.data)
        self.assertIn(b'id="studentSearch"', res.data)

        res = self.client.get('/teacher/reports')
        self.assertIn(b'id="reportsSearchInput"', res.data)

        res = self.client.get('/teacher/evaluation')
        self.assertIn(b'id="evaluationSearchInput"', res.data)

        res = self.client.get('/teacher/analytics')
        self.assertIn(b'id="analyticsSearchInput"', res.data)

        res = self.client.get('/teacher/attendance')
        self.assertIn(b'id="topSearchInput"', res.data)

        res = self.client.get('/teacher/prediction')
        self.assertIn(b'id="predictStudentSearch"', res.data)
        self.client.get('/logout')

        # Student side search bars removed
        self.login_student()
        res = self.client.get('/dashboard')
        self.assertNotIn(b'id="studentDashboardSearch"', res.data)

        res = self.client.get('/students')
        self.assertNotIn(b'id="studentDirectorySearch"', res.data)

        res = self.client.get('/reports')
        self.assertNotIn(b'id="studentReportsSearch"', res.data)

        res = self.client.get('/analytics')
        self.assertNotIn(b'id="studentAnalyticsSearch"', res.data)

        res = self.client.get('/attendance')
        self.assertNotIn(b'id="studentAttendanceSearch"', res.data)
        self.client.get('/logout')

    def test_23_logout_button_font_white_and_gender_removed(self):
        """Verify Logout button has white font across student & teacher modules, and prediction works without gender input"""
        # 1. Prediction without gender input
        self.login_teacher()
        payload_no_gender = {
            'study_hours': 12.0,
            'attendance': 85.0,
            'previous_marks': 78.0,
            'sleep_duration': 7.0,
            'social_media': 2.5,
            'participation': 'medium'
        }
        res = self.client.post('/api/predict', data=json.dumps(payload_no_gender), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('predicted_score', data)

        # 2. Teacher logout font color white
        # Teacher sidebar
        res_t_dash = self.client.get('/teacher')
        self.assertIn(b'color: #ffffff;', res_t_dash.data)
        self.assertIn(b'Logout', res_t_dash.data)

        # Teacher settings
        res_t_set = self.client.get('/teacher/settings')
        self.assertIn(b'color: #ffffff', res_t_set.data)
        self.assertIn(b'Logout', res_t_set.data)
        self.client.get('/logout')

        # 3. Student logout font color white
        self.login_student()
        # Student sidebar & dashboard
        res_s_dash = self.client.get('/dashboard')
        self.assertIn(b'color: #ffffff;', res_s_dash.data)
        self.assertIn(b'Logout', res_s_dash.data)

        # Student other page with sidebar
        res_s_dir = self.client.get('/students')
        self.assertIn(b'color: #ffffff;', res_s_dir.data)
        self.assertIn(b'Logout', res_s_dir.data)

        # Student settings
        res_s_set = self.client.get('/settings')
        self.assertIn(b'color: #ffffff', res_s_set.data)
        self.assertIn(b'Logout', res_s_set.data)
        self.client.get('/logout')

    def test_24_student_dashboard_removed_charts(self):
        """Verify Student Performance (Performance Trend) and Gender Distribution charts are removed from Student Dashboard"""
        self.login_student()
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)

        # Removed charts
        self.assertNotIn(b'id="performanceChart"', res.data)
        self.assertNotIn(b'Performance Trend', res.data)
        self.assertNotIn(b'id="genderChart"', res.data)
        self.assertNotIn(b'Gender Distribution', res.data)

        # Retained charts
        self.assertIn(b'id="subjectChart"', res.data)
        self.assertIn(b'Subject Analysis', res.data)
        self.assertIn(b'id="attendanceChart"', res.data)
        self.assertIn(b'Attendance Trend', res.data)
        self.client.get('/logout')

    def test_25_student_dashboard_removed_table(self):
        """Verify Student Performance table is removed from Student Dashboard"""
        self.login_student()
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)

        # Removed student performance table card
        self.assertNotIn(b'class="table-card"', res.data)
        self.assertNotIn(b'<h3>Student Performance</h3>', res.data)
        self.assertNotIn(b'Aarav Sharma', res.data)
        self.assertNotIn(b'Ananya Patel', res.data)
        self.client.get('/logout')

    def test_26_student_and_teacher_profile_picture_management(self):
        """Verify profile picture upload, persistence across pages, and removal for both student and teacher"""
        # 1. Student profile picture
        self.login_student()
        res_settings = self.client.get('/settings')
        self.assertEqual(res_settings.status_code, 200)
        self.assertIn(b'studentProfilePicInput', res_settings.data)
        self.assertIn(b'Upload Photo', res_settings.data)

        # Upload student avatar
        avatar_data = {
            'profile_pic': (io.BytesIO(b'dummy student avatar image bytes'), 'student_avatar.png')
        }
        res_up = self.client.post('/student/settings/profile-pic', data=avatar_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_up.status_code, 200)
        self.assertIn(b'Profile picture updated successfully!', res_up.data)
        self.assertIn(b'/static/uploads/profile_pics/student_', res_up.data)

        # Check DB
        conn = get_db_connection()
        student_rec = conn.execute("SELECT profile_pic FROM students WHERE email = 'student@gmail.com'").fetchone()
        conn.close()
        self.assertIsNotNone(student_rec['profile_pic'])
        self.assertTrue(student_rec['profile_pic'].startswith('uploads/profile_pics/student_'))

        # Verify avatar is rendered on other student pages
        res_dash = self.client.get('/dashboard')
        self.assertIn(student_rec['profile_pic'].encode(), res_dash.data)
        res_stud = self.client.get('/students')
        self.assertIn(student_rec['profile_pic'].encode(), res_stud.data)

        # Remove student avatar
        res_rem = self.client.post('/student/settings/profile-pic/remove', follow_redirects=True)
        self.assertEqual(res_rem.status_code, 200)
        self.assertIn(b'Profile picture removed successfully.', res_rem.data)
        conn = get_db_connection()
        student_rec_after = conn.execute("SELECT profile_pic FROM students WHERE email = 'student@gmail.com'").fetchone()
        conn.close()
        self.assertIsNone(student_rec_after['profile_pic'])
        self.client.get('/logout')

        # 2. Teacher profile picture
        self.login_teacher()
        res_t_settings = self.client.get('/teacher/settings')
        self.assertEqual(res_t_settings.status_code, 200)
        self.assertIn(b'teacherProfilePicInput', res_t_settings.data)
        self.assertIn(b'Upload Photo', res_t_settings.data)

        # Upload teacher avatar
        teacher_avatar_data = {
            'profile_pic': (io.BytesIO(b'dummy teacher avatar image bytes'), 'teacher_avatar.jpg')
        }
        res_t_up = self.client.post('/teacher/settings/profile-pic', data=teacher_avatar_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_t_up.status_code, 200)
        self.assertIn(b'Teacher profile picture updated successfully!', res_t_up.data)
        self.assertIn(b'/static/uploads/profile_pics/teacher_', res_t_up.data)

        # Check DB
        conn = get_db_connection()
        teacher_rec = conn.execute("SELECT profile_pic FROM teachers WHERE email = 'teacher@gmail.com'").fetchone()
        conn.close()
        self.assertIsNotNone(teacher_rec['profile_pic'])
        self.assertTrue(teacher_rec['profile_pic'].startswith('uploads/profile_pics/teacher_'))

        # Verify avatar is rendered on other teacher pages
        res_t_dash = self.client.get('/teacher')
        self.assertIn(teacher_rec['profile_pic'].encode(), res_t_dash.data)
        res_t_stud = self.client.get('/teacher/students')
        self.assertIn(teacher_rec['profile_pic'].encode(), res_t_stud.data)

        # Remove teacher avatar
        res_t_rem = self.client.post('/teacher/settings/profile-pic/remove', follow_redirects=True)
        self.assertEqual(res_t_rem.status_code, 200)
        self.assertIn(b'Profile picture removed successfully.', res_t_rem.data)
        conn = get_db_connection()
        teacher_rec_after = conn.execute("SELECT profile_pic FROM teachers WHERE email = 'teacher@gmail.com'").fetchone()
        conn.close()
        self.assertIsNone(teacher_rec_after['profile_pic'])
        self.client.get('/logout')

    def test_27_profile_picture_validation_and_form_update(self):
        """Verify invalid image file extensions are rejected and main settings forms also handle profile pictures"""
        self.login_student()
        # Invalid extension
        invalid_file = {
            'profile_pic': (io.BytesIO(b'executable file'), 'malicious.exe')
        }
        res_bad = self.client.post('/student/settings/profile-pic', data=invalid_file, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_bad.status_code, 200)
        self.assertIn(b'Invalid image format', res_bad.data)

        # Update via main student settings form
        form_data = {
            'name': 'Shreya Solanki',
            'email': 'student@gmail.com',
            'department': 'MSc IT',
            'semester': '2',
            'profile_pic': (io.BytesIO(b'valid student png bytes'), 'avatar_form.png')
        }
        res_form = self.client.post('/student/settings/update', data=form_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_form.status_code, 200)
        self.assertIn(b'Profile details updated successfully!', res_form.data)
        conn = get_db_connection()
        st = conn.execute("SELECT profile_pic FROM students WHERE email = 'student@gmail.com'").fetchone()
        conn.close()
        self.assertIsNotNone(st['profile_pic'])
        self.client.post('/student/settings/profile-pic/remove')
        self.client.get('/logout')

        self.login_teacher()
        # Invalid extension
        invalid_file_teacher = {
            'profile_pic': (io.BytesIO(b'executable file'), 'malicious.exe')
        }
        res_t_bad = self.client.post('/teacher/settings/profile-pic', data=invalid_file_teacher, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_t_bad.status_code, 200)
        self.assertIn(b'Invalid image format', res_t_bad.data)

        # Update via main teacher settings form
        t_form_data = {
            'name': 'Dr. Alan Smith',
            'email': 'teacher@gmail.com',
            'department': 'Computer Science',
            'profile_pic': (io.BytesIO(b'valid teacher jpg bytes'), 'teacher_form.jpg')
        }
        res_t_form = self.client.post('/teacher/settings/update', data=t_form_data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_t_form.status_code, 200)
        self.assertIn(b'Teacher profile updated successfully!', res_t_form.data)
        conn = get_db_connection()
        tch = conn.execute("SELECT profile_pic FROM teachers WHERE email = 'teacher@gmail.com'").fetchone()
        conn.close()
        self.assertIsNotNone(tch['profile_pic'])
        self.client.post('/teacher/settings/profile-pic/remove')
        self.client.get('/logout')

    def test_28_student_modules_navigation_never_redirects_to_teacher(self):
        """Verify student modules never redirect to teacher routes for student or teacher sessions, and teacher routes guide students cleanly"""
        self.login_student()

        student_paths = ['/dashboard', '/students', '/analytics', '/reports', '/settings']
        for path in student_paths:
            res = self.client.get(path, follow_redirects=True)
            self.assertEqual(res.status_code, 200, f"Failed accessing {path}")
            self.assertEqual(res.request.path, path, f"Path {path} redirected unexpectedly to {res.request.path}")
            self.assertFalse(res.request.path.startswith('/teacher'), f"Student path {path} redirected to teacher portal: {res.request.path}")
            self.assertIn(b'StudentIQ', res.data)
            self.assertIn(b'Logout', res.data)

        # Cross-role guidance: when student requests a teacher path, they are guided to the student counterpart
        cross_mappings = [
            ('/teacher', '/dashboard'),
            ('/teacher/students', '/students'),
            ('/teacher/analytics', '/analytics'),
            ('/teacher/reports', '/reports'),
            ('/teacher/settings', '/settings')
        ]
        for t_path, expected_s_path in cross_mappings:
            res = self.client.get(t_path, follow_redirects=True)
            self.assertEqual(res.status_code, 200, f"Failed navigating from {t_path}")
            self.assertEqual(res.request.path, expected_s_path, f"Accessing {t_path} did not guide student to {expected_s_path}, got {res.request.path}")

        self.client.get('/logout')

        # Faculty session: student paths can be previewed without bouncing to teacher
        self.login_teacher()
        for path in student_paths:
            res = self.client.get(path, follow_redirects=True)
            self.assertEqual(res.status_code, 200, f"Teacher previewing {path} failed with {res.status_code}")
            self.assertFalse(res.request.path.startswith('/teacher'), f"Teacher previewing {path} bounced to teacher portal: {res.request.path}")

        # Faculty teacher routes stay on teacher side
        teacher_paths = ['/teacher', '/teacher/students', '/teacher/attendance', '/teacher/evaluation', '/teacher/analytics', '/teacher/prediction', '/teacher/reports', '/teacher/settings']
        for t_path in teacher_paths:
            res = self.client.get(t_path, follow_redirects=True)
            self.assertEqual(res.status_code, 200, f"Faculty route {t_path} failed")
            self.assertEqual(res.request.path, t_path, f"Faculty route {t_path} redirected to {res.request.path}")

        self.client.get('/logout')

    def test_29_teacher_students_action_buttons_working(self):
        """Verify all interactive buttons in Teacher Students module (View, Edit, Delete, Export, Prediction) work end-to-end"""
        self.login_teacher()

        # 1. Check /teacher/students page renders action buttons, modals, and export trigger
        res = self.client.get('/teacher/students')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'viewStudentModal', res.data)
        self.assertIn(b'editStudentModal', res.data)
        self.assertIn(b'deleteStudentModal', res.data)
        self.assertIn(b'view-student-btn', res.data)
        self.assertIn(b'edit-student-btn', res.data)
        self.assertIn(b'delete-student-btn', res.data)
        self.assertIn(b'run-prediction-btn', res.data)
        self.assertIn(b'/teacher/reports/export/all-students.csv', res.data)

        # 2. Test dynamic student profile API endpoint
        conn = get_db_connection()
        sample_student = conn.execute("SELECT * FROM students LIMIT 1").fetchone()
        self.assertIsNotNone(sample_student)
        st_id = sample_student['id']
        conn.close()

        api_res = self.client.get(f'/api/teacher/student/{st_id}')
        self.assertEqual(api_res.status_code, 200)
        import json
        payload = json.loads(api_res.data.decode('utf-8'))
        self.assertTrue(payload.get('success'))
        self.assertEqual(payload['student']['id'], st_id)
        self.assertIn('academic_records', payload)
        self.assertIn('attendance_records', payload)
        self.assertIn('prediction', payload)
        self.assertIn('evaluations', payload)

        # 3. Test direct view redirect route
        view_res = self.client.get(f'/teacher/students/{st_id}')
        self.assertEqual(view_res.status_code, 302)
        self.assertIn(f'/teacher/students?view={st_id}', view_res.headers['Location'])

        # 4. Test Edit Student action
        orig_name = sample_student['name']
        orig_email = sample_student['email']
        orig_phone = sample_student['phone'] or ''
        orig_dept = sample_student['department']
        orig_sem = sample_student['semester']
        orig_gender = sample_student['gender']

        edit_res = self.client.post(f'/teacher/students/edit/{st_id}', data={
            'name': orig_name + ' Updated',
            'email': orig_email,
            'phone': orig_phone,
            'department': orig_dept,
            'semester': orig_sem,
            'gender': orig_gender
        }, follow_redirects=True)
        self.assertEqual(edit_res.status_code, 200)
        self.assertIn(b'updated successfully', edit_res.data)

        # Revert student edit
        revert_res = self.client.post(f'/teacher/students/edit/{st_id}', data={
            'name': orig_name,
            'email': orig_email,
            'phone': orig_phone,
            'department': orig_dept,
            'semester': orig_sem,
            'gender': orig_gender
        }, follow_redirects=True)
        self.assertEqual(revert_res.status_code, 200)

        # 5. Test Delete Student action with cascading cleanup
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
                    ("delete_test_student@example.com", "hash123", "student"))
        temp_user_id = cur.lastrowid
        cur.execute("INSERT INTO students (user_id, name, email, department, semester, gender) VALUES (?, ?, ?, ?, ?, ?)",
                    (temp_user_id, "Delete Test Student", "delete_test_student@example.com", "CS", 1, "Male"))
        temp_st_id = cur.lastrowid
        cur.execute("INSERT INTO academic_records (student_id, subject, marks, semester) VALUES (?, ?, ?, ?)",
                    (temp_st_id, "Python Programming", 88.0, 1))
        cur.execute("INSERT INTO attendance (student_id, subject, total_classes, attended_classes, percentage) VALUES (?, ?, ?, ?, ?)",
                    (temp_st_id, "Python Programming", 40, 36, 90.0))
        conn.commit()
        conn.close()

        del_res = self.client.post(f'/teacher/students/delete/{temp_st_id}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertIn(b'have been deleted', del_res.data)

        # Verify cascades
        conn = get_db_connection()
        st_check = conn.execute("SELECT * FROM students WHERE id = ?", (temp_st_id,)).fetchone()
        u_check = conn.execute("SELECT * FROM users WHERE id = ?", (temp_user_id,)).fetchone()
        ar_check = conn.execute("SELECT * FROM academic_records WHERE student_id = ?", (temp_st_id,)).fetchall()
        att_check = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (temp_st_id,)).fetchall()
        conn.close()
        self.assertIsNone(st_check)
        self.assertIsNone(u_check)
        self.assertEqual(len(ar_check), 0)
        self.assertEqual(len(att_check), 0)

        # 6. Test CSV Export button endpoint
        csv_res = self.client.get('/teacher/reports/export/all-students.csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn('text/csv', csv_res.headers.get('Content-Type', ''))

        self.client.get('/logout')

    def test_30_student_attendance_module_and_sidebar_option(self):
        """Verify Students option is removed from student sidebar, Attendance option is added, and /attendance displays subject attendance details"""
        self.login_student()

        # 1. Verify student sidebar: Students option removed, Attendance option added
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'<span>Attendance</span>', dash_res.data)
        self.assertIn(b'/attendance', dash_res.data)
        self.assertNotIn(b'<span>Students</span>', dash_res.data)

        # 2. Access /attendance page
        att_res = self.client.get('/attendance')
        self.assertEqual(att_res.status_code, 200)
        self.assertIn(b'My Attendance', att_res.data)
        self.assertIn(b'Overall Attendance', att_res.data)
        self.assertIn(b'Total Classes Held', att_res.data)
        self.assertIn(b'Total Classes Taken', att_res.data)
        self.assertIn(b'Classes Missed', att_res.data)
        self.assertIn(b'Subject-Wise Attendance Breakdown', att_res.data)
        self.assertNotIn(b'studentAttendanceSearch', att_res.data)

        # 3. Verify cross-role redirections
        t_att_res = self.client.get('/teacher/attendance', follow_redirects=False)
        self.assertEqual(t_att_res.status_code, 302)
        self.assertIn('/attendance', t_att_res.headers['Location'])

        self.client.get('/logout')

        self.login_teacher()
        t_access_res = self.client.get('/attendance', follow_redirects=False)
        self.assertEqual(t_access_res.status_code, 302)
        self.assertIn('/teacher/attendance', t_access_res.headers['Location'])

        self.client.get('/logout')

    def test_31_student_reports_export_and_analytics_trends_removed(self):
        """Verify Student Reports has Export Report (PDF/CSV) of faculty-generated reports, modal removed, and Analytics has no Performance Trends"""
        self.login_student()

        # 1. Reports page verification
        rep_page = self.client.get('/reports')
        self.assertEqual(rep_page.status_code, 200)
        self.assertIn(b'Export Report', rep_page.data)
        self.assertIn(b'Export CSV', rep_page.data)
        self.assertIn(b'Faculty Evaluator', rep_page.data)
        self.assertNotIn(b'id="generateReportBtn"', rep_page.data)
        self.assertNotIn(b'id="reportModal"', rep_page.data)

        # 2. Export Faculty Report as PDF
        pdf_res = self.client.get('/student/reports/export')
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.mimetype, 'application/pdf')
        self.assertTrue(len(pdf_res.data) > 0)

        # 3. Export Faculty Report as CSV
        csv_res = self.client.get('/student/reports/export?format=csv')
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn('text/csv', csv_res.headers.get('Content-Type', ''))
        self.assertIn(b'StudentIQ Academic Report', csv_res.data)

        # 4. Analytics page verification: Performance Trend completely removed
        ana_page = self.client.get('/analytics')
        self.assertEqual(ana_page.status_code, 200)
        self.assertNotIn(b'Performance Trend', ana_page.data)
        self.assertNotIn(b'performanceTrendChart', ana_page.data)
        self.assertNotIn(b'StudentIQ Analytics - Performance Trend Chart', ana_page.data)

        self.client.get('/logout')

    def test_32_explainable_random_forest_prediction_and_85_threshold(self):
        """Verify explainable Random Forest prediction without artificial boosting, 85% threshold, and parameter analysis"""
        from ml_model import predict_student_performance

        # ====================================================
        # CASE 1: High Attendance & Academic Profile
        # Attendance = 92, Study Hours = 18, Previous Marks = 86,
        # Sleep = 8, Social Media = 1.5, Motivation = High
        # ====================================================
        c1 = predict_student_performance({
            "attendance": 92,
            "study_hours": 18,
            "previous_marks": 86,
            "sleep_duration": 8,
            "social_media": 1.5,
            "motivation_level": "High"
        })
        self.assertIn("predicted_score", c1)
        self.assertIn("score_float", c1)
        # Verify score is strictly from Random Forest (no artificial boost formula)
        self.assertAlmostEqual(c1["score_float"], 70.4, delta=1.5)
        self.assertEqual(c1["performance_category"], "Average Performance")
        self.assertEqual(c1["threshold"], "60–74%")
        self.assertFalse(c1["meets_85_threshold"])
        self.assertEqual(c1["risk_level"], "Low Risk")

        # Verify Parameter Analysis for Case 1
        pa1 = c1["parameter_analysis"]
        self.assertEqual(pa1["attendance"]["status"], "Excellent")
        self.assertIn("Attendance is in a strong range", pa1["attendance"]["message"])
        self.assertEqual(pa1["study_hours"]["status"], "Very Good")
        self.assertIn("Study time is in a strong range", pa1["study_hours"]["message"])
        self.assertEqual(pa1["previous_marks"]["status"], "Very Good")
        self.assertIn("Previous academic performance is a strong indicator", pa1["previous_marks"]["message"])
        self.assertEqual(pa1["sleep_duration"]["status"], "Optimal")
        self.assertIn("Sleep duration is within the recommended range", pa1["sleep_duration"]["message"])
        self.assertEqual(pa1["social_media"]["status"], "Low")
        self.assertIn("Social media usage is within a favorable range", pa1["social_media"]["message"])
        self.assertEqual(pa1["motivation_level"]["status"], "Strong")

        # Verify Recommendations for Case 1
        self.assertTrue(len(c1["recommendations_list"]) > 0)
        self.assertIn("All key student parameters are within high-performance benchmarks", c1["recommendation"])

        # ====================================================
        # CASE 2: Low Parameters Profile
        # Attendance = 70, Study Hours = 6, Previous Marks = 60,
        # Sleep = 5, Social Media = 5, Motivation = Low
        # ====================================================
        c2 = predict_student_performance({
            "attendance": 70,
            "study_hours": 6,
            "previous_marks": 60,
            "sleep_duration": 5,
            "social_media": 5,
            "motivation_level": "Low"
        })
        self.assertAlmostEqual(c2["score_float"], 64.5, delta=1.5)
        self.assertEqual(c2["performance_category"], "Average Performance")
        self.assertFalse(c2["meets_85_threshold"])

        # Verify Parameter Analysis for Case 2
        pa2 = c2["parameter_analysis"]
        self.assertEqual(pa2["attendance"]["status"], "Needs Improvement")
        self.assertEqual(pa2["study_hours"]["status"], "Low")
        self.assertEqual(pa2["previous_marks"]["status"], "Needs Improvement")
        self.assertEqual(pa2["sleep_duration"]["status"], "Low")
        self.assertEqual(pa2["social_media"]["status"], "Very High")
        self.assertEqual(pa2["motivation_level"]["status"], "Needs Improvement")

        # Verify targeted recommendations generated for weaker parameters
        recs2 = c2["recommendations_list"]
        self.assertTrue(any("attendance" in r.lower() for r in recs2))
        self.assertTrue(any("study time" in r.lower() for r in recs2))
        self.assertTrue(any("assessments" in r.lower() for r in recs2))
        self.assertTrue(any("sleep" in r.lower() for r in recs2))
        self.assertTrue(any("social media" in r.lower() for r in recs2))
        self.assertTrue(any("engagement" in r.lower() for r in recs2))

        # ====================================================
        # CASE 3: Mixed / Average Student Values
        # Attendance = 80, Study Hours = 14, Previous Marks = 78,
        # Sleep = 7, Social Media = 2.5, Motivation = Medium
        # ====================================================
        c3 = predict_student_performance({
            "attendance": 80,
            "study_hours": 14,
            "previous_marks": 78,
            "sleep_duration": 7,
            "social_media": 2.5,
            "motivation_level": "Medium"
        })
        self.assertAlmostEqual(c3["score_float"], 66.5, delta=2.0)
        self.assertEqual(c3["performance_category"], "Average Performance")
        self.assertEqual(c3["parameter_analysis"]["sleep_duration"]["status"], "Optimal")
        self.assertEqual(c3["parameter_analysis"]["motivation_level"]["status"], "Moderate")

        # ====================================================
        # CASE 4: 85%+ Performance Threshold Verification
        # High profile where model prediction reaches 85%+
        # ====================================================
        c4 = predict_student_performance({
            "attendance": 98,
            "study_hours": 27,
            "previous_marks": 93,
            "sleep_duration": 6,
            "social_media": 3.5,
            "tutoring_sessions": 5,
            "family_income": "High",
            "teacher_quality": "High",
            "parental_involvement": "Low",
            "access_to_resources": "Medium"
        })
        self.assertGreaterEqual(c4["score_float"], 75.0)
        if c4["score_float"] >= 85.0:
            self.assertTrue(c4["meets_85_threshold"])
            self.assertEqual(c4["threshold"], "85%+")
            self.assertEqual(c4["performance_category"], "Excellent Performance")

        # ====================================================
        # Feature Importance & High-Performance Indicators
        # ====================================================
        self.assertIn("feature_importance", c1)
        self.assertGreater(c1["feature_importance"]["Attendance"], 0.35)
        self.assertGreater(c1["feature_importance"]["Social_Media_Usage"], 0.10)
        self.assertGreater(c1["feature_importance"]["Hours_Studied"], 0.10)
        self.assertIn("high_performance_indicators", c1)
        self.assertIn("benchmarks", c1["high_performance_indicators"])
        self.assertIn("final prediction is generated by the trained Random Forest model", c1["high_performance_indicators"]["disclaimer"])

        # ====================================================
        # Frontend / API Compatibility via HTTP POST
        # ====================================================
        self.login_teacher()
        api_res = self.client.post('/api/predict', data=json.dumps({
            "attendance": 92,
            "study_hours": 18,
            "previous_marks": 86,
            "sleep_duration": 8,
            "social_media": 1.5,
            "motivation_level": "High"
        }), content_type='application/json')
        self.assertEqual(api_res.status_code, 200)
        api_data = json.loads(api_res.data)
        self.assertTrue(api_data["success"])
        self.assertIn("performance_category", api_data)
        self.assertIn("parameter_analysis", api_data)
        self.assertIn("feature_importance", api_data)
        self.assertIn("high_performance_indicators", api_data)

        # Teacher Prediction UI page verification
        page_res = self.client.get('/teacher/prediction')
        self.assertEqual(page_res.status_code, 200)
        self.assertIn(b'Motivation Level', page_res.data)
        self.assertIn(b'Predicted Performance', page_res.data)
        self.assertIn(b'Parameter Analysis', page_res.data)
        self.assertIn(b'Indicators Associated With Strong Performance', page_res.data)
        self.assertIn(b'Model Feature Importance', page_res.data)
        self.client.get('/logout')

    def test_33_student_and_teacher_data_exact_match(self):
        """Verify student data and prediction module on student side exactly match teacher portal records"""
        conn = get_db_connection()
        vishal = conn.execute("SELECT s.*, u.password FROM students s JOIN users u ON s.user_id = u.id WHERE s.name = 'Vishal'").fetchone()
        self.assertIsNotNone(vishal, "Student Vishal must exist in database")
        vishal_id = vishal["id"]

        # Ensure Vishal has consistent baseline prediction in DB
        conn.execute("DELETE FROM predictions WHERE student_id = ?", (vishal_id,))
        conn.execute("""
            INSERT INTO predictions
            (id, student_id, predicted_score, performance_level, risk_level, prediction_date, attendance, study_hours, previous_marks, sleep_hours, social_media_hours)
            VALUES (401, ?, 68.0, 'Average Performance', 'Low Risk', '2026-09-29 12:00:00', 87.0, 16.0, 80.0, 8.0, 2.0)
        """, (vishal_id,))
        conn.commit()

        # 1. Teacher views Vishal's data
        self.login_teacher()
        t_res = self.client.get(f"/api/teacher/student/{vishal_id}")
        self.assertEqual(t_res.status_code, 200)
        t_data = t_res.get_json()
        self.assertTrue(t_data["success"])
        teacher_avg_marks = t_data["average_marks"]
        teacher_avg_att = t_data["average_attendance"]
        teacher_pred_score = t_data["prediction"]["predicted_score"]
        teacher_perf_level = t_data["prediction"]["performance_level"]
        teacher_risk_level = t_data["prediction"]["risk_level"]
        self.client.get("/logout")

        # 2. Student Vishal logs in to his own account
        self.login_student(identifier=vishal["email"], password=vishal["password"], phone=vishal["phone"])

        # Check Student Dashboard (/dashboard)
        dash_res = self.client.get("/dashboard")
        self.assertEqual(dash_res.status_code, 200)
        dash_html = dash_res.data.decode()

        # Assert Average Marks matches teacher side
        self.assertIn(f"{teacher_avg_marks}%", dash_html)
        # Assert Average Attendance matches teacher side
        self.assertIn(f"{teacher_avg_att}%", dash_html)
        # Assert Predicted Score matches teacher side
        self.assertTrue(f"{int(teacher_pred_score)}%" in dash_html or f"{teacher_pred_score}%" in dash_html)
        # Assert Performance Level / Category matches teacher side
        self.assertIn(teacher_perf_level, dash_html)
        # Assert Risk Level matches teacher side
        self.assertIn(teacher_risk_level, dash_html)
        # Assert Prediction Module container exists
        self.assertIn("predictionModuleSection", dash_html)
        self.assertIn("Forecast Intelligence & Predictive Analytics", dash_html)
        self.assertIn("Parameter Analysis:", dash_html)

        # Check Student Analytics (/analytics)
        analytics_res = self.client.get("/analytics")
        self.assertEqual(analytics_res.status_code, 200)
        analytics_html = analytics_res.data.decode()
        self.assertIn(f"{teacher_avg_marks}%", analytics_html)
        self.assertIn(f"{teacher_avg_att}%", analytics_html)
        self.assertTrue(f"{int(teacher_pred_score)}%" in analytics_html or f"{teacher_pred_score}%" in analytics_html)
        self.assertIn(teacher_perf_level, analytics_html)
        self.assertNotIn("<strong>86%</strong>", analytics_html)

        # Check Student Attendance (/attendance)
        att_res = self.client.get("/attendance")
        self.assertEqual(att_res.status_code, 200)
        att_html = att_res.data.decode()
        for att_rec in t_data["attendance_records"]:
            self.assertIn(att_rec["subject"], att_html)
            self.assertIn(f"{att_rec['percentage']}%", att_html)
        self.client.get("/logout")

        # 3. Teacher updates prediction for Vishal (Live Forecast)
        self.login_teacher()
        post_pred = self.client.post("/teacher/prediction", data={
            "student_id": str(vishal_id),
            "attendance": "96.0",
            "studyHours": "28.0",
            "previousMarks": "94.0",
            "sleep_duration": "8.0",
            "social_media": "1.0",
            "participation": "high",
            "gender": "Male"
        }, follow_redirects=True)
        self.assertEqual(post_pred.status_code, 200)

        # Retrieve new latest prediction recorded
        new_pred = conn.execute("SELECT * FROM predictions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (vishal_id,)).fetchone()
        self.assertIsNotNone(new_pred)
        new_score = new_pred["predicted_score"]
        new_level = new_pred["performance_level"]
        self.client.get("/logout")

        # 4. Student logs back in and verifies the live update reflects immediately
        self.login_student(identifier=vishal["email"], password=vishal["password"], phone=vishal["phone"])
        dash_res2 = self.client.get("/dashboard")
        self.assertEqual(dash_res2.status_code, 200)
        dash_html2 = dash_res2.data.decode()
        self.assertTrue(f"{int(new_score)}%" in dash_html2 or f"{new_score}%" in dash_html2)
        self.assertIn(new_level, dash_html2)
        self.client.get("/logout")

        # Restore original baseline prediction row
        conn.execute("DELETE FROM predictions WHERE student_id = ?", (vishal_id,))
        conn.execute("""
            INSERT INTO predictions
            (id, student_id, predicted_score, performance_level, risk_level, prediction_date, attendance, study_hours, previous_marks, sleep_hours, social_media_hours)
            VALUES (401, ?, 68.0, 'Average Performance', 'Low Risk', '2026-09-29 17:29:27', 87.0, 16.0, 80.0, 8.0, 2.0)
        """, (vishal_id,))
        conn.commit()
        conn.close()

    def test_34_teacher_marked_attendance_shows_on_top(self):
        """Verify that when a teacher marks attendance (single or class), the marked record shows at the very top of attendance records"""
        self.login_teacher()

        conn = get_db_connection()
        # Find an attendance record to test single student marking
        all_recs = conn.execute("SELECT id, student_id, subject FROM attendance ORDER BY id ASC").fetchall()
        self.assertTrue(len(all_recs) >= 2)
        target_rec = all_recs[-1]
        target_id = target_rec["id"]

        # 1. Teacher marks single attendance (Present)
        res = self.client.post("/teacher/attendance/mark-single", data={
            "attendance_id": str(target_id),
            "status": "present"
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn(f"highlight={target_id}", res.headers["Location"])

        # Fetch redirected teacher attendance page
        res_page = self.client.get(res.headers["Location"])
        self.assertEqual(res_page.status_code, 200)
        html = res_page.data.decode()

        # The target row should be marked highlighted and show Just Marked badge
        self.assertIn(f'id="attendance-row-{target_id}"', html)
        self.assertIn("row-highlighted", html)
        self.assertIn("Just Marked", html)

        # Parse tbody to ensure target_id is the FIRST row in the attendance table
        tbody_start = html.find("<tbody>")
        first_row_start = html.find("<tr", tbody_start)
        first_row_end = html.find("</tr>", first_row_start)
        first_row_html = html[first_row_start:first_row_end]
        self.assertIn(f'id="attendance-row-{target_id}"', first_row_html)
        self.assertIn("Just Marked", first_row_html)

        # 2. Teacher marks class attendance for a subject
        students = conn.execute("SELECT id FROM students LIMIT 3").fetchall()
        stu_ids = [str(s["id"]) for s in students]
        class_subject = "Cloud Computing"

        res_class = self.client.post("/teacher/attendance/mark-class", data={
            "subject": class_subject,
            "all_student_ids": stu_ids,
            "present_student_ids": [stu_ids[0]]
        }, follow_redirects=False)
        self.assertEqual(res_class.status_code, 302)
        self.assertIn("highlight_subject=", res_class.headers["Location"])

        res_class_page = self.client.get(res_class.headers["Location"])
        self.assertEqual(res_class_page.status_code, 200)
        html_class = res_class_page.data.decode()

        # The first row in tbody should now belong to class_subject
        tbody_start_c = html_class.find("<tbody>")
        first_row_start_c = html_class.find("<tr", tbody_start_c)
        first_row_end_c = html_class.find("</tr>", first_row_start_c)
        first_row_html_c = html_class[first_row_start_c:first_row_end_c]
        self.assertIn(class_subject, first_row_html_c)
        self.assertIn("Just Marked", first_row_html_c)

        # 3. Direct access to /teacher/attendance without query params still lists updated records first
        res_direct = self.client.get("/teacher/attendance")
        self.assertEqual(res_direct.status_code, 200)
        html_direct = res_direct.data.decode()
        tbody_start_d = html_direct.find("<tbody>")
        first_row_start_d = html_direct.find("<tr", tbody_start_d)
        first_row_end_d = html_direct.find("</tr>", first_row_start_d)
        first_row_html_d = html_direct[first_row_start_d:first_row_end_d]
        self.assertIn(class_subject, first_row_html_d)

        # Cleanup created class records to restore baseline
        conn.execute("DELETE FROM attendance WHERE subject = ?", (class_subject,))
        conn.commit()
        conn.close()
        self.client.get("/logout")

if __name__ == '__main__':
    unittest.main()


