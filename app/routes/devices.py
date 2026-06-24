from app.core.rules import update_heartbeat, evaluate_system
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from app.db.session import SessionLocal
from app.db.models import Device, Zone, ZoneNode, SystemEvent, SOSRequest
import time
import secrets
from fastapi import Request
from app.core.device_auth import verify_device

router = APIRouter()

def get_device_status(last_seen, is_lost):
    if last_seen is None:
        return "NOT_ASSIGNED"
    if is_lost:
        return "LOST"
    return "ONLINE"

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

class NodeUpdate(BaseModel):
    node_id: int
    flood: bool
    sos: bool

class NodeRegister(BaseModel):
    node_id: int
    gateway_id: int
    zone_id: int


class OfflineSOSReport(BaseModel):
    node_id: int
    name: str
    phone: str
    lat: float
    lng: float
    sequence: int


# -----------------------------
# Routes
# -----------------------------

@router.post("/devices/offline-sos")
def report_offline_sos(data: OfflineSOSReport, request: Request):
    gateway = verify_device(request.headers)

    db = SessionLocal()
    now = time.time()

    user_name = f"{data.name} (OFFLINE BLE via Node {data.node_id})"
    
    # Check for existing active SOS from this phone
    existing = (
        db.query(SOSRequest)
        .filter(SOSRequest.user_phone == data.phone)
        .filter(SOSRequest.status == "ACTIVE")
        .first()
    )

    if existing:
        existing.lat = data.lat
        existing.lng = data.lng
        existing.location_updated_at = now
        existing.user_name = user_name
        sos = existing
    else:
        sos = SOSRequest(
            zone_id=gateway.zone_id,
            user_name=user_name,
            user_phone=data.phone,
            source="AUTO",
            lat=data.lat,
            lng=data.lng,
            location_updated_at=now,
            is_live_location=False,
            status="ACTIVE",
            created_at=now,
            details={
                "entry_node": data.node_id,
                "sequence": data.sequence,
                "gateway_id": gateway.device_id
            }
        )
        db.add(sos)

    # Removed SYSTEM_SOS event to prevent forcing zone state

    db.commit()
    system_status = evaluate_system(gateway.zone_id, db)
    db.commit()
    db.close()

    return {
        "message": "Offline SOS Alert Relayed",
        "system_status": system_status
    }


@router.post("/devices/register")
def register_device(data: DeviceRegister):
    db = SessionLocal()

    # check zone existence
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
        is_lost=False,
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

@router.get("/devices/gateways")
def get_gateways():
    db = SessionLocal()
    gateways = db.query(Device).all()

    result = []
    for g in gateways:
        result.append({
            "device_id": g.device_id,
            "zone_id": g.zone_id,
            "last_seen": g.last_seen,
            "flood": g.flood,
            "sos": g.sos,
            "is_lost": g.is_lost,
            "status": get_device_status(g.last_seen, g.is_lost),
            "lost_since": g.lost_since,
            "reconnected_after": g.reconnected_after
        })

    db.close()
    return {"gateways": result}

@router.get("/devices/gateways/{zone_id}")
def get_zone_gateways(zone_id: int):
    db = SessionLocal()
    gateways = db.query(Device).filter(Device.zone_id == zone_id).all()

    result = []
    for g in gateways:
        result.append({
            "device_id": g.device_id,
            "zone_id": g.zone_id,
            "last_seen": g.last_seen,
            "flood": g.flood,
            "sos": g.sos,
            "is_lost": g.is_lost,
            "status": get_device_status(g.last_seen, g.is_lost),
            "lost_since": g.lost_since,
            "reconnected_after": g.reconnected_after
        })

    db.close()
    return {"gateways": result}



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

@router.post("/nodes/update")
def update_node(data: NodeUpdate, request: Request):

    gateway = verify_device(request.headers)

    db = SessionLocal()

    node = db.get(ZoneNode, data.node_id)

    if not node:
        db.close()
        raise HTTPException(400, "Node is not registered for deployment")

    if node.gateway_id != gateway.device_id or node.zone_id != gateway.zone_id:
        db.close()
        raise HTTPException(400, "Node does not belong to this gateway")

    now = time.time()
    was_lost = bool(node.is_lost)

    node.flood = data.flood

    # Physical node SOS is a push-button event; keep it active until a rescuer clears it.
    if data.sos:
        node.sos = True
    node.last_seen = now
    node.is_lost = False

    if was_lost:
        db.add(SystemEvent(
            event_type="NODE_RECONNECTED",
            device_id=node.node_id,
            timestamp=now,
            details={
                "zone": node.zone_id,
                "gateway_id": gateway.device_id
            }
        ))

    db.commit()
    system_status = evaluate_system(gateway.zone_id, db)
    db.close()

    return {
        "message": "Node Updated",
        "system_status": system_status
    }

@router.post("/nodes/register")
def register_node(data: NodeRegister):

    db = SessionLocal()

    zone = db.get(Zone, data.zone_id)
    if not zone:
        db.close()
        raise HTTPException(400, "Zone does not exist")

    gateway = db.get(Device, data.gateway_id)
    if not gateway:
        db.close()
        raise HTTPException(400, "Gateway does not exist")

    if gateway.zone_id != data.zone_id:
        db.close()
        raise HTTPException(400, "Gateway does not belong to selected zone")

    existing = db.get(ZoneNode, data.node_id)
    if existing:
        db.close()
        raise HTTPException(400, "Node already registered")

    node = ZoneNode(
        node_id=data.node_id,
        gateway_id=data.gateway_id,
        zone_id=data.zone_id,
        flood=False,
        sos=False,
        last_seen=None,
        is_lost=False,
        encrypted=True
    )

    db.add(node)
    db.commit()
    db.close()

    return {
        "message": "Node registered successfully",
        "node_id": data.node_id,
        "gateway_id": data.gateway_id,
        "zone_id": data.zone_id
    }

@router.get("/nodes/{zone_id}")
def get_nodes(zone_id: int):

    db = SessionLocal()

    nodes = db.query(ZoneNode)\
              .filter(ZoneNode.zone_id == zone_id)\
              .all()

    result = []

    for n in nodes:

        result.append({
            "node_id": n.node_id,
            "gateway_id": n.gateway_id,
            "flood": n.flood,
            "sos": n.sos,
            "is_lost": n.is_lost,
            "last_seen": n.last_seen
        })

    db.close()

    return {"nodes": result}

@router.delete("/devices/{device_id}")
def delete_device(device_id: int):
    db = SessionLocal()
    device = db.get(Device, device_id)
    if not device:
        db.close()
        raise HTTPException(404, "Gateway not found")

    zone_id = device.zone_id
    db.delete(device)
    db.commit()

    evaluate_system(zone_id, db)
    db.commit()
    db.close()

    return {"message": "Gateway deleted successfully", "device_id": device_id}

@router.delete("/nodes/{node_id}")
def delete_node(node_id: int):
    db = SessionLocal()
    node = db.get(ZoneNode, node_id)
    if not node:
        db.close()
        raise HTTPException(404, "Node not found")

    zone_id = node.zone_id
    db.delete(node)
    db.commit()

    evaluate_system(zone_id, db)
    db.commit()
    db.close()

    return {"message": "Node deleted successfully", "node_id": node_id}
