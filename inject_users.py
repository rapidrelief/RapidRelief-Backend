import requests

BASE_URL = "https://rapidrelief-backend-wnf8.onrender.com"

# 1. Super Admin
super_admin_data = {
    "firebase_uid": "QsQBxeVGmDaPUghOds5chBBYUWp1",
    "email": "superadmin@rapidrelief.app",
    "role": "SUPER_ADMIN",
    "name": "Super Admin",
    "phone": "0000000000"
}
r1 = requests.post(f"{BASE_URL}/auth/register", json=super_admin_data)
print("Super Admin Register:", r1.status_code, r1.text)

# Also flag as super admin just to be safe
flag_data = {
    "firebase_uid": "QsQBxeVGmDaPUghOds5chBBYUWp1",
    "secret_key": "RAPID_RELIEF_SUPER_SECRET"
}
r2 = requests.post(f"{BASE_URL}/super_admin/flag", json=flag_data)
print("Super Admin Flag:", r2.status_code, r2.text)

# 2. Org Admin
org_admin_data = {
    "firebase_uid": "40TkRfBsLFdyepMDIlmkxbd5vKp1",
    "email": "nomanbaig176@gmail.com",
    "role": "ORG_ADMIN",
    "name": "Hassan Khan",
    "phone": "12345678901",
    "organization_id": 1
}
r3 = requests.post(f"{BASE_URL}/auth/register", json=org_admin_data)
print("Org Admin Register:", r3.status_code, r3.text)

