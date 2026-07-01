from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Zone, Device, User
from pydantic import BaseModel
from typing import List
import time
from app.db.models import ZoneNode
from sqlalchemy import text
from app.db.session import engine

router = APIRouter(prefix="/org_admin", tags=["org_admin_infrastructure"])

_user_schema_ready = False
def ensure_user_schema():
    global _user_schema_ready
    if _user_schema_ready: return
    try:
        with engine.begin() as conn:
            existing = {row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
            for col, dtype in {"lat": "FLOAT", "lng": "FLOAT", "location_updated_at": "FLOAT"}.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {dtype}"))
    except Exception as e:
        print("Schema update error:", e)
    _user_schema_ready = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class OrgZoneCreate(BaseModel):
    name: str
    lat: float
    lng: float
    radius_m: float
    priority: str

class OrgDeviceCreate(BaseModel):
    device_id: int
    api_key: str
    zone_id: int

class OrgNodeCreate(BaseModel):
    node_id: int
    gateway_id: int

def get_zone_stats(zone_id: int, db_session: Session):
    gateways = db_session.query(Device).filter(Device.zone_id == zone_id).all()
    nodes = db_session.query(ZoneNode).filter(ZoneNode.zone_id == zone_id).all()
    
    total_gateways = len(gateways)
    total_nodes = len(nodes)
    total_devices = total_gateways + total_nodes
    
    communicating_devices = sum(1 for g in gateways if g.last_seen is not None) + sum(1 for n in nodes if n.last_seen is not None)
    
    active_gateways = sum(1 for g in gateways if not g.is_lost and g.last_seen is not None)
    active_nodes = sum(1 for n in nodes if not n.is_lost and n.last_seen is not None)
    active_devices = active_gateways + active_nodes
    
    has_sos = any(g.sos for g in gateways) or any(n.sos for n in nodes)
    has_flood = any(g.flood for g in gateways) or any(n.flood for n in nodes)
    
    if total_devices == 0 or communicating_devices == 0:
        signal_state = "nosignal"
    elif has_sos:
        signal_state = "sos"
    elif has_flood:
        signal_state = "flood"
    elif active_devices == 0:
        signal_state = "lost"
    else:
        signal_state = "online"
        
    return {
        "total_devices": total_devices,
        "total_gateways": total_gateways,
        "total_nodes": total_nodes,
        "active_devices": active_devices,
        "signal_state": signal_state
    }

@router.get("/zones")
def get_org_zones(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    zones = db_session.query(Zone).filter(Zone.organization_id == caller.organization_id).all()
    result = []
    for z in zones:
        result.append({
            "id": z.id,
            "name": z.name,
            "lat": z.lat,
            "lng": z.lng,
            "radius_m": z.radius_m,
            "priority": z.priority,
            "stats": get_zone_stats(z.id, db_session)
        })
    return result

@router.post("/zone")
def create_org_zone(firebase_uid: str, req: OrgZoneCreate, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    z = Zone(
        name=req.name,
        lat=req.lat,
        lng=req.lng,
        radius_m=req.radius_m,
        priority=req.priority,
        organization_id=caller.organization_id
    )
    db_session.add(z)
    db_session.commit()
    db_session.refresh(z)
    return {"status": "success", "zone_id": z.id}

@router.get("/devices")
def get_org_devices(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    devices = db_session.query(Device).filter(Device.organization_id == caller.organization_id).all()
    result = []
    for d in devices:
        result.append({
            "device_id": d.device_id,
            "api_key": d.api_key,
            "last_seen": d.last_seen,
            "zone_id": d.zone_id,
            "is_lost": d.is_lost,
            "flood": d.flood,
            "sos": d.sos
        })
    return result

@router.post("/device")
def create_org_device(firebase_uid: str, req: OrgDeviceCreate, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Verify zone belongs to org or is global
    zone = db_session.query(Zone).filter(Zone.id == req.zone_id).first()
    if not zone or (zone.organization_id is not None and zone.organization_id != caller.organization_id):
        raise HTTPException(status_code=404, detail="Zone not found or access denied")

    # Check if device_id is already taken
    existing_device = db_session.query(Device).filter(Device.device_id == req.device_id).first()
    if existing_device:
        raise HTTPException(status_code=400, detail="Gateway ID already exists")

    d = Device(
        device_id=req.device_id,
        api_key=req.api_key,
        zone_id=req.zone_id,
        organization_id=caller.organization_id
    )
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return {"status": "success", "device_id": d.device_id}

@router.get("/nodes")
def get_org_nodes(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    nodes = db_session.query(ZoneNode).filter(ZoneNode.organization_id == caller.organization_id).all()
    result = []
    for n in nodes:
        result.append({
            "node_id": n.node_id,
            "gateway_id": n.gateway_id,
            "zone_id": n.zone_id,
            "is_lost": n.is_lost,
            "last_seen": n.last_seen,
            "flood": n.flood,
            "sos": n.sos,
            "encrypted": n.encrypted
        })
    return result

@router.post("/node")
def create_org_node(firebase_uid: str, req: OrgNodeCreate, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Verify gateway belongs to org
    gateway = db_session.query(Device).filter(Device.device_id == req.gateway_id).first()
    if not gateway or (gateway.organization_id is not None and gateway.organization_id != caller.organization_id):
        raise HTTPException(status_code=404, detail="Gateway not found or access denied")

    # Check if node_id is already taken
    existing_node = db_session.query(ZoneNode).filter(ZoneNode.node_id == req.node_id).first()
    if existing_node:
        raise HTTPException(status_code=400, detail="Node ID already exists")

    n = ZoneNode(
        node_id=req.node_id,
        gateway_id=req.gateway_id,
        zone_id=gateway.zone_id,
        organization_id=caller.organization_id,
        encrypted=True
    )
    db_session.add(n)
    db_session.commit()
    db_session.refresh(n)
    return {"status": "success", "node_id": n.node_id}

@router.get("/global_zones")
def get_global_zones(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or (caller.role != "ORG_ADMIN" and not caller.is_super_admin):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    zones = db_session.query(Zone).all()
    result = []
    for z in zones:
        org_name = "Legacy / Unassigned"
        if z.organization_id:
            from app.db.models import Organization
            org = db_session.query(Organization).filter(Organization.id == z.organization_id).first()
            if org:
                org_name = org.name
        
        result.append({
            "id": z.id,
            "name": z.name,
            "lat": z.lat,
            "lng": z.lng,
            "radius_m": z.radius_m,
            "priority": z.priority,
            "organization_id": z.organization_id,
            "organization_name": org_name,
            "stats": get_zone_stats(z.id, db_session)
        })
    return result

@router.get("/global_devices")
def get_global_devices(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    devices = db_session.query(Device).all()
    result = []
    for d in devices:
        org_name = "Legacy / Unassigned"
        if d.organization_id:
            from app.db.models import Organization
            org = db_session.query(Organization).filter(Organization.id == d.organization_id).first()
            if org:
                org_name = org.name

        result.append({
            "device_id": d.device_id,
            "api_key": d.api_key,
            "last_seen": d.last_seen,
            "zone_id": d.zone_id,
            "is_lost": d.is_lost,
            "flood": d.flood,
            "sos": d.sos,
            "organization_name": org_name,
            "organization_id": d.organization_id
        })
    return result

@router.get("/active_sos")
def get_org_active_sos(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    org_zones = db_session.query(Zone.id).filter(Zone.organization_id == caller.organization_id).all()
    global_zones = db_session.query(Zone.id).filter(Zone.organization_id == None).all()
    
    # Org admins can see SOS from their own zones AND unassigned/global zones
    visible_zone_ids = [z[0] for z in org_zones] + [z[0] for z in global_zones]
    
    if not visible_zone_ids:
        return []

    result = []
    
    # Fetch from SQLite
    from app.db.models import SOSRequest
    active_sos = db_session.query(SOSRequest).filter(
        SOSRequest.status == "Active",
        SOSRequest.zone_id.in_(visible_zone_ids)
    ).all()
    
    for sos in active_sos:
        result.append({
            "id": str(sos.id),
            "zone_id": sos.zone_id,
            "user_name": sos.user_name,
            "user_phone": sos.user_phone,
            "rescuer_name": sos.rescuer_name,
            "source": sos.source,
            "lat": sos.lat,
            "lng": sos.lng,
            "created_at": sos.created_at,
            "details": sos.details
        })
        
    # Fetch from Firestore
    try:
        from app.firebase.firebase import db
        # Handle both 'Active' and 'ACTIVE' cases that might exist in Firestore
        docs = db.collection("sos_requests").where("status", "in", ["Active", "ACTIVE"]).stream()
        for doc in docs:
            data = doc.to_dict()
            z_id_raw = data.get("zone_id")
            
            try:
                z_id = int(str(z_id_raw)) if z_id_raw is not None else None
            except ValueError:
                z_id = None
                
            # Include SOS if it's in their zone OR if it's completely unassigned (z_id is None)
            if z_id is None or z_id in visible_zone_ids:
                # Avoid duplicates if it's already in SQLite
                if not any(r["id"] == str(doc.id) for r in result):
                    result.append({
                        "id": str(doc.id),
                        "zone_id": z_id,
                        "user_name": data.get("user_name", data.get("fullName", "Unknown User")),
                        "user_phone": data.get("user_phone", data.get("phone", "")),
                        "rescuer_name": data.get("rescuer_name", ""),
                        "source": data.get("source", "USER"),
                        "lat": data.get("lat", data.get("location", {}).get("lat", 0.0)),
                        "lng": data.get("lng", data.get("location", {}).get("lng", 0.0)),
                        "created_at": data.get("created_at", data.get("timestamp")),
                        "details": data.get("details", {})
                    })
    except Exception as e:
        print(f"Error fetching active sos from firestore: {e}")
        
    return result

@router.get("/active_floods")
def get_org_active_floods(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    org_zones = db_session.query(Zone).filter(Zone.organization_id == caller.organization_id).all()
    
    result = []
    for z in org_zones:
        stats = get_zone_stats(z.id, db_session)
        if stats["signal_state"] == "flood":
            result.append({
                "zone_id": z.id,
                "zone_name": z.name,
                "lat": z.lat,
                "lng": z.lng,
                "active_devices": stats["active_devices"]
            })
            
    # Include Simulated Floods
    from app.db.models import SOSRequest
    simulated_floods = db_session.query(SOSRequest).filter(
        SOSRequest.status == "Active",
        SOSRequest.source == "ZONE_FLOOD",
        SOSRequest.zone_id.in_([z.id for z in org_zones])
    ).all()
    
    for f in simulated_floods:
        if not any(r["zone_id"] == f.zone_id for r in result):
            z_match = next((z for z in org_zones if z.id == f.zone_id), None)
            result.append({
                "zone_id": f.zone_id,
                "zone_name": z_match.name if z_match else f"Zone {f.zone_id}",
                "lat": f.lat,
                "lng": f.lng,
                "active_devices": "Simulated"
            })
            
    return result


@router.delete("/zone/{zone_id}")
def delete_org_zone(zone_id: int, firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    zone = db_session.query(Zone).filter(Zone.id == zone_id, Zone.organization_id == caller.organization_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
        
    db_session.query(Device).filter(Device.zone_id == zone_id).delete()
    db_session.query(ZoneNode).filter(ZoneNode.zone_id == zone_id).delete()
    db_session.delete(zone)
    db_session.commit()
    return {"status": "success"}

@router.delete("/device/{device_id}")
def delete_org_device(device_id: int, firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    device = db_session.query(Device).filter(Device.device_id == device_id, Device.organization_id == caller.organization_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    db_session.query(ZoneNode).filter(ZoneNode.gateway_id == device_id).delete()
    db_session.delete(device)
    db_session.commit()
    return {"status": "success"}

@router.delete("/node/{node_id}")
def delete_org_node(node_id: int, firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    node = db_session.query(ZoneNode).filter(ZoneNode.node_id == node_id, ZoneNode.organization_id == caller.organization_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
        
    db_session.delete(node)
    db_session.commit()
    return {"status": "success"}
