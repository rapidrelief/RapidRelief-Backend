import pandas as pd
import numpy as np
import os

def generate_flood_data(rows=2000):
    np.random.seed(42)
    
    # Generate random historical weather features
    # Rainfall (mm/day)
    rainfall = np.random.exponential(scale=15, size=rows)
    # Add extreme rainfall events
    rainfall[np.random.rand(rows) < 0.05] += np.random.uniform(100, 300, size=int(0.05 * rows))
    
    # River Level (meters)
    river_level = 2.0 + (rainfall * 0.02) + np.random.normal(0, 0.5, size=rows)
    
    # Soil Moisture (%)
    soil_moisture = np.clip(np.random.normal(40, 15, size=rows) + (rainfall * 0.1), 0, 100)
    
    # Temperature (Celsius)
    temperature = np.random.normal(28, 5, size=rows)
    
    # Humidity (%)
    humidity = np.clip(np.random.normal(60, 15, size=rows) + (rainfall * 0.2), 0, 100)
    
    # Determine Flood (1 = Yes, 0 = No)
    # Flood is likely if rainfall > 100mm OR (river_level > 5.0 and soil_moisture > 80)
    flood = np.zeros(rows, dtype=int)
    flood[(rainfall > 120)] = 1
    flood[(river_level > 5.5) & (soil_moisture > 85)] = 1
    flood[(rainfall > 80) & (river_level > 4.5)] = 1
    
    # Add some noise to the target variable to make it realistic
    noise_idx = np.random.choice(rows, size=int(0.02 * rows), replace=False)
    flood[noise_idx] = 1 - flood[noise_idx]
    
    df = pd.DataFrame({
        'Rainfall_mm': np.round(rainfall, 2),
        'River_Level_m': np.round(river_level, 2),
        'Soil_Moisture_pct': np.round(soil_moisture, 2),
        'Temperature_C': np.round(temperature, 2),
        'Humidity_pct': np.round(humidity, 2),
        'Flood': flood
    })
    
    os.makedirs('app/ml', exist_ok=True)
    df.to_csv('app/ml/flood_data.csv', index=False)
    print(f"Generated {rows} rows of flood data. Flood events: {df['Flood'].sum()}")

if __name__ == '__main__':
    generate_flood_data()
