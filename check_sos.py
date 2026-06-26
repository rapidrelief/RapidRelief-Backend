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

docs = db.collection("sos_requests").stream()
output = []
for doc in docs:
    data = doc.to_dict()
    output.append({"id": doc.id, "data": data})

print(json.dumps(output, indent=2))
