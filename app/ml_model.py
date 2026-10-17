import os
import json
import pickle
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

_model = None
_scaler = None
_encoders = None
_metadata = None


def _load_artifacts():
    global _model, _scaler, _encoders, _metadata
    if _model is not None:
        return

    rf_path = os.path.join(MODELS_DIR, "random_forest_model.pkl")
    scaler_path = os.path.join(MODELS_DIR, "scaler.pkl")
    encoders_path = os.path.join(MODELS_DIR, "label_encoders.pkl")
    meta_path = os.path.join(MODELS_DIR, "model_metadata.json")

    if not os.path.exists(rf_path) or not os.path.exists(scaler_path) or not os.path.exists(encoders_path):
        raise FileNotFoundError("Trained model artifacts not found in models directory.")

    with open(rf_path, "rb") as f:
        _model = pickle.load(f)
    with open(scaler_path, "rb") as f:
        _scaler = pickle.load(f)
    with open(encoders_path, "rb") as f:
        _encoders = pickle.load(f)

    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            _metadata = json.load(f)
    else:
        _metadata = {}


def get_feature_importances():
    """
    Extract actual feature importances directly from the trained Random Forest model.
    Does NOT invent or hardcode values.
    """
    _load_artifacts()
    feature_cols = _metadata.get("feature_cols", [])
    if hasattr(_model, "feature_importances_") and len(feature_cols) == len(_model.feature_importances_):
        importances = dict(zip(feature_cols, [round(float(v), 4) for v in _model.feature_importances_]))
        sorted_imp = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))
        return sorted_imp
    return _metadata.get("feature_importances", {})


def analyze_student_parameters(attendance, study_hours, previous_scores, sleep_duration, social_media, motivation):
    """
    Parameter-wise interpretation based on defined educational ranges.
    These ranges are used strictly for human-readable interpretation and recommendations,
    never as manual prediction weights.
    """
    # 1. ATTENDANCE
    # 90–100% -> Excellent | 85–89% -> Good | 75–84% -> Moderate | <75% -> Needs Improvement
    if attendance >= 90.0:
        att_status = "Excellent"
        att_msg = "Attendance is in a strong range."
    elif attendance >= 85.0:
        att_status = "Good"
        att_msg = "Attendance meets recommended high-performance benchmarks."
    elif attendance >= 75.0:
        att_status = "Moderate"
        att_msg = "Attendance is acceptable, but improving toward 85%+ supports higher outcomes."
    else:
        att_status = "Needs Improvement"
        att_msg = "Attendance is low and negatively impacts overall academic performance."

    # 2. STUDY HOURS
    # >=20 -> Excellent | 16–19 -> Very Good | 12–15 -> Good | 8–11 -> Needs Improvement | <8 -> Low
    if study_hours >= 20.0:
        study_status = "Excellent"
        study_msg = "Dedicated study time is well above benchmark levels."
    elif study_hours >= 16.0:
        study_status = "Very Good"
        study_msg = "Study time is in a strong range."
    elif study_hours >= 12.0:
        study_status = "Good"
        study_msg = "Study routine is steady; increasing toward 16+ hrs/week can bolster outcomes."
    elif study_hours >= 8.0:
        study_status = "Needs Improvement"
        study_msg = "Study hours are below recommended range."
    else:
        study_status = "Low"
        study_msg = "Insufficient study time to master core coursework topics."

    # 3. PREVIOUS EXAM MARKS
    # 90–100 -> Excellent | 85–89 -> Very Good | 80–84 -> Good | 70–79 -> Moderate | <70 -> Needs Improvement
    if previous_scores >= 90.0:
        prev_status = "Excellent"
        prev_msg = "Outstanding mastery of foundational course material."
    elif previous_scores >= 85.0:
        prev_status = "Very Good"
        prev_msg = "Previous academic performance is a strong indicator."
    elif previous_scores >= 80.0:
        prev_status = "Good"
        prev_msg = "Solid previous marks with potential to reach top tier."
    elif previous_scores >= 70.0:
        prev_status = "Moderate"
        prev_msg = "Moderate prior scores; targeted revision is recommended."
    else:
        prev_status = "Needs Improvement"
        prev_msg = "Prior assessment marks indicate key conceptual gaps."

    # 4. SLEEP DURATION
    # 7–9 -> Optimal | 6–7 -> Acceptable | 5–6 -> Low | <5 -> Very Low | >10 -> Excessive
    if 7.0 <= sleep_duration <= 9.0:
        sleep_status = "Optimal"
        sleep_msg = "Sleep duration is within the recommended range."
    elif 6.0 <= sleep_duration < 7.0:
        sleep_status = "Acceptable"
        sleep_msg = "Sleep is acceptable; 7–9 hours provides best cognitive recovery."
    elif 5.0 <= sleep_duration < 6.0:
        sleep_status = "Low"
        sleep_msg = "Sleep duration is low; fatigue can hinder memory and focus."
    elif sleep_duration < 5.0:
        sleep_status = "Very Low"
        sleep_msg = "Severe sleep deficit significantly impairs academic focus."
    else:
        sleep_status = "Excessive"
        sleep_msg = "Sleep duration is excessive and may disrupt productive study hours."

    # 5. SOCIAL MEDIA USAGE
    # <=2 -> Low/Healthy | 2–3 -> Moderate | 3–4 -> High | >4 -> Very High
    if social_media <= 2.0:
        social_status = "Low"
        social_msg = "Social media usage is within a favorable range."
    elif social_media <= 3.0:
        social_status = "Moderate"
        social_msg = "Moderate social media usage; keep screen time in check."
    elif social_media <= 4.0:
        social_status = "High"
        social_msg = "Elevated screen time may detract from focused study sessions."
    else:
        social_status = "Very High"
        social_msg = "Excessive recreational screen time reduces available study hours."

    # 6. MOTIVATION LEVEL (Dataset trained feature: Motivation_Level)
    # High -> Strong | Medium -> Moderate | Low -> Needs Improvement
    mot_normalized = str(motivation).strip().capitalize()
    if mot_normalized == "High":
        mot_status = "Strong"
        mot_msg = "High motivation and strong engagement in coursework."
    elif mot_normalized == "Low":
        mot_status = "Needs Improvement"
        mot_msg = "Low motivation; proactive guidance and faculty mentorship are advised."
    else:
        mot_status = "Moderate"
        mot_msg = "Moderate motivation; increasing active participation will help."

    return {
        "attendance": {
            "name": "Attendance",
            "value": attendance,
            "display_value": f"{attendance:g}%" if isinstance(attendance, (int, float)) else f"{attendance}%",
            "status": att_status,
            "message": att_msg,
            "benchmark": ">=85–90%"
        },
        "study_hours": {
            "name": "Study Hours",
            "value": study_hours,
            "display_value": f"{study_hours:g} hrs/week" if isinstance(study_hours, (int, float)) else f"{study_hours} hrs/week",
            "status": study_status,
            "message": study_msg,
            "benchmark": ">=16 hours/week"
        },
        "previous_marks": {
            "name": "Previous Marks",
            "value": previous_scores,
            "display_value": f"{previous_scores:g}%" if isinstance(previous_scores, (int, float)) else f"{previous_scores}%",
            "status": prev_status,
            "message": prev_msg,
            "benchmark": ">=85%"
        },
        "sleep_duration": {
            "name": "Sleep",
            "value": sleep_duration,
            "display_value": f"{sleep_duration:g} hrs/day" if isinstance(sleep_duration, (int, float)) else f"{sleep_duration} hrs/day",
            "status": sleep_status,
            "message": sleep_msg,
            "benchmark": "7–9 hours/day"
        },
        "social_media": {
            "name": "Social Media",
            "value": social_media,
            "display_value": f"{social_media:g} hrs/day" if isinstance(social_media, (int, float)) else f"{social_media} hrs/day",
            "status": social_status,
            "message": social_msg,
            "benchmark": "<=2 hours/day"
        },
        "motivation_level": {
            "name": "Motivation",
            "value": mot_normalized if mot_normalized in ["High", "Medium", "Low"] else "Medium",
            "display_value": mot_normalized if mot_normalized in ["High", "Medium", "Low"] else "Medium",
            "status": mot_status,
            "message": mot_msg,
            "benchmark": "High"
        }
    }


def generate_parameter_recommendations(attendance, study_hours, previous_scores, sleep_duration, social_media, motivation):
    """
    Generate targeted recommendations strictly based on weaker parameters.
    Recommendations NEVER modify the Random Forest prediction score.
    """
    recs = []
    if attendance < 85.0:
        recs.append("Consider improving attendance toward 85% or above.")
    if study_hours < 16.0:
        recs.append("Consider increasing focused study time toward 16+ hours per week.")
    if previous_scores < 85.0:
        recs.append("Focus on strengthening topics from previous assessments.")
    if sleep_duration < 7.0:
        recs.append("Try to maintain a consistent sleep schedule around 7–9 hours.")
    elif sleep_duration > 10.0:
        recs.append("Regulate daily rest routine to ensure consistent productive daytime hours.")
    if social_media > 3.0:
        recs.append("Consider reducing recreational social media usage to increase focused study time.")
    if str(motivation).strip().capitalize() == "Low":
        recs.append("Increase classroom engagement and seek faculty mentorship.")

    if not recs:
        recs.append("All key student parameters are within high-performance benchmarks. Continue consistent academic routine.")

    return recs


def predict_student_performance(inputs=None):
    """
    Predict student exam performance using the trained RandomForestRegressor model.
    The prediction is derived directly from model.predict() without artificial score boosting
    or double counting of inputs.
    """
    _load_artifacts()

    inputs = inputs or {}

    def _parse_val(val, default):
        if val is None or str(val).strip() == "":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    # Parse primary student input features
    attendance = _parse_val(inputs.get("attendance") if "attendance" in inputs else inputs.get("Attendance"), 80.0)
    study_hours = _parse_val(inputs.get("study_hours") if "study_hours" in inputs else (inputs.get("studyHours") if "studyHours" in inputs else inputs.get("Hours_Studied")), 15.0)
    previous_scores = _parse_val(inputs.get("previous_marks") if "previous_marks" in inputs else (inputs.get("previousMarks") if "previousMarks" in inputs else inputs.get("Previous_Scores")), 75.0)
    sleep_duration = _parse_val(inputs.get("sleep_duration") if "sleep_duration" in inputs else (inputs.get("sleep_hours") if "sleep_hours" in inputs else (inputs.get("sleepHours") if "sleepHours" in inputs else inputs.get("Sleep_Hours"))), 7.0)
    social_media = _parse_val(inputs.get("social_media") if "social_media" in inputs else (inputs.get("social_media_usage") if "social_media_usage" in inputs else (inputs.get("socialMediaHours") if "socialMediaHours" in inputs else inputs.get("Social_Media_Usage"))), 2.0)

    # Motivation Level (mapped to trained feature 'Motivation_Level')
    raw_mot = inputs.get("motivation_level") or inputs.get("motivation") or inputs.get("participation") or "Medium"
    motivation = str(raw_mot).strip().capitalize()
    if motivation not in ["High", "Medium", "Low"]:
        motivation = "Medium"

    # Gender
    gender = str(inputs.get("gender") or "Female").strip().capitalize()
    if gender not in ["Female", "Male"]:
        gender = "Female"

    # Base values from metadata defaults
    defaults = _metadata.get("defaults", {})
    record = dict(defaults)

    # Override with input values
    record["Attendance"] = attendance
    record["Hours_Studied"] = study_hours
    record["Previous_Scores"] = previous_scores
    record["Sleep_Hours"] = sleep_duration
    record["Social_Media_Usage"] = social_media
    record["Motivation_Level"] = motivation
    record["Gender"] = gender

    if "tutoring_sessions" in inputs:
        record["Tutoring_Sessions"] = _parse_val(inputs["tutoring_sessions"], record.get("Tutoring_Sessions", 1.0))
    if "physical_activity" in inputs:
        record["Physical_Activity"] = _parse_val(inputs["physical_activity"], record.get("Physical_Activity", 3.0))

    feature_cols = _metadata.get("feature_cols", [
        "Hours_Studied", "Attendance", "Sleep_Hours", "Social_Media_Usage", "Previous_Scores",
        "Tutoring_Sessions", "Physical_Activity",
        "Parental_Involvement", "Access_to_Resources", "Extracurricular_Activities",
        "Motivation_Level", "Internet_Access", "Family_Income", "Teacher_Quality",
        "School_Type", "Peer_Influence", "Learning_Disabilities",
        "Parental_Education_Level", "Distance_from_Home", "Gender"
    ])

    # Construct feature row according to exact trained column order
    row = []
    for col in feature_cols:
        val = record.get(col, defaults.get(col, 0))
        if col in _encoders:
            le = _encoders[col]
            val_str = str(val)
            if val_str in le.classes_:
                encoded_val = le.transform([val_str])[0]
            else:
                encoded_val = 0
            row.append(encoded_val)
        else:
            row.append(float(val))

    # Scale features using pre-fitted StandardScaler
    X_df = pd.DataFrame([row], columns=feature_cols)
    X_scaled = _scaler.transform(X_df)

    # DIRECT RANDOM FOREST REGRESSION PREDICTION
    # The trained Random Forest is the primary predictor: no double-counting or artificial weights
    raw_pred = float(_model.predict(X_scaled)[0])
    score_float = round(max(0.0, min(100.0, raw_pred)), 1)
    int_score = int(round(score_float))

    # 85% Performance Threshold Classification:
    # >= 85: "Excellent Performance", "85%+"
    # 75–84: "Good Performance"
    # 60–74: "Average Performance"
    # < 60: "Needs Improvement"
    meets_85_threshold = bool(score_float >= 85.0)

    if score_float >= 85.0:
        performance_category = "Excellent Performance"
        threshold_label = "85%+"
        status = "Excellent Performance"
        risk_level = "Low Risk"
        description = "Predicted performance meets the Excellent Performance threshold (85%+)."
    elif score_float >= 75.0:
        performance_category = "Good Performance"
        threshold_label = "75–84%"
        status = "Good Performance"
        risk_level = "Low Risk"
        description = "Predicted performance is in the Good Performance range (75–84%)."
    elif score_float >= 60.0:
        performance_category = "Average Performance"
        threshold_label = "60–74%"
        status = "Average Performance"
        if attendance < 60.0 or previous_scores < 50.0:
            risk_level = "High Risk"
            description = "Predicted performance is in the Average Performance range, but critical attendance or prior marks indicate high risk."
        elif attendance >= 85.0 and previous_scores >= 80.0:
            risk_level = "Low Risk"
            description = "Predicted performance is in the Average Performance range, supported by strong academic engagement."
        else:
            risk_level = "Moderate Risk"
            description = "Predicted performance is in the Average Performance range (60–74%)."
    else:
        performance_category = "Needs Improvement"
        threshold_label = "<60%"
        status = "Needs Improvement"
        risk_level = "High Risk"
        description = "Predicted performance is below 60%, indicating needs improvement."

    # Parameter-wise analysis
    param_analysis = analyze_student_parameters(
        attendance=attendance,
        study_hours=study_hours,
        previous_scores=previous_scores,
        sleep_duration=sleep_duration,
        social_media=social_media,
        motivation=motivation
    )

    # Targeted recommendations for weaker parameters
    recs_list = generate_parameter_recommendations(
        attendance=attendance,
        study_hours=study_hours,
        previous_scores=previous_scores,
        sleep_duration=sleep_duration,
        social_media=social_media,
        motivation=motivation
    )
    recommendation_text = " ".join(recs_list)

    # Actual feature importances from trained model
    sorted_importances = get_feature_importances()
    top_feature_list = [
        {"feature": k.replace("_", " "), "importance": round(v, 4), "percentage": round(v * 100, 1)}
        for k, v in list(sorted_importances.items())[:8]
    ]

    # High-Performance Profile benchmarks
    high_perf_profile = {
        "benchmarks": {
            "attendance": "85–90%+",
            "study_hours": "16+ hours/week",
            "previous_marks": "85%+",
            "sleep_duration": "7–9 hours/day",
            "social_media": "<= 2 hours/day",
            "motivation_level": "High"
        },
        "disclaimer": "These conditions represent a stronger academic profile. The final prediction is generated by the trained Random Forest model."
    }

    return {
        "predicted_score": int_score,
        "score_float": score_float,
        "status": status,
        "performance_category": performance_category,
        "threshold": threshold_label,
        "meets_85_threshold": meets_85_threshold,
        "risk_level": risk_level,
        "description": description,
        "recommendation": recommendation_text,
        "recommendations_list": recs_list,
        "parameter_analysis": param_analysis,
        "feature_importance": sorted_importances,
        "top_features": top_feature_list,
        "feature_importance_disclaimer": "Feature importance describes how the trained model uses features across its decision trees. It reflects model reliance rather than individual causal proof.",
        "high_performance_indicators": high_perf_profile,
        "factors": {
            "attendance": attendance,
            "study_hours": study_hours,
            "previous_marks": previous_scores,
            "sleep_duration": sleep_duration,
            "social_media": social_media,
            "participation": motivation,
            "motivation_level": motivation
        }
    }


if __name__ == "__main__":
    test_result = predict_student_performance({
        "attendance": 92,
        "study_hours": 18,
        "previous_marks": 86,
        "sleep_duration": 8,
        "social_media": 1.5,
        "motivation_level": "High"
    })
    print("Test prediction result:")
    print(json.dumps(test_result, indent=2))
