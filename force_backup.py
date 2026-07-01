import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.db.session import SessionLocal
from sync_firestore import backup_db

db_session = SessionLocal()
print("Forcing backup of local SQLite to Firestore...")
backup_db(db_session)
print("Backup complete!")
db_session.close()
