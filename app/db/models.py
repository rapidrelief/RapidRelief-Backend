from sqlalchemy import Column, Integer, Boolean, Float, String, JSON, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Device(Base):
    __tablename__ = "devices"

    device_id = Column(Integer, primary_key=True)
    api_key = Column(String(64), nullable=False)
    last_seen = Column(Float)
    flood = Column(Boolean, default=False)
    sos = Column(Boolean, default=False)

    is_lost = Column(Boolean, default=False)
    lost_since = Column(Float, nullable=True)
    reconnected_after = Column(Integer, nullable=True)

    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)

class SystemEvent(Base):
    __tablename__ = "System_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)
    device_id = Column(Integer, nullable=True)
    timestamp = Column(Float, nullable=False)
    details = Column(JSON, nullable=True)

class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    radius_m = Column(Float, nullable=False)

    priority = Column(String, default="MEDIUM") #low / medium / high 

class ZoneState(Base):
    __tablename__ = "zone_state"

    zone_id = Column(Integer, primary_key=True)
    state = Column(String)
    updated_at = Column(Float)
    active_devices = Column(Integer)
    lost_devices = Column(Integer)
    confidence = Column(Float)    

class SOSRequest(Base):
    __tablename__ = "sos_requests"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer)
    user_id = Column(String, nullable=True)
    user_name = Column(String, nullable=True)
    user_phone = Column(String, nullable=True)
    rescuer_id = Column(String)
    rescuer_name = Column(String)
    source = Column(String, default="RESCUER")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    location_updated_at = Column(Float, nullable=True)
    is_live_location = Column(Boolean, default=False)
    status = Column(String, default="Active")
    created_at = Column(Float)
    completed_at = Column(Float, nullable=True)
    completed_by = Column(String, nullable=True)
    completed_by_name = Column(String, nullable=True)
    details = Column(JSON, nullable=True)

class ZoneNode(Base):
    __tablename__ = "zone_nodes"

    node_id = Column(Integer, primary_key=True)
    gateway_id = Column(Integer, nullable=False)

    zone_id = Column(Integer, nullable=False)
    flood = Column(Boolean, default=False)
    sos = Column(Boolean, default=False)
    last_seen = Column(Float)  
    is_lost = Column(Boolean, default=False)

    encrypted = Column(Boolean, default=True)
     
