from app.core.rules import update_heartbeat, evaluate_system
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from app.db.session import SessionLocal
from app.db.models import Device, Zone
import secrets
from fastapi import Request
from app.core.device_auth import verify_device

router = APIRouter()

# -----------------------------
# In-memory store (for now)
# -----------------------------
devices: Dict[int, dict] = {}
device_state: Dict[int, dict] = {}

# -----------------------------
# Models
# -----------------------------
class DeviceRegister(BaseModel):
    device_id: int
    type: str
    location: str
    zone_id: int


class Heartbeat(BaseModel):
    flood: bool
    sos: bool

class FloodEvent(BaseModel):
    device_id: int
    flood: bool


class SOSEvent(BaseModel):
    device_id: int
    sos: bool



# -----------------------------
# Routes
# -----------------------------

@router.post("/devices/register")
def register_device(data: DeviceRegister):

    db = SessionLocal()

    #check zone existence
    zone = db.get(Zone, data.zone_id)
    if not zone:
        db.close()
        raise HTTPException(400, "Zone does not exist. Create Zone first.")

    existing = db.get(Device, data.device_id)
    if existing:
        db.close()
        raise HTTPException(400, "Device already registered")

    api_key = secrets.token_hex(32)
    
    device = Device(
        device_id=data.device_id,
        api_key=api_key,
        last_seen=None,
        flood=False,
        sos=False,
        zone_id=data.zone_id
    )
    db.add(device)
    db.commit()
    db.close()

    return {
        "message": "Device registered successfully",
        "device_id": data.device_id,
        "api_key": api_key,
        "zone_id": data.zone_id
    }


@router.post("/devices/heartbeat")
def heartbeat(data: Heartbeat, request: Request):

    device = verify_device(request.headers)

    update_heartbeat(
        device_id=device.device_id,
        flood=data.flood,
        sos=data.sos
    )

    db = SessionLocal()
    db_device = db.get(Device, device.device_id)
    zone_id = db_device.zone_id

    system_status = evaluate_system(zone_id, db)

    db.close()

    return {
        "message": "Heartbeat Received",
        "system_status": system_status
        }


@router.get("/devices/status/{zone_id}")
def get_system_status(zone_id: int):
    db = SessionLocal()
    result = evaluate_system(zone_id, db)
    db.close()
    return result

@router.get("/devices/health")
def devices_health():
    return {"status": "Devices route working"}



@router.post("/devices/flood")
def flood_event(data: FloodEvent):
    return {"message": "Flood Event Record",
            "device_id": data.device_id,
            "flood": data.flood
    }



@router.post("/devices/sos")
def sos_event(data: SOSEvent):
    return {"message": "SOS Received",
            "device_id": data.device_id,
            "flood": data.sos
    }
