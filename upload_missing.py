import os
import sys
import sqlite3

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.firebase.firebase import db

def upload():
    conn = sqlite3.connect('rapidrelief.db')
    conn.row_factory = sqlite3.Row
    
    devices = conn.execute('SELECT * FROM devices').fetchall()
    for d in devices:
        doc_id = str(d['device_id'])
        db.collection('backup_devices').document(doc_id).set(dict(d))
        print(f"Uploaded device {doc_id}")
        
    nodes = conn.execute('SELECT * FROM zone_nodes').fetchall()
    for n in nodes:
        doc_id = str(n['node_id'])
        db.collection('backup_nodes').document(doc_id).set(dict(n))
        print(f"Uploaded node {doc_id}")
        
    sos = conn.execute('SELECT * FROM sos_requests').fetchall()
    for s in sos:
        doc_id = f"request-{s['id']}"
        db.collection('backup_sos').document(doc_id).set(dict(s))
        db.collection('sos_requests').document(doc_id).set(dict(s))
        print(f"Uploaded sos {doc_id}")

if __name__ == '__main__':
    upload()
