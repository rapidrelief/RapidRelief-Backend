from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Zone, Device, User
from pydantic import BaseModel
from typing import List
import time
from app.db.models import ZoneNode

router = APIRouter(prefix="/org_admin", tags=["org_admin_infrastructure"])

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
    api_key: str
    zone_id: int

def get_zone_stats(zone_id: int, db_session: Session):
    gateways = db_session.query(Device).filter(Device.zone_id == zone_id).all()
    nodes = db_session.query(ZoneNode).filter(ZoneNode.zone_id == zone_id).all()
    
    total_gateways = len(gateways)
    total_nodes = len(nodes)
    total_devices = total_gateways + total_nodes
    
    active_gateways = sum(1 for g in gateways if not g.is_lost)
    active_nodes = sum(1 for n in nodes if not n.is_lost)
    active_devices = active_gateways + active_nodes
    
    has_sos = any(g.sos for g in gateways) or any(n.sos for n in nodes)
    has_flood = any(g.flood for g in gateways) or any(n.flood for n in nodes)
    
    if total_devices == 0:
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

    d = Device(
        api_key=req.api_key,
        zone_id=req.zone_id,
        organization_id=caller.organization_id
    )
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return {"status": "success", "device_id": d.device_id}

@router.get("/global_zones")
def get_global_zones(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
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
