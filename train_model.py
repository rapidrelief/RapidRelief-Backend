import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

def train():
    # Load dataset
    df = pd.read_csv('app/ml/flood_data.csv')
    
    # Features and Target
    X = df[['Rainfall_mm', 'River_Level_m', 'Soil_Moisture_pct', 'Temperature_C', 'Humidity_pct']]
    y = df['Flood']
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Initialize Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    
    # Train model
    print("Training Random Forest Classifier...")
    rf.fit(X_train, y_train)
    
    # Evaluate model
    y_pred = rf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model Accuracy: {accuracy * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Save the model
    os.makedirs('app/ml', exist_ok=True)
    joblib.dump(rf, 'app/ml/flood_model.pkl')
    print("Model saved to app/ml/flood_model.pkl")

if __name__ == '__main__':
    train()
