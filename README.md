# StudentIQ – Predictive Analytics for Student Performance

## About the Project

**StudentIQ** is a machine learning-based web application developed to analyze, monitor, and predict students' academic performance. The system uses student academic records, attendance, and evaluation data to generate performance predictions and identify students who may be at academic risk.

The application provides separate interfaces for teachers and students, enabling teachers to manage student information, record attendance, evaluate performance, and generate reports, while students can monitor their academic progress through personalized dashboards.

By combining machine learning with interactive data visualization, StudentIQ aims to support early identification of academic difficulties and help educators make informed, data-driven decisions.

## Key Features

- **User Authentication:** Secure login and role-based access for teachers and students.
- **Student Management:** Add, search, view, and manage student records.
- **Attendance Management:** Record and monitor overall and subject-wise student attendance.
- **Performance Prediction:** Use a trained machine learning model to predict student performance based on relevant input features.
- **Academic Risk Assessment:** Help identify students who may require additional academic support.
- **Student Evaluation:** Record and review students' academic and developmental evaluations.
- **Analytics and Insights:** Visualize academic performance, attendance statistics, and performance trends through interactive dashboards.
- **Report Generation:** Generate performance and risk analysis reports for academic monitoring.
- **Student Dashboard:** Allow students to view their academic performance, attendance, predictions, and analytics.
- **Profile and Settings:** Manage account information and application preferences.
- **OTP Verification:** Support phone-based OTP verification for applicable authentication and password recovery workflows.

## Technologies Used

- **Programming Language:** Python
- **Backend Framework:** Flask
- **Database:** SQLite3
- **Frontend:** HTML, CSS, JavaScript
- **Machine Learning:** Scikit-learn
- **Data Processing:** Pandas and NumPy
- **Data Visualization:** Chart.js
- **Version Control:** Git and GitHub

## Machine Learning Approach

StudentIQ integrates a trained **Random Forest Regressor** to estimate student performance. The model uses processed input features to generate predictions that can be presented through the application's interface.

The machine learning workflow includes:
1. Dataset collection and exploration.
2. Data cleaning and preprocessing.
3. Feature encoding and numerical scaling, where required.
4. Model training and evaluation.
5. Saving the trained model and preprocessing artifacts.
6. Integrating the model with the Flask application for predictions.

## System Modules

| Module | Description |
|---|---|
| Authentication | Manages user login, registration, and applicable OTP verification. |
| Student Management | Maintains student information and academic records. |
| Attendance Management | Records attendance and calculates attendance statistics. |
| Student Evaluation | Supports the evaluation and monitoring of student progress. |
| Performance Prediction | Generates machine learning-based performance estimates. |
| Analytics and Insights | Displays academic statistics, trends, and performance indicators. |
| Reports | Generates reports for performance monitoring and risk assessment. |
| Student Portal | Provides students with access to their academic information and dashboards. |

## Project Objectives

- Analyze student academic performance using machine learning.
- Support early identification of students who may be academically at risk.
- Simplify student information and attendance management.
- Provide visual insights into academic progress.
- Help teachers make informed decisions using data-driven predictions.
- Encourage students to monitor and improve their academic performance.

## Future Enhancements

- Develop a dedicated Android and iOS application.
- Integrate real-time notifications for attendance shortages and academic risk.
- Provide personalized study recommendations.
- Explore advanced machine learning models to improve predictive performance.
- Deploy the application on a cloud platform for wider accessibility.

## Conclusion

StudentIQ combines web development, database management, machine learning, and data visualization into a unified academic monitoring system. It aims to make student performance analysis more accessible and help educators identify areas where students may need additional support.

**Project Type:** Academic Minor Project  
**Domain:** Machine Learning, Educational Technology, Predictive Analytics
