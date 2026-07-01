from sqlalchemy import Column, Integer, Boolean, Float, String, JSON, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    status = Column(String, default="pending") # pending, approved, rejected
    created_at = Column(Float)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    firebase_uid = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    role = Column(String, nullable=False) # SUPER_ADMIN, ORG_ADMIN, RESCUER
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    qualifications = Column(JSON, nullable=True)
    password_changed = Column(Boolean, default=False)
    is_super_admin = Column(Boolean, default=False) # The manual flag
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    location_updated_at = Column(Float, nullable=True)

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
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

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
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

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
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    priority = Column(String, default="Medium") # High, Medium, Low
    subject = Column(String, nullable=False)
    message = Column(String, nullable=False)
    report_type = Column(String, default="Notification") # Flood Warning, SOS, Notification
    is_read = Column(Boolean, default=False)
    created_at = Column(Float, nullable=False)
    last_activity_at = Column(Float, nullable=True)
    replies = Column(String, default="[]") # JSON stringified array of replies

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_uid = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    receiver_uid = Column(String, nullable=False) # "SUPER_ADMIN", "ORG-1001", or specific user Firebase UID
    subject = Column(String, nullable=False)
    content = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(Float, nullable=False)
