import json
import os

NOTEBOOK_DIR = "/Users/yuvii/Downloads/Student_Performance_2/notebook"

def make_notebook(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.13"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

def md_cell(text):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.split("\n")]
    }

def code_cell(code):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in code.split("\n")]
    }

# Notebook 1: Data Loading and EDA
nb1_cells = [
    md_cell("""# Predictive Analytics for Student Performance
## Phase 1: Data Loading & Exploratory Data Analysis (EDA)

### Objective
Analyze factors influencing student performance, understand feature distributions, inspect correlations with exam scores, and prepare for preprocessing."""),
    code_cell("""import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

plt.style.use('ggplot')
sns.set_palette('Set2')
print("Libraries imported successfully!")"""),
    md_cell("### 1. Load Dataset"),
    code_cell("""df = pd.read_csv('../data/student_performance.csv')
print(f"Dataset Shape: {df.shape}")
df.head()"""),
    md_cell("### 2. Dataset Information & Summary Statistics"),
    code_cell("""df.info()"""),
    code_cell("""df.describe()"""),
    md_cell("### 3. Check for Missing Values"),
    code_cell("""missing = df.isnull().sum()
missing[missing > 0]"""),
    md_cell("### 4. Target Variable Distribution (Exam Score)"),
    code_cell("""plt.figure(figsize=(8, 5))
sns.histplot(df['Exam_Score'], kde=True, bins=30, color='#6C63FF')
plt.title('Distribution of Exam Scores')
plt.xlabel('Exam Score')
plt.ylabel('Count')
plt.show()"""),
    md_cell("### 5. Hours Studied vs. Exam Score"),
    code_cell("""plt.figure(figsize=(8, 5))
sns.scatterplot(x='Hours_Studied', y='Exam_Score', data=df, alpha=0.5, color='#4CAF50')
plt.title('Hours Studied vs. Exam Score')
plt.show()"""),
    md_cell("### 6. Attendance vs. Exam Score"),
    code_cell("""plt.figure(figsize=(8, 5))
sns.scatterplot(x='Attendance', y='Exam_Score', data=df, alpha=0.5, color='#FF9800')
plt.title('Attendance vs. Exam Score')
plt.show()""")
]

# Notebook 2: Data Preprocessing
nb2_cells = [
    md_cell("""# Predictive Analytics for Student Performance
## Phase 2: Data Preprocessing

### Objective
Handle missing values, encode categorical variables, scale numerical features, and split the dataset for training."""),
    code_cell("""import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

df = pd.read_csv('../data/student_performance.csv')
print(f"Original Shape: {df.shape}")"""),
    md_cell("### 1. Handling Missing Values"),
    code_cell("""for col in ['Teacher_Quality', 'Parental_Education_Level', 'Distance_from_Home']:
    mode_val = df[col].mode()[0]
    df[col] = df[col].fillna(mode_val)
    print(f"Imputed {col} with mode: {mode_val}")

print("Remaining null values:", df.isnull().sum().sum())"""),
    md_cell("### 2. Encoding Categorical Features"),
    code_cell("""categorical_cols = [
    'Parental_Involvement', 'Access_to_Resources', 'Extracurricular_Activities',
    'Motivation_Level', 'Internet_Access', 'Family_Income', 'Teacher_Quality',
    'School_Type', 'Peer_Influence', 'Learning_Disabilities',
    'Parental_Education_Level', 'Distance_from_Home', 'Gender'
]

label_encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le

print("Categorical encoding complete.")
df[categorical_cols].head()"""),
    md_cell("### 3. Feature Matrix and Target Separation"),
    code_cell("""numerical_cols = ['Hours_Studied', 'Attendance', 'Sleep_Hours', 'Previous_Scores', 'Tutoring_Sessions', 'Physical_Activity']
features = numerical_cols + categorical_cols

X = df[features]
y = df['Exam_Score']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"Train size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")"""),
    md_cell("### 4. Feature Scaling"),
    code_cell("""scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
print("Feature scaling complete.")""")
]

# Notebook 3: Model Building
nb3_cells = [
    md_cell("""# Predictive Analytics for Student Performance
## Phase 3: Model Building

### Objective
Train regression algorithms (Linear Regression, Decision Tree, Random Forest Regressor) and serialize best model."""),
    code_cell("""import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

# Load & prepare data
df = pd.read_csv('../data/student_performance.csv')
for col in ['Teacher_Quality', 'Parental_Education_Level', 'Distance_from_Home']:
    df[col] = df[col].fillna(df[col].mode()[0])

categorical_cols = [
    'Parental_Involvement', 'Access_to_Resources', 'Extracurricular_Activities',
    'Motivation_Level', 'Internet_Access', 'Family_Income', 'Teacher_Quality',
    'School_Type', 'Peer_Influence', 'Learning_Disabilities',
    'Parental_Education_Level', 'Distance_from_Home', 'Gender'
]
numerical_cols = ['Hours_Studied', 'Attendance', 'Sleep_Hours', 'Previous_Scores', 'Tutoring_Sessions', 'Physical_Activity']

label_encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le

X = df[numerical_cols + categorical_cols]
y = df['Exam_Score']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)"""),
    md_cell("### 1. Train Linear Regression"),
    code_cell("""lr = LinearRegression()
lr.fit(X_train_scaled, y_train)
lr_preds = lr.predict(X_test_scaled)
print(f"Linear Regression R2: {r2_score(y_test, lr_preds):.4f}")"""),
    md_cell("### 2. Train Decision Tree Regressor"),
    code_cell("""dt = DecisionTreeRegressor(max_depth=6, random_state=42)
dt.fit(X_train_scaled, y_train)
dt_preds = dt.predict(X_test_scaled)
print(f"Decision Tree R2: {r2_score(y_test, dt_preds):.4f}")"""),
    md_cell("### 3. Train Random Forest Regressor"),
    code_cell("""rf = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
rf.fit(X_train_scaled, y_train)
rf_preds = rf.predict(X_test_scaled)
print(f"Random Forest R2: {r2_score(y_test, rf_preds):.4f}")
print(f"Random Forest MAE: {mean_absolute_error(y_test, rf_preds):.4f}")"""),
    md_cell("### 4. Save Final Model Artifacts"),
    code_cell("""with open('../models/random_forest_model.pkl', 'wb') as f:
    pickle.dump(rf, f)
with open('../models/scaler.pkl', 'wb') as f:
    pickle.dump(scaler, f)
with open('../models/label_encoders.pkl', 'wb') as f:
    pickle.dump(label_encoders, f)
print("Model artifacts saved to ../models/")""")
]

# Notebook 4: Model Evaluation
nb4_cells = [
    md_cell("""# Predictive Analytics for Student Performance
## Phase 4: Model Evaluation & Interpretation

### Objective
Evaluate the model across standard regression metrics (MAE, MSE, RMSE, R²), plot residuals, and analyze feature importance."""),
    code_cell("""import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Load artifacts
with open('../models/random_forest_model.pkl', 'rb') as f:
    rf = pickle.load(f)
with open('../models/scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)
with open('../models/label_encoders.pkl', 'rb') as f:
    encoders = pickle.load(f)

# Load data and evaluate
df = pd.read_csv('../data/student_performance.csv')
for col in ['Teacher_Quality', 'Parental_Education_Level', 'Distance_from_Home']:
    df[col] = df[col].fillna(df[col].mode()[0])

categorical_cols = list(encoders.keys())
numerical_cols = ['Hours_Studied', 'Attendance', 'Sleep_Hours', 'Previous_Scores', 'Tutoring_Sessions', 'Physical_Activity']

for col in categorical_cols:
    df[col] = encoders[col].transform(df[col].astype(str))

features = numerical_cols + categorical_cols
X = df[features]
y = df['Exam_Score']

X_scaled = scaler.transform(X)
preds = rf.predict(X_scaled)"""),
    md_cell("### 1. Overall Performance Metrics"),
    code_cell("""mae = mean_absolute_error(y, preds)
mse = mean_squared_error(y, preds)
rmse = np.sqrt(mse)
r2 = r2_score(y, preds)

print("Evaluation Summary:")
print(f"  R2 Score: {r2:.4f}")
print(f"  MAE:      {mae:.4f}")
print(f"  RMSE:     {rmse:.4f}")"""),
    md_cell("### 2. Actual vs. Predicted Exam Scores"),
    code_cell("""plt.figure(figsize=(8, 6))
plt.scatter(y[:200], preds[:200], alpha=0.6, color='#6C63FF')
plt.plot([y.min(), y.max()], [y.min(), y.max()], 'r--', lw=2)
plt.xlabel('Actual Exam Score')
plt.ylabel('Predicted Exam Score')
plt.title('Actual vs. Predicted Exam Scores')
plt.show()"""),
    md_cell("### 3. Feature Importance Analysis"),
    code_cell("""importances = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
plt.figure(figsize=(10, 6))
importances.plot(kind='bar', color='#4CAF50')
plt.title('Feature Importances in Predicting Exam Score')
plt.ylabel('Importance')
plt.xlabel('Feature')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.show()""")
]

with open(os.path.join(NOTEBOOK_DIR, "1_Data_Loading_and_EDA.ipynb"), "w") as f:
    json.dump(make_notebook(nb1_cells), f, indent=1)

with open(os.path.join(NOTEBOOK_DIR, "2_Data_Preprocessing.ipynb"), "w") as f:
    json.dump(make_notebook(nb2_cells), f, indent=1)

with open(os.path.join(NOTEBOOK_DIR, "3_Model_Building.ipynb"), "w") as f:
    json.dump(make_notebook(nb3_cells), f, indent=1)

with open(os.path.join(NOTEBOOK_DIR, "4_Model_Evaluation.ipynb"), "w") as f:
    json.dump(make_notebook(nb4_cells), f, indent=1)

print("All 4 notebooks written successfully!")
