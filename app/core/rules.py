import time
from app.db.session import SessionLocal
from app.db.models import Device, SystemEvent, ZoneState, ZoneNode, SOSRequest

HEARTBEAT_TIMEOUT = 20
FLOOD_QUORUM_PERCENT = 0.6
MIN_ACTIVE_DEVICES = 2
LOST_DEVICE_SOS_MIN_ASSIGNED = 5
LOST_DEVICE_SOS_THRESHOLD = 3
USER_SOS_QUORUM_THRESHOLD = 10

LAST_SYSTEM_STATE = {}


def has_active_rescuer_or_quorum_sos(zone_id: int, db):
    active_sos = (
        db.query(SOSRequest)
        .filter(SOSRequest.zone_id == zone_id)
        .filter(SOSRequest.status == "ACTIVE")
        .filter(SOSRequest.source.in_(["RESCUER", "ZONE_SOS"]))
        .count()
    )
    return active_sos > 0


def update_heartbeat(device_id: int, flood: bool, sos: bool):
    db = SessionLocal()
    now = time.time()

    device = db.get(Device, device_id)

    if not device:
        db.close()
        raise RuntimeError("Heartbeat from non-registered device")

    if device.is_lost:
        downtime = int(now - device.lost_since) if device.lost_since else 0

        db.add(SystemEvent(
            event_type="DEVICE_RECONNECTED",
            device_id=device.device_id,
            timestamp=now,
            details={"downtime_sec": downtime}
        ))

        device.is_lost = False
        device.lost_since = None
        device.reconnected_after = downtime
    else:
        device.reconnected_after = None

    device.last_seen = now
    device.flood = flood
    device.sos = sos

    db.commit()
    db.close()


def get_required_flood_votes(total_nodes: int) -> int:
    if total_nodes <= 2:
        return 1
    elif total_nodes == 3:
        return 2
    elif 4 <= total_nodes <= 6:
        return 3
    elif 7 <= total_nodes <= 10:
        return 5
    else:
        return max(5, int(total_nodes * 0.5))


def evaluate_system(zone_id: int, db):
    now = time.time()

    gateways = db.query(Device).filter(Device.zone_id == zone_id).all()
    nodes = db.query(ZoneNode).filter(ZoneNode.zone_id == zone_id).all()

    active = []
    lost = []
    flood_votes = 0
    node_flood_votes = 0
    active_nodes_count = 0
    sos_active = False
    reconnected = []

    reporting_units = []

    for gateway in gateways:
        db.expire(gateway)
        db.refresh(gateway)
        reporting_units.append(("gateway", gateway.device_id, gateway))

    for node in nodes:
        db.expire(node)
        db.refresh(node)
        reporting_units.append(("node", node.node_id, node))

    for unit_type, unit_id, unit in reporting_units:
        if unit.last_seen is None:
            continue

        if now - unit.last_seen > HEARTBEAT_TIMEOUT:
            if not unit.is_lost:
                unit.is_lost = True

                if hasattr(unit, "lost_since"):
                    unit.lost_since = now

                db.add(SystemEvent(
                    event_type="DEVICE_LOST" if unit_type == "gateway" else "NODE_LOST",
                    device_id=unit_id,
                    timestamp=now,
                    details={"zone": zone_id}
                ))

            lost.append(unit)
            continue

        active.append(unit)

        if unit.flood:
            flood_votes += 1
            if unit_type == "node":
                node_flood_votes += 1

        if unit.sos:
            sos_active = True

        if unit_type == "node":
            active_nodes_count += 1

        if hasattr(unit, "reconnected_after") and unit.reconnected_after:
            reconnected.append({
                "device_id": unit_id,
                "downtime_sec": unit.reconnected_after
              })

    active_count = len(active)
    lost_count = len(lost)
    assigned_total = active_count + lost_count
    total = len(gateways) + len(nodes)
    total_nodes = len(nodes)

    is_flooded = False
    if total_nodes > 0:
        required_votes = get_required_flood_votes(total_nodes)
        if node_flood_votes >= required_votes:
            is_flooded = True

    if has_active_rescuer_or_quorum_sos(zone_id, db):
        state = "SOS"
        confidence = 100.0
        sos_active = True
    elif sos_active:
        state = "SOS"
        confidence = 100.0
    elif assigned_total >= LOST_DEVICE_SOS_MIN_ASSIGNED and lost_count >= LOST_DEVICE_SOS_THRESHOLD:
        state = "SOS"
        confidence = 100.0
        sos_active = True
    elif is_flooded:
        state = "FLOOD"
        confidence = round((node_flood_votes / total_nodes) * 100, 2) if total_nodes > 0 else 100.0
    elif assigned_total == 0:
        state = "NO_SIGNAL"
        confidence = 0.0
    elif active_count == 0 and lost_count > 0:
        state = "LOST"
        confidence = 0.0
    elif active_count < MIN_ACTIVE_DEVICES:
        state = "WEAK_SIGNAL"
        confidence = 20.0
    else:
        if total_nodes > 0 and node_flood_votes > 0:
            state = "WARNING"
            confidence = round((node_flood_votes / total_nodes) * 100, 2)
        else:
            state = "SAFE"
            confidence = 0.0

    confidence = round(confidence, 2)
    prev_state = LAST_SYSTEM_STATE.get(zone_id)

    if prev_state != state:
        db.add(SystemEvent(
            event_type=f"SYSTEM_{state}",
            device_id=None,
            timestamp=now,
            details={
                "zone": zone_id,
                "from": prev_state,
                "to": state
            }
        ))

        if prev_state == "FLOOD":
            flood_start = now
            events = db.query(SystemEvent).filter(SystemEvent.event_type == "SYSTEM_FLOOD").order_by(SystemEvent.timestamp.desc()).all()
            for ev in events:
                if ev.details and ev.details.get("zone") == zone_id:
                    flood_start = ev.timestamp
                    break
            
            reporting_nodes = [n.node_id for n in nodes if n.flood]
            reporting_gateways = [g.device_id for g in gateways if g.flood]
            
            from app.db.models import Zone
            zone_obj = db.get(Zone, zone_id)
            zone_name = zone_obj.name if zone_obj else f"Zone {zone_id}"
            
            db.add(SOSRequest(
                zone_id=zone_id,
                user_name="Zone state changed to FLOOD",
                source="ZONE_FLOOD",
                status="COMPLETED",
                created_at=flood_start,
                completed_at=now,
                details={
                    "zone_name": zone_name,
                    "state": "FLOOD",
                    "total_devices": len(gateways) + len(nodes),
                    "reporting_devices_count": len(reporting_gateways) + len(reporting_nodes),
                    "reporting_gateways": reporting_gateways,
                    "reporting_nodes": reporting_nodes,
                }
            ))

        LAST_SYSTEM_STATE[zone_id] = state

    zone_state = db.get(ZoneState, zone_id)

    if not zone_state:
        zone_state = ZoneState(
            zone_id=zone_id,
            state=state,
            updated_at=now,
            active_devices=active_count,
            lost_devices=lost_count,
            confidence=confidence
        )

        db.add(zone_state)
    else:
        zone_state.state = state
        zone_state.updated_at = now
        zone_state.active_devices = active_count
        zone_state.lost_devices = lost_count
        zone_state.confidence = confidence

    db.commit()

    return {
        "zone_id": zone_id,
        "total_devices": total,
        "assigned_devices": assigned_total,
        "active_devices": active_count,
        "lost_devices": lost_count,
        "flood_votes": flood_votes,
        "confidence": confidence,
        "state": state,
        "sos_active": sos_active,
        "reconnected_devices": reconnected
    }
