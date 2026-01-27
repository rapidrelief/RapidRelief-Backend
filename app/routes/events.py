from fastapi import APIRouter

router = APIRouter()

@router.get("/events/health")
def events_health():
    return {"status": "Events route working"}