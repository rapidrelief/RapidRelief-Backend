from fastapi import APIRouter

router = APIRouter()

@router.get("/devices/health")
def devices_health():
    return {"status": "Devices route working"}