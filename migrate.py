from app.db.session import engine
from app.db.models import Base
import sqlite3

print("Creating new tables...")
Base.metadata.create_all(bind=engine)

print("Adding organization_id to existing tables...")
conn = sqlite3.connect('rapidrelief.db')
cursor = conn.cursor()

tables_to_update = ['zones', 'devices', 'zone_nodes']
for table in tables_to_update:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN organization_id INTEGER REFERENCES organizations(id);")
        print(f"Added organization_id to {table}")
    except sqlite3.OperationalError as e:
        print(f"Column might already exist in {table} or error: {e}")

try:
    cursor.execute("ALTER TABLE organizations ADD COLUMN address VARCHAR;")
    print("Added address to organizations")
except sqlite3.OperationalError as e:
    print(f"address column might already exist or error: {e}")

conn.commit()
conn.close()
print("Migration complete!")
