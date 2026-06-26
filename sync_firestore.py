import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Organization, Device, ZoneNode, Zone, SOSRequest
from app.firebase.firebase import db

def serialize_model(model_instance):
    return {c.name: getattr(model_instance, c.name) for c in model_instance.__table__.columns}

def backup_db(db_session):
    """Backs up the SQLite DB to Firestore."""
    try:
        for model_class, collection_name in [
            (Organization, 'backup_organizations'),
            (User, 'backup_users'),
            (Zone, 'backup_zones'),
            (Device, 'backup_devices'),
            (ZoneNode, 'backup_nodes'),
            (SOSRequest, 'backup_sos'),
        ]:
            docs = db_session.query(model_class).all()
            if not docs:
                continue
            pk_col = list(model_class.__table__.primary_key.columns)[0].name
            
            batch = db.batch()
            count = 0
            for item in docs:
                data = serialize_model(item)
                doc_id = str(data[pk_col])
                doc_ref = db.collection(collection_name).document(doc_id)
                batch.set(doc_ref, data)
                count += 1
                if count >= 400:
                    batch.commit()
                    batch = db.batch()
                    count = 0
            if count > 0:
                batch.commit()
    except Exception as e:
        print(f"Error during backup: {e}")

def restore_db(db_session):
    """Restores the SQLite DB from Firestore."""
    try:
        for model_class, collection_name in [
            (Organization, 'backup_organizations'),
            (User, 'backup_users'),
            (Zone, 'backup_zones'),
            (Device, 'backup_devices'),
            (ZoneNode, 'backup_nodes'),
            (SOSRequest, 'backup_sos'),
        ]:
            docs = db.collection(collection_name).stream()
            count = 0
            for doc in docs:
                data = doc.to_dict()
                db_session.add(model_class(**data))
                count += 1
            if count > 0:
                db_session.commit()
                print(f"Restored {count} records into {model_class.__tablename__}")
    except Exception as e:
        print(f"Error during restore: {e}")

if __name__ == "__main__":
    # If run standalone, execute backup
    session = SessionLocal()
    backup_db(session)
    session.close()
