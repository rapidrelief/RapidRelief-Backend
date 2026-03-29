import time
from app.db.session import SessionLocal
from app.db.models import Device, SystemEvent, ZoneState

HEARTBEAT_TIMEOUT = 20 #120 for testing 30 sec will be in production
FLOOD_QUORUM_PERCENT = 0.6
MIN_ACTIVE_DEVICES = 2

LAST_SYSTEM_STATE = {}

# -----------------------------
# HEARTBEAT UPDATE
# -----------------------------
def update_heartbeat(device_id: int, flood: bool, sos: bool):

    db = SessionLocal()
    now = time.time()

    device = db.get(Device, device_id)

    if not device:
        db.close()
        raise RuntimeError("Heartbeat from non-registered device")

    # reconnect logic
    if device.is_lost:

        downtime = int(now - device.lost_since)

        event = SystemEvent(
            event_type="DEVICE_RECONNECTED",
            device_id=device.device_id,
            timestamp=now,
            details={"downtime_sec": downtime}
        )

        db.add(event)

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


# -----------------------------
# ZONE ENGINE
# -----------------------------
def evaluate_system(zone_id: int, db):

    now = time.time()

    devices = db.query(Device).filter(Device.zone_id == zone_id).all()

    active = []
    lost = []
    flood_votes = 0
    sos_active = False
    reconnected = []

    for d in devices:
        db.expire(d)
        db.refresh(d)

        if d.last_seen is None:
            continue

        # timeout check
        if d.last_seen is not None and (now - d.last_seen) > HEARTBEAT_TIMEOUT:
            print(f"[TIMEOUT] Device {d.device_id} Lost")

            if not d.is_lost:

                d.is_lost = True
                d.lost_since = now

                db.add(SystemEvent(
                    event_type="DEVICE_LOST",
                    device_id=d.device_id,
                    timestamp=now,
                    details={"zone": zone_id}
                ))

            lost.append(d)

        else:

            active.append(d)

            if d.flood:
                flood_votes += 1

            if d.sos:
                sos_active = True

            if d.reconnected_after:
                reconnected.append({
                    "device_id": d.device_id,
                    "downtime_sec": d.reconnected_after
                })

    active_count = len(active)
    lost_count = len(lost)
    total = len(devices)

    # -----------------------------
    # FINAL STATE DECISION (FIXED)
    # -----------------------------
    if sos_active:

        state = "SOS"
        confidence = 100.0

    elif active_count == 0:

        state = "NO_SIGNAL"
        confidence = 0.0

    elif active_count < MIN_ACTIVE_DEVICES:

        state = "WEAK_SIGNAL"
        confidence = 20.0

    else:

        flood_ratio = flood_votes / active_count

        if flood_ratio >= FLOOD_QUORUM_PERCENT:
            state = "FLOOD"
        elif flood_ratio >= 0.3:
            state = "WARNING"
        else:
            state = "SAFE"

        confidence = flood_ratio * 100

    confidence = round(confidence, 2)

    # -----------------------------
    # SYSTEM EVENT ON STATE CHANGE
    # -----------------------------
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

        LAST_SYSTEM_STATE[zone_id] = state

    # -----------------------------
    # UPDATE ZONE STATE TABLE
    # -----------------------------
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
        "active_devices": active_count,
        "lost_devices": lost_count,
        "flood_votes": flood_votes,
        "confidence": confidence,
        "state": state,
        "sos_active": sos_active,
        "reconnected_devices": reconnected
    }