import requests
import sqlite3

BASE_URL = "https://rapidrelief-backend-wnf8.onrender.com"
FIREBASE_UID = "40TkRfBsLFdyepMDIlmkxbd5vKp1"

def inject():
    conn = sqlite3.connect('rapidrelief.db')
    conn.row_factory = sqlite3.Row
    
    devices = conn.execute('SELECT * FROM devices').fetchall()
    for d in devices:
        payload = {
            "device_id": int(d['device_id']),
            "api_key": d['api_key'],
            "zone_id": int(d['zone_id'])
        }
        res = requests.post(f"{BASE_URL}/org_admin/device?firebase_uid={FIREBASE_UID}", json=payload)
        print(f"Device {d['device_id']}: {res.status_code} {res.text}")
        
    nodes = conn.execute('SELECT * FROM zone_nodes').fetchall()
    for n in nodes:
        payload = {
            "node_id": int(n['node_id']),
            "gateway_id": int(n['gateway_id'])
        }
        res = requests.post(f"{BASE_URL}/org_admin/node?firebase_uid={FIREBASE_UID}", json=payload)
        print(f"Node {n['node_id']}: {res.status_code} {res.text}")

if __name__ == '__main__':
    inject()
