import sqlite3
import requests

conn = sqlite3.connect('rapidrelief.db')
uid = conn.execute("SELECT firebase_uid FROM users WHERE role='ORG_ADMIN' ORDER BY id DESC LIMIT 1").fetchone()[0]
print('UID:', uid)

urls = [
    f'http://localhost:8000/org_admin/rescuers?firebase_uid={uid}',
    f'http://localhost:8000/org_admin/zones?firebase_uid={uid}',
    f'http://localhost:8000/org_admin/devices?firebase_uid={uid}',
    f'http://localhost:8000/org_admin/global_zones?firebase_uid={uid}',
    f'http://localhost:8000/org_admin/global_devices?firebase_uid={uid}'
]

for url in urls:
    res = requests.get(url)
    print(f"URL: {url.split('?')[0]}")
    print(f"Status: {res.status_code}")
    if res.status_code != 200:
        print(f"Error: {res.text}")
    else:
        print(f"Data: {len(res.json())} items")
        if len(res.json()) > 0 and isinstance(res.json(), list):
            print(f"Sample: {res.json()[0]}")
    print("---")
