from pydantic import BaseModel

class ZoneCreate(BaseModel):
    name: str
    lat: float
    lng: float
    radius_m: float
    priority: str