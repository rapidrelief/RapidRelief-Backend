import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.firebase.firebase import db

def check():
    devs = list(db.collection('backup_devices').stream())
    print(f"Firestore backup_devices count: {len(devs)}")
    nodes = list(db.collection('backup_nodes').stream())
    print(f"Firestore backup_nodes count: {len(nodes)}")

if __name__ == '__main__':
    check()
