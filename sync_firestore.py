import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models import User, Organization
from app.firebase.firebase import db

def sync_all_users():
    session = SessionLocal()
    try:
        users = session.query(User).all()
        for u in users:
            doc_data = {
                "uid": u.firebase_uid,
                "email": u.email,
                "role": u.role.lower() if u.role else None,
                "is_super_admin": u.is_super_admin,
            }
            if u.name:
                doc_data["fullName"] = u.name
            if u.phone:
                doc_data["phone"] = u.phone
                
            if u.organization_id:
                org = session.query(Organization).filter(Organization.id == u.organization_id).first()
                if org:
                    doc_data["organization_id"] = org.id
                    doc_data["organization_name"] = org.name
            
            print(f"Syncing user {u.email} ({u.role}) to Firestore...")
            db.collection("users").document(u.firebase_uid).set(doc_data, merge=True)
            
        print("Done syncing all users to Firestore!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    sync_all_users()
