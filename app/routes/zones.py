from fastapi import APIRouter
from app.core.rules import evaluate_system
from app.db.session import SessionLocal
from app.db.models import Zone, ZoneState, Device
from app.models.schemas import ZoneCreate

router = APIRouter(prefix="/api", tags=["zones"])

@router.post ("/zones")
def create_zone(zone: ZoneCreate):

    db = SessionLocal()
    
    z = Zone(**zone.dict())
    
    db.add(z)
    db.commit()
    db.refresh(z)
    
    db.close()
    return z

@router.get("/zones/status")
def get_all_zone_status():
    db = SessionLocal()

    zones = db.query(ZoneState).all()

    result = []

    for z in zones:
        result.append({
            "zone_id": z.zone_id,
            "state": z.state,
            "confidence": z.confidence,
            "active_devices": z.active_devices,
            "lost_devices": z.lost_devices,
            "updated_at": z.updated_at
        })
    
    db.close()

    return {"zones": result}

@router.get("/zones/map")
def get_zones_map():
    db = SessionLocal()

    zones = db.query(Zone).all()

    response = []

    for z in zones:
       

        zs = db.query(ZoneState).filter(ZoneState.zone_id == z.id).first()

        if zs:
            state = zs.state
            active_devices = zs.active_devices
            lost_devices = zs.lost_devices
            confidence = zs.confidence
        else:
            state = "UNKNOWN"
            active_devices = 0
            lost_devices = None
            confidence = 0

        response.append({
            "id": z.id,
            "name": z.name,
            "lat": z.lat,
            "lng": z.lng,
            "radius_m": z.radius_m,
            "priority": z.priority,
            "state": state,
            "active_devices": active_devices,
            "lost_devices": lost_devices,
            "confidence": confidence
        })

    db.commit()
    db.close()

    return {"zones": response}