import time
import secrets
import hmac
import hashlib
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Device, Zone, SOSRequest, ZoneState

client = TestClient(app)

def test_offline_sos_endpoint():
    db = SessionLocal()
    
    # 1. Setup a test zone and device (if not already existing)
    zone = db.query(Zone).filter(Zone.id == 1).first()
    if not zone:
        zone = Zone(id=1, name="Test Sector A", lat=24.8607, lng=67.0011, radius_m=500.0, priority="medium")
        db.add(zone)
        db.commit()
        db.refresh(zone)
        print("Created test zone 1.")
        
    device = db.query(Device).filter(Device.device_id == 22).first()
    api_key = "17fdb4310d198b361b14af7febb011341b7a709b8ce61abbd3761cf697c55a7d"
    if not device:
        device = Device(
            device_id=22,
            api_key=api_key,
            last_seen=time.time(),
            flood=False,
            sos=False,
            is_lost=False,
            zone_id=1
        )
        db.add(device)
        db.commit()
        print("Created test gateway device 22.")
    else:
        # Ensure it has our test API key
        device.api_key = api_key
        db.commit()

    # Clear any old active SOS requests for the test phone to ensure clean test
    db.query(SOSRequest).filter(SOSRequest.user_phone == "03001234567").delete()
    db.commit()
    
    db.close()

    # 2. Compute device HMAC signature for authentication
    timestamp = str(int(time.time()))
    payload = f"22:{timestamp}"
    signature = hmac.new(
        api_key.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-Device-ID": "22",
        "X-Timestamp": timestamp,
        "X-Device-Signature": signature,
        "Content-Type": "application/json"
    }

    # 3. Post offline SOS data
    post_data = {
        "node_id": 101,
        "name": "Jane Doe",
        "phone": "03001234567",
        "lat": 24.8615,
        "lng": 67.0020,
        "sequence": 42
    }

    print("Sending POST request to /api/devices/offline-sos...")
    response = client.post("/api/devices/offline-sos", json=post_data, headers=headers)
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    assert response.status_code == 200
    assert "Offline SOS Alert Relayed" in response.json()["message"]

    # 4. Verify database record
    db = SessionLocal()
    sos_req = (
        db.query(SOSRequest)
        .filter(SOSRequest.user_phone == "03001234567")
        .filter(SOSRequest.status == "ACTIVE")
        .first()
    )
    
    assert sos_req is not None
    assert sos_req.user_name == "Jane Doe (OFFLINE BLE via Node 101)"
    assert sos_req.lat == 24.8615
    assert sos_req.lng == 67.0020
    assert sos_req.source == "AUTO"
    print("Database SOS Request verification passed!")

    # 5. Verify ZoneState changed to SOS
    zone_state = db.query(ZoneState).filter(ZoneState.zone_id == 1).first()
    assert zone_state is not None
    assert zone_state.state == "SOS"
    print("Zone state verification passed! Zone 1 is in SOS state.")

    # Cleanup
    db.query(SOSRequest).filter(SOSRequest.user_phone == "03001234567").delete()
    db.commit()
    db.close()
    print("Cleanup successful. Test passed!")

if __name__ == "__main__":
    test_offline_sos_endpoint()
