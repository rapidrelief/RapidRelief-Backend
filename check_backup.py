import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.firebase.firebase import db

docs = list(db.collection('backup_users').stream())
for d in docs:
    print(d.to_dict())
