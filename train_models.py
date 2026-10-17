import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "student_performance.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def train_and_save():
    print(f"Loading data from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    print(f"Dataset shape: {df.shape}")

    # Handle missing values
    categorical_cols = [
        "Parental_Involvement", "Access_to_Resources", "Extracurricular_Activities",
        "Motivation_Level", "Internet_Access", "Family_Income", "Teacher_Quality",
        "School_Type", "Peer_Influence", "Learning_Disabilities",
        "Parental_Education_Level", "Distance_from_Home", "Gender"
    ]

    numerical_cols = [
        "Hours_Studied", "Attendance", "Sleep_Hours", "Social_Media_Usage", "Previous_Scores",
        "Tutoring_Sessions", "Physical_Activity"
    ]

    target_col = "Exam_Score"

    # Fill missing values for categorical with mode, numerical with median
    for col in categorical_cols:
        if df[col].isnull().any():
            mode_val = df[col].mode()[0]
            df[col] = df[col].fillna(mode_val)
            print(f"Filled missing values in {col} with mode: {mode_val}")

    for col in numerical_cols:
        if df[col].isnull().any():
            med_val = df[col].median()
            df[col] = df[col].fillna(med_val)
            print(f"Filled missing values in {col} with median: {med_val}")

    # Encode categorical features
    label_encoders = {}
    encoded_df = df.copy()

    for col in categorical_cols:
        le = LabelEncoder()
        encoded_df[col] = le.fit_transform(encoded_df[col].astype(str))
        label_encoders[col] = le

    feature_cols = numerical_cols + categorical_cols
    X = encoded_df[feature_cols]
    y = encoded_df[target_col]

    # Split dataset
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train Random Forest Regressor
    print("Training Random Forest Regressor...")
    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train_scaled, y_train)

    # Train Linear Regression baseline
    lr_model = LinearRegression()
    lr_model.fit(X_train_scaled, y_train)

    # Evaluation
    rf_preds = rf_model.predict(X_test_scaled)
    lr_preds = lr_model.predict(X_test_scaled)

    rf_mae = mean_absolute_error(y_test, rf_preds)
    rf_mse = mean_squared_error(y_test, rf_preds)
    rf_rmse = np.sqrt(rf_mse)
    rf_r2 = r2_score(y_test, rf_preds)

    lr_r2 = r2_score(y_test, lr_preds)

    print("\n--- Model Evaluation Results ---")
    print(f"Linear Regression R2: {lr_r2:.4f}")
    print(f"Random Forest MAE:   {rf_mae:.4f}")
    print(f"Random Forest MSE:   {rf_mse:.4f}")
    print(f"Random Forest RMSE:  {rf_rmse:.4f}")
    print(f"Random Forest R2:    {rf_r2:.4f}")

    # Compute feature importances
    importances = dict(zip(feature_cols, [round(float(v), 4) for v in rf_model.feature_importances_]))
    sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))
    print("\nTop 5 Important Features:")
    for k, v in list(sorted_importances.items())[:5]:
        print(f"  {k}: {v}")

    # Save artifacts
    rf_path = os.path.join(MODELS_DIR, "random_forest_model.pkl")
    scaler_path = os.path.join(MODELS_DIR, "scaler.pkl")
    encoders_path = os.path.join(MODELS_DIR, "label_encoders.pkl")
    meta_path = os.path.join(MODELS_DIR, "model_metadata.json")

    with open(rf_path, "wb") as f:
        pickle.dump(rf_model, f)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    with open(encoders_path, "wb") as f:
        pickle.dump(label_encoders, f)

    # Save metadata including defaults for missing form inputs
    metadata = {
        "feature_cols": feature_cols,
        "numerical_cols": numerical_cols,
        "categorical_cols": categorical_cols,
        "metrics": {
            "mae": round(float(rf_mae), 3),
            "rmse": round(float(rf_rmse), 3),
            "r2": round(float(rf_r2), 3)
        },
        "feature_importances": sorted_importances,
        "defaults": {
            "Hours_Studied": float(df["Hours_Studied"].median()),
            "Attendance": float(df["Attendance"].median()),
            "Sleep_Hours": float(df["Sleep_Hours"].median()),
            "Social_Media_Usage": float(df["Social_Media_Usage"].median()),
            "Previous_Scores": float(df["Previous_Scores"].median()),
            "Tutoring_Sessions": float(df["Tutoring_Sessions"].median()),
            "Physical_Activity": float(df["Physical_Activity"].median()),
            "Parental_Involvement": str(df["Parental_Involvement"].mode()[0]),
            "Access_to_Resources": str(df["Access_to_Resources"].mode()[0]),
            "Extracurricular_Activities": str(df["Extracurricular_Activities"].mode()[0]),
            "Motivation_Level": str(df["Motivation_Level"].mode()[0]),
            "Internet_Access": str(df["Internet_Access"].mode()[0]),
            "Family_Income": str(df["Family_Income"].mode()[0]),
            "Teacher_Quality": str(df["Teacher_Quality"].mode()[0]),
            "School_Type": str(df["School_Type"].mode()[0]),
            "Peer_Influence": str(df["Peer_Influence"].mode()[0]),
            "Learning_Disabilities": str(df["Learning_Disabilities"].mode()[0]),
            "Parental_Education_Level": str(df["Parental_Education_Level"].mode()[0]),
            "Distance_from_Home": str(df["Distance_from_Home"].mode()[0]),
            "Gender": str(df["Gender"].mode()[0])
        }
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print("\nSaved artifacts successfully:")
    print(f"  {rf_path} ({os.path.getsize(rf_path)} bytes)")
    print(f"  {scaler_path} ({os.path.getsize(scaler_path)} bytes)")
    print(f"  {encoders_path} ({os.path.getsize(encoders_path)} bytes)")
    print(f"  {meta_path} ({os.path.getsize(meta_path)} bytes)")

if __name__ == "__main__":
    train_and_save()
