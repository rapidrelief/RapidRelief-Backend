import firebase_admin 
from firebase_admin import credentials, firestore, auth
from app.core.config import backend_path, settings

cred = credentials.Certificate(str(backend_path(settings.firebase_service_account_path)))

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
