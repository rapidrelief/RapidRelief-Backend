from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routes import devices
from app.core.auth import verify_token
from app.db.session import engine
from app.db.models import Base
from app.routes import zones
from app.core.watchdog import watchdog
from app.routes import auth
from app.routes import sos
from app.routes import realtime
from app.routes import infrastructure
import asyncio

Base.metadata.create_all(bind=engine)
sos.ensure_sos_schema()

app = FastAPI(
    title="RapidRelief API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local testing
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.on_event("startup")
async def start_watchdog():
    asyncio.create_task(watchdog())

@app.get("/")
def root():
    return { "status": "RapidRelief Backend running" }

@app.get("/api/protected")
def protected(user=Depends(verify_token)):
    return {
        "message": "Authorized",
        "uid": user["uid"],
        "email": user.get("email")
    }


app.include_router(devices.router)
app.include_router(zones.router)
app.include_router(auth.router)
app.include_router(sos.router)
app.include_router(realtime.router)
app.include_router(infrastructure.router)
