from pydantic import BaseModel
from typing import Optional

class ZoneCreate(BaseModel):
    name: str
    lat: float
    lng: float
    radius_m: float
    priority: str

class OrganizationCreate(BaseModel):
    name: str

class RegisterOrgRequest(BaseModel):
    org_name: str
    address: Optional[str] = None
    admin_firebase_uid: str
    admin_email: str
    admin_name: str
    admin_phone: str

class ApproveOrgRequest(BaseModel):
    organization_id: int
    super_admin_uid: str

class CreateRescuerRequest(BaseModel):
    admin_uid: str
    rescuer_email: str
    rescuer_name: str
    rescuer_phone: str

class SuperAdminFlagRequest(BaseModel):
    firebase_uid: str
    secret_key: str # A simple hardcoded secret to allow the first super admin to bootstrap

class ReportCreate(BaseModel):
    organization_id: int
    priority: str
    subject: str
    message: str
    report_type: str

class ReportResponse(BaseModel):
    id: int
    organization_id: int
    priority: str
    subject: str
    message: str
    report_type: str
    is_read: bool
    created_at: float
    last_activity_at: float | None = None
    replies: str = "[]"

    class Config:
        from_attributes = True

class ReportReplyCreate(BaseModel):
    content: str

class MessageCreate(BaseModel):
    receiver_uid: str
    subject: str
    content: str

class MessageResponse(BaseModel):
    id: int
    sender_uid: str
    sender_name: str
    receiver_uid: str
    subject: str
    content: str
    is_read: bool
    created_at: float

    class Config:
        from_attributes = True