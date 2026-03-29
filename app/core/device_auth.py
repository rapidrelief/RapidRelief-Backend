import time
import hmac
import hashlib
from fastapi import HTTPException
from app.db.session import SessionLocal
from app.db.models import Device

REQUEST_EXPIRY_SECONDS = 180 #180 for testing #30 sec will be in production

def verify_device(headers):
    device_id = headers.get("X-Device-ID")
    timestamp = headers.get("X-Timestamp")
    signature = headers.get("X-Device-Signature")

    if not device_id or not signature or not timestamp:
        raise HTTPException(401, "Missing auth header")

    try:
        device_id = int(device_id)
        timestamp = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid auth headers")

    now = int(time.time())

    if abs(now - timestamp) > REQUEST_EXPIRY_SECONDS:
        raise HTTPException(401, "Request expired")

    db = SessionLocal()
    device = db.get(Device, device_id)
    db.close()

    if not device:
        raise HTTPException(401, "Device not Registered")

    payload = f"{device_id}:{timestamp}"

    expected_signature = hmac.new(
        device.api_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(401, "Invalid Signature")

    return device