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