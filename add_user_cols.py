import sqlite3

conn = sqlite3.connect('C:/Users/project/Documents/RapidRelief/backend/rapidrelief.db')
c = conn.cursor()

try:
    c.execute("ALTER TABLE users ADD COLUMN lat FLOAT")
except Exception as e:
    print(f"lat already exists or error: {e}")

try:
    c.execute("ALTER TABLE users ADD COLUMN lng FLOAT")
except Exception as e:
    print(f"lng already exists or error: {e}")

try:
    c.execute("ALTER TABLE users ADD COLUMN location_updated_at FLOAT")
except Exception as e:
    print(f"location_updated_at already exists or error: {e}")

conn.commit()
conn.close()
print("Database schema updated.")
