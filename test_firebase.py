import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.config import backend_path, settings

cred = credentials.Certificate(str(backend_path(settings.firebase_service_account_path)))
firebase_admin.initialize_app(cred)
db = firestore.client()
try:
    project_id = cred.project_id
    print('Project ID:', project_id)
    app2 = firebase_admin.initialize_app(cred, {'storageBucket': f'{project_id}.appspot.com'}, name='storage_app')
    bucket = storage.bucket(app=app2)
    print('Bucket created successfully:', bucket.name)
except Exception as e:
    print('Error:', e)
