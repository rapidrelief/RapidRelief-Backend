from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import SessionLocal, engine
from app.db.models import SOSRequest, ZoneState, SystemEvent, Zone, Device, ZoneNode
import time

router = APIRouter(prefix="/api/sos", tags=["sos"])

USER_SOS_SOURCES = {"USER", "AUTO"}
QUORUM_THRESHOLD = 10
HISTORY_RETENTION_SECONDS = 10 * 24 * 60 * 60

_schema_ready = False


def ensure_sos_schema():
    global _schema_ready

    if _schema_ready:
        return

    required_columns = {
        "user_id": "VARCHAR",
        "user_name": "VARCHAR",
        "user_phone": "VARCHAR",
        "source": "VARCHAR DEFAULT 'RESCUER'",
        "lat": "FLOAT",
        "lng": "FLOAT",
        "location_updated_at": "FLOAT",
        "is_live_location": "BOOLEAN DEFAULT 0",
        "completed_at": "FLOAT",
        "completed_by": "VARCHAR",
        "completed_by_name": "VARCHAR",
        "details": "JSON",
    }

    with engine.begin() as conn:
        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(sos_requests)")).fetchall()
        }

        for column, definition in required_columns.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE sos_requests ADD COLUMN {column} {definition}"))

    _schema_ready = True


def serialize_sos(sos: SOSRequest):
    return {
        "id": sos.id,
        "zone_id": sos.zone_id,
        "user_id": sos.user_id,
        "user_name": sos.user_name,
        "user_phone": sos.user_phone,
        "rescuer_id": sos.rescuer_id,
        "rescuer_name": sos.rescuer_name,
        "source": sos.source or "RESCUER",
        "lat": sos.lat,
        "lng": sos.lng,
        "location_updated_at": sos.location_updated_at,
        "is_live_location": bool(sos.is_live_location),
        "created_at": sos.created_at,
        "completed_at": sos.completed_at,
        "completed_by": sos.completed_by,
        "completed_by_name": sos.completed_by_name,
        "details": sos.details,
        "status": sos.status,
    }


def get_latest_state_event(db, zone_id: int, state: str):
    return (
        db.query(SystemEvent)
        .filter(SystemEvent.event_type == f"SYSTEM_{state}")
        .order_by(SystemEvent.timestamp.desc())
        .all()
    )


def get_latest_zone_state_time(db, zone_id: int, state: str, fallback: float):
    events = get_latest_state_event(db, zone_id, state)
    for event in events:
        details = event.details or {}
        if details.get("zone") == zone_id:
            return event.timestamp
    return fallback


def build_zone_alert_snapshot(db, zone: Zone, zone_state: ZoneState, state: str):
    now = time.time()
    gateways = db.query(Device).filter(Device.zone_id == zone.id).all()
    nodes = db.query(ZoneNode).filter(ZoneNode.zone_id == zone.id).all()

    total_devices = len(gateways) + len(nodes)
    active_devices = zone_state.active_devices or 0
    lost_devices = zone_state.lost_devices or 0

    field = "sos" if state == "SOS" else "flood"
    reporting_gateways = [
        g.device_id
        for g in gateways
        if getattr(g, field, False)
    ]
    reporting_nodes = [
        n.node_id
        for n in nodes
        if getattr(n, field, False)
    ]

    created_at = get_latest_zone_state_time(
        db,
        zone.id,
        state,
        zone_state.updated_at or now
    )

    source = "ZONE_SOS" if state == "SOS" else "ZONE_FLOOD"
    title = f"Zone state changed to {state}"

    return {
        "id": f"{source.lower()}-{zone.id}",
        "zone_alert": True,
        "zone_id": zone.id,
        "zone_name": zone.name,
        "source": source,
        "state": state,
        "title": title,
        "user_name": title,
        "created_at": created_at,
        "completed_at": None,
        "status": "ACTIVE",
        "total_devices": total_devices,
        "active_devices": active_devices,
        "lost_devices": lost_devices,
        "reporting_devices_count": len(reporting_gateways) + len(reporting_nodes),
        "reporting_gateways": reporting_gateways,
        "reporting_nodes": reporting_nodes,
        "details": {
            "zone_name": zone.name,
            "state": state,
            "total_devices": total_devices,
            "active_devices": active_devices,
            "lost_devices": lost_devices,
            "reporting_devices_count": len(reporting_gateways) + len(reporting_nodes),
            "reporting_gateways": reporting_gateways,
            "reporting_nodes": reporting_nodes,
        },
    }


def get_active_zone_alerts(db):
    alerts = []
    states = (
        db.query(ZoneState)
        .filter(ZoneState.state.in_(["SOS", "FLOOD"]))
        .all()
    )

    for zone_state in states:
        zone = db.get(Zone, zone_state.zone_id)
        if not zone:
            continue

        snapshot = build_zone_alert_snapshot(db, zone, zone_state, zone_state.state)

        if zone_state.state == "SOS" and snapshot["reporting_devices_count"] == 0:
            continue

        alerts.append(snapshot)

    return alerts


def active_user_sos_count(db, zone_id: int):
    if not zone_id:
        return 0

    rows = (
        db.query(SOSRequest)
        .filter(SOSRequest.zone_id == zone_id)
        .filter(SOSRequest.status == "ACTIVE")
        .filter(SOSRequest.source.in_(USER_SOS_SOURCES))
        .all()
    )

    unique_users = {
        s.user_id or f"request-{s.id}"
        for s in rows
    }

    return len(unique_users)


def force_zone_sos(db, zone_id: int, reason: str):
    if not zone_id:
        return

    now = time.time()
    zone = db.get(ZoneState, zone_id)

    if not zone:
        zone = ZoneState(
            zone_id=zone_id,
            state="SOS",
            updated_at=now,
            active_devices=0,
            lost_devices=0,
            confidence=100.0,
        )
        db.add(zone)
    else:
        zone.state = "SOS"
        zone.updated_at = now
        zone.confidence = 100.0

    db.add(SystemEvent(
        event_type="SYSTEM_SOS",
        device_id=None,
        timestamp=now,
        details={"zone": zone_id, "reason": reason}
    ))


def release_zone_sos_if_allowed(db, zone_id: int):
    if not zone_id:
        return

    active_rescuer_sos = (
        db.query(SOSRequest)
        .filter(SOSRequest.zone_id == zone_id)
        .filter(SOSRequest.status == "ACTIVE")
        .filter(SOSRequest.source == "RESCUER")
        .count()
    )

    if active_rescuer_sos > 0 or active_user_sos_count(db, zone_id) >= QUORUM_THRESHOLD:
        return

    zone = db.get(ZoneState, zone_id)
    if zone and zone.state == "SOS":
        zone.state = None
        zone.updated_at = time.time()


def cleanup_old_history(db):
    now = time.time()
    
    # 10 days retention for regular SOS
    sos_cutoff = now - (10 * 24 * 60 * 60)
    
    # 10 days retention for flood history
    flood_cutoff = now - (10 * 24 * 60 * 60)
    
    # Clean up old regular SOS
    old_sos = (
        db.query(SOSRequest)
        .filter(SOSRequest.status == "COMPLETED")
        .filter(SOSRequest.source != "ZONE_FLOOD")
        .filter(SOSRequest.completed_at.isnot(None))
        .filter(SOSRequest.completed_at < sos_cutoff)
        .all()
    )
    for item in old_sos:
        db.delete(item)
        
    # Clean up old flood alerts
    old_floods = (
        db.query(SOSRequest)
        .filter(SOSRequest.status == "COMPLETED")
        .filter(SOSRequest.source == "ZONE_FLOOD")
        .filter(SOSRequest.completed_at.isnot(None))
        .filter(SOSRequest.completed_at < flood_cutoff)
        .all()
    )
    for item in old_floods:
        db.delete(item)


@router.post("/create")
def create_sos(data: dict):
    ensure_sos_schema()
    db = SessionLocal()
    now = time.time()

    source = str(data.get("source") or "RESCUER").upper()
    if source not in {"USER", "AUTO", "RESCUER", "ZONE_SOS", "ZONE_FLOOD"}:
        source = "USER"

    zone_id = data.get("zone_id")
    user_id = data.get("user_id")

    existing = None
    if source in USER_SOS_SOURCES and user_id:
        existing = (
            db.query(SOSRequest)
            .filter(SOSRequest.user_id == user_id)
            .filter(SOSRequest.status == "ACTIVE")
            .filter(SOSRequest.source.in_(USER_SOS_SOURCES))
            .first()
        )

    if existing:
        existing.zone_id = zone_id
        existing.user_name = data.get("user_name") or existing.user_name
        existing.user_phone = data.get("user_phone") or existing.user_phone
        existing.source = source
        existing.lat = data.get("lat")
        existing.lng = data.get("lng")
        existing.location_updated_at = data.get("location_updated_at") or now
        existing.is_live_location = bool(data.get("is_live_location", True))
        sos = existing
    else:
        sos = SOSRequest(
            zone_id=zone_id,
            user_id=user_id,
            user_name=data.get("user_name"),
            user_phone=data.get("user_phone"),
            rescuer_id=data.get("rescuer_id"),
            rescuer_name=data.get("rescuer_name"),
            source=source,
            lat=data.get("lat"),
            lng=data.get("lng"),
            location_updated_at=data.get("location_updated_at") or now,
            is_live_location=bool(data.get("is_live_location", source in USER_SOS_SOURCES)),
            status="ACTIVE",
            created_at=now,
            details=data.get("details")
        )
        db.add(sos)

    if source == "RESCUER":
        force_zone_sos(db, zone_id, "rescuer")

    db.flush()

    quorum_count = active_user_sos_count(db, zone_id)
    if source in USER_SOS_SOURCES and quorum_count >= QUORUM_THRESHOLD:
        force_zone_sos(db, zone_id, "user_quorum")

    db.commit()

    result = serialize_sos(sos)
    result["quorum_count"] = quorum_count
    result["quorum_threshold"] = QUORUM_THRESHOLD

    db.close()
    return {"message": "SOS Created", "sos": result}


@router.get("/active")
def get_active_sos():
    ensure_sos_schema()
    db = SessionLocal()

    sos_list = (
        db.query(SOSRequest)
        .filter(SOSRequest.status == "ACTIVE")
        .order_by(SOSRequest.created_at.desc())
        .all()
    )

    result = [serialize_sos(s) for s in sos_list]
    result.extend(get_active_zone_alerts(db))
    db.close()
    return {"sos": result}


@router.post("/zone/{zone_id}/clear")
def clear_zone_sos(zone_id: int, data: dict = None):
    ensure_sos_schema()
    db = SessionLocal()
    now = time.time()

    zone = db.get(Zone, zone_id)
    zone_state = db.get(ZoneState, zone_id)

    if not zone or not zone_state:
        db.close()
        return {"error": "Zone not found"}

    snapshot = build_zone_alert_snapshot(db, zone, zone_state, "SOS")

    gateways = db.query(Device).filter(Device.zone_id == zone_id).all()
    nodes = db.query(ZoneNode).filter(ZoneNode.zone_id == zone_id).all()

    for gateway in gateways:
        gateway.sos = False

    for node in nodes:
        node.sos = False

    completed_by = (data or {}).get("completed_by")
    completed_by_name = (data or {}).get("completed_by_name")

    # Mark all active SOS requests in this zone as COMPLETED
    active_requests = (
        db.query(SOSRequest)
        .filter(SOSRequest.zone_id == zone_id)
        .filter(SOSRequest.status == "ACTIVE")
        .all()
    )
    for req in active_requests:
        req.status = "COMPLETED"
        req.completed_at = now
        req.completed_by = completed_by
        req.completed_by_name = completed_by_name

    db.add(SOSRequest(
        zone_id=zone_id,
        user_name="Zone state changed to SOS",
        source="ZONE_SOS",
        status="COMPLETED",
        created_at=snapshot.get("created_at") or now,
        completed_at=now,
        completed_by=completed_by,
        completed_by_name=completed_by_name,
        details=snapshot.get("details")
    ))

    db.add(SystemEvent(
        event_type="ZONE_SOS_CLEARED",
        device_id=None,
        timestamp=now,
        details={
            "zone": zone_id,
            "completed_by": completed_by,
            "completed_by_name": completed_by_name,
            "snapshot": snapshot.get("details")
        }
    ))

    db.commit()

    from app.core.rules import evaluate_system
    system_status = evaluate_system(zone_id, db)

    db.commit()
    db.close()

    return {
        "message": "Zone SOS cleared",
        "system_status": system_status
    }


@router.get("/history")
def get_sos_history():
    ensure_sos_schema()
    db = SessionLocal()
    cleanup_old_history(db)

    cutoff = time.time() - HISTORY_RETENTION_SECONDS
    sos_list = (
        db.query(SOSRequest)
        .filter(SOSRequest.status == "COMPLETED")
        .filter(SOSRequest.completed_at >= cutoff)
        .order_by(SOSRequest.completed_at.desc())
        .all()
    )

    result = [serialize_sos(s) for s in sos_list]
    db.commit()
    db.close()
    return {"sos": result}


@router.get("/history/user/{user_id}")
def get_user_sos_history(user_id: str):
    ensure_sos_schema()
    db = SessionLocal()
    cleanup_old_history(db)

    cutoff = time.time() - HISTORY_RETENTION_SECONDS
    sos_list = (
        db.query(SOSRequest)
        .filter(SOSRequest.user_id == user_id)
        .filter(SOSRequest.completed_at >= cutoff)
        .order_by(SOSRequest.completed_at.desc())
        .all()
    )

    result = [serialize_sos(s) for s in sos_list]
    db.commit()
    db.close()
    return {"sos": result}


@router.post("/history/user/{user_id}/clear")
def clear_user_sos_history(user_id: str):
    ensure_sos_schema()
    db = SessionLocal()
    
    db.query(SOSRequest).filter(
        SOSRequest.user_id == user_id,
        SOSRequest.status == "COMPLETED"
    ).delete(synchronize_session=False)
    
    db.commit()
    db.close()
    return {"message": "User SOS history cleared"}


@router.post("/complete/{sos_id}")
def complete_sos(sos_id: int, data: dict = None):
    ensure_sos_schema()
    db = SessionLocal()
    now = time.time()

    sos = db.get(SOSRequest, sos_id)

    if not sos:
        db.close()
        return {"error": "Not found"}

    sos.status = "COMPLETED"
    sos.completed_at = now

    if data:
        sos.completed_by = data.get("completed_by")
        sos.completed_by_name = data.get("completed_by_name")

    release_zone_sos_if_allowed(db, sos.zone_id)
    if sos.zone_id:
        from app.core.rules import evaluate_system
        evaluate_system(sos.zone_id, db)

    db.commit()
    db.close()

    return {"message": "SOS Completed"}
