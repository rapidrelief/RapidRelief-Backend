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