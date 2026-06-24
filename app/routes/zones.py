from fastapi import APIRouter, HTTPException
from app.core.rules import evaluate_system
from app.db.session import SessionLocal
from app.db.models import Zone, ZoneState, Device, ZoneNode, SystemEvent, SOSRequest
from app.models.schemas import ZoneCreate

router = APIRouter(prefix="/api", tags=["zones"])

def get_device_status(last_seen, is_lost):
    if last_seen is None:
        return "NOT_ASSIGNED"
    if is_lost:
        return "LOST"
    return "ONLINE"

@router.post ("/zones")
def create_zone(zone: ZoneCreate):

    db = SessionLocal()
    
    z = Zone(**zone.dict())
    
    db.add(z)
    db.commit()
    db.refresh(z)
    
    db.close()
    return z

@router.get("/zones")
def get_zones():
    db = SessionLocal()

    zones = db.query(Zone).all()
    result = []

    for z in zones:
        result.append({
            "id": z.id,
            "name": z.name,
            "lat": z.lat,
            "lng": z.lng,
            "radius_m": z.radius_m,
            "priority": z.priority
        })

    db.close()
    return {"zones": result}

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
        gateways = db.query(Device).filter(Device.zone_id == z.id).all()
        nodes = db.query(ZoneNode).filter(ZoneNode.zone_id == z.id).all()
        total_devices = len(gateways) + len(nodes)
        unassigned_devices = len([g for g in gateways if g.last_seen is None])
        unassigned_devices += len([n for n in nodes if n.last_seen is None])
        computed_lost_devices = len([
            g for g in gateways
            if get_device_status(g.last_seen, g.is_lost) == "LOST"
        ])
        computed_lost_devices += len([
            n for n in nodes
            if get_device_status(n.last_seen, n.is_lost) == "LOST"
        ])

        if zs:
            state = zs.state
            active_devices = zs.active_devices
            lost_devices = zs.lost_devices
            confidence = zs.confidence
        else:
            state = "UNKNOWN"
            active_devices = 0
            lost_devices = 0
            confidence = 0

        display_lost_devices = max(lost_devices or 0, computed_lost_devices)

        response.append({
            "id": z.id,
            "name": z.name,
            "lat": z.lat,
            "lng": z.lng,
            "radius_m": z.radius_m,
            "priority": z.priority,
            "state": state,
            "total_devices": total_devices,
            "devices": total_devices,
            "active_devices": active_devices,
            "lost_devices": display_lost_devices,
            "lostDevices": display_lost_devices,
            "unassigned_devices": unassigned_devices,
            "confidence": confidence
        })

    db.close()

    return {"zones": response}

@router.get("/zones/{zone_id}/deployment")
def get_zone_deployment(zone_id: int):
    db = SessionLocal()

    zone = db.get(Zone, zone_id)
    if not zone:
        db.close()
        raise HTTPException(404, "Zone not found")

    gateways = db.query(Device).filter(Device.zone_id == zone_id).all()
    nodes = db.query(ZoneNode).filter(ZoneNode.zone_id == zone_id).all()

    result = {
        "zone": {
            "id": zone.id,
            "name": zone.name,
            "lat": zone.lat,
            "lng": zone.lng,
            "radius_m": zone.radius_m,
            "priority": zone.priority
        },
        "gateways": [
            {
                "device_id": g.device_id,
                "last_seen": g.last_seen,
                "flood": g.flood,
                "sos": g.sos,
                "is_lost": g.is_lost,
                "status": get_device_status(g.last_seen, g.is_lost),
                "lost_since": g.lost_since,
                "reconnected_after": g.reconnected_after,
                "zone_id": g.zone_id
            }
            for g in gateways
        ],
        "nodes": [
            {
                "node_id": n.node_id,
                "gateway_id": n.gateway_id,
                "zone_id": n.zone_id,
                "flood": n.flood,
                "sos": n.sos,
                "last_seen": n.last_seen,
                "is_lost": n.is_lost,
                "status": get_device_status(n.last_seen, n.is_lost),
                "encrypted": n.encrypted
            }
            for n in nodes
        ]
    }

    db.close()
    return result

@router.get("/zones/{zone_id}/logs")
def get_zone_logs(zone_id: int):
    db = SessionLocal()

    zone = db.get(Zone, zone_id)
    if not zone:
        db.close()
        raise HTTPException(404, "Zone not found")

    events = (
        db.query(SystemEvent)
        .order_by(SystemEvent.timestamp.desc())
        .limit(100)
        .all()
    )

    zone_events = []
    for e in events:
        details = e.details or {}
        if details.get("zone") == zone_id:
            zone_events.append({
                "id": e.id,
                "type": e.event_type,
                "device_id": e.device_id,
                "timestamp": e.timestamp,
                "details": details
            })

    sos_requests = (
        db.query(SOSRequest)
        .filter(SOSRequest.zone_id == zone_id)
        .order_by(SOSRequest.created_at.desc())
        .limit(50)
        .all()
    )

    sos_logs = [
        {
            "id": s.id,
            "type": "SOS_REQUEST",
            "zone_id": s.zone_id,
            "rescuer_id": s.rescuer_id,
            "rescuer_name": s.rescuer_name,
            "status": s.status,
            "timestamp": s.created_at
        }
        for s in sos_requests
    ]

    db.close()
    return {"zone_id": zone_id, "events": zone_events, "sos": sos_logs}

@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: int):
    db = SessionLocal()
    zone = db.get(Zone, zone_id)
    if not zone:
        db.close()
        raise HTTPException(404, "Zone not found")

    db.query(Device).filter(Device.zone_id == zone_id).delete()
    db.query(ZoneNode).filter(ZoneNode.zone_id == zone_id).delete()
    db.query(ZoneState).filter(ZoneState.zone_id == zone_id).delete()
    db.query(SOSRequest).filter(SOSRequest.zone_id == zone_id).delete()

    db.delete(zone)
    db.commit()
    db.close()
    return {"message": "Zone deleted successfully", "zone_id": zone_id}
