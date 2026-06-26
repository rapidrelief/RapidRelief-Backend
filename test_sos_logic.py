import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

# Initialize firebase
cred_path = os.path.join(os.path.dirname(__file__), "app", "firebase", "firebase_service_account.json")
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

docs = db.collection("sos_requests").where("status", "in", ["Active", "ACTIVE"]).stream()
result = []
for doc in docs:
    data = doc.to_dict()
    z_id_raw = data.get("zone_id")
    try:
        z_id = int(str(z_id_raw)) if z_id_raw is not None else None
    except ValueError:
        z_id = None

    org_zone_ids = [1, 2, 3] # mock
    print(f"Doc {doc.id} z_id={z_id}")
    if z_id is None or z_id in org_zone_ids:
        result.append(doc.id)

print(result)
