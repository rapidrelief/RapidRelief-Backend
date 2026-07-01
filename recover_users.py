import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.db.session import engine, SessionLocal
from app.db.models import Base, User
from app.firebase.firebase import db
from sync_firestore import backup_db
from app.routes.infrastructure import ensure_user_schema
import traceback

Base.metadata.create_all(bind=engine)
ensure_user_schema()

db_session = SessionLocal()

try:
    print("Recovering users from 'users' collection...")
    users_ref = db.collection('users').stream()
    recovered_count = 0
    for doc in users_ref:
        data = doc.to_dict()
        role = data.get("role", "").upper()
        if role in ["SUPER_ADMIN", "ORG_ADMIN", "RESCUER"]:
            uid = data.get("uid")
            if not uid: continue
            
            # Check if user already exists
            existing = db_session.query(User).filter(User.firebase_uid == uid).first()
            if existing: continue
            
            org_id = None
            if "organization_id" in data:
                raw_org = str(data["organization_id"])
                if raw_org.startswith("ORG-"):
                    try:
                        org_id = int(raw_org.split("-")[1]) - 1000
                    except:
                        pass
                else:
                    try:
                        org_id = int(raw_org)
                    except:
                        pass
                        
            new_user = User(
                firebase_uid=uid,
                email=data.get("email"),
                role=role,
                organization_id=org_id,
                name=data.get("fullName"),
                phone=data.get("phone"),
                is_super_admin=data.get("is_super_admin", False),
                lat=data.get("location", {}).get("lat") if data.get("location") else None,
                lng=data.get("location", {}).get("lng") if data.get("location") else None,
            )
            db_session.add(new_user)
            recovered_count += 1
            
    if recovered_count > 0:
        db_session.commit()
        print(f"Successfully recovered {recovered_count} users to SQLite!")
        print("Running backup_db to sync backup_users...")
        backup_db(db_session)
        print("Backup complete!")
    else:
        print("No admin/rescuer users found to recover (they might already be in local SQLite).")

except Exception as e:
    print("Error:", e)
    traceback.print_exc()
finally:
    db_session.close()
