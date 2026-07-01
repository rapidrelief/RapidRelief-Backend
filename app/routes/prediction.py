import os
import joblib
import pandas as pd
import requests
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Zone

router = APIRouter(prefix="/prediction", tags=["prediction"])

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "flood_model.pkl")

# Load model once
try:
    rf_model = joblib.load(MODEL_PATH)
except Exception as e:
    print(f"Warning: Could not load ML model: {e}")
    rf_model = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/zone/{zone_id}")
def get_zone_prediction(zone_id: int, days: int = 7, db: Session = Depends(get_db)):
    if rf_model is None:
        raise HTTPException(status_code=503, detail="ML Model not available. Please train it first.")

    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    # Fetch forecast from Open-Meteo
    url = f"https://api.open-meteo.com/v1/forecast?latitude={zone.lat}&longitude={zone.lng}&daily=precipitation_sum,temperature_2m_max&timezone=auto&forecast_days={days}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        weather_data = res.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather API Error: {e}")

    daily = weather_data.get("daily", {})
    dates = daily.get("time", [])
    rainfall_arr = daily.get("precipitation_sum", [])
    temp_arr = daily.get("temperature_2m_max", [])

    predictions = []
    
    for i in range(len(dates)):
        # Handle None values from API
        rainfall = rainfall_arr[i] if rainfall_arr[i] is not None else 0.0
        temp = temp_arr[i] if temp_arr[i] is not None else 25.0
        
        # FYP Simulation: Synthesize missing physical features based on rainfall
        river_level = 2.0 + (rainfall * 0.05)
        soil_moisture = min(100.0, 40.0 + (rainfall * 0.5))
        humidity = min(100.0, 60.0 + (rainfall * 0.2))

        # Create DataFrame for model input
        input_data = pd.DataFrame([{
            'Rainfall_mm': rainfall,
            'River_Level_m': river_level,
            'Soil_Moisture_pct': soil_moisture,
            'Temperature_C': temp,
            'Humidity_pct': humidity
        }])

        # Predict probability (Class 1 = Flood)
        prob = rf_model.predict_proba(input_data)[0][1]
        
        # Determine Risk Level
        risk_level = "LOW"
        if prob > 0.7:
            risk_level = "HIGH"
        elif prob > 0.4:
            risk_level = "MEDIUM"

        predictions.append({
            "date": dates[i],
            "rainfall_mm": rainfall,
            "temperature_c": temp,
            "river_level_m": round(river_level, 2),
            "soil_moisture_pct": round(soil_moisture, 2),
            "humidity_pct": round(humidity, 2),
            "flood_probability": round(prob * 100, 2),
            "risk_level": risk_level
        })

    return {
        "zone_id": zone.id,
        "zone_name": zone.name,
        "forecast": predictions
    }
