from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routes import devices
from app.core.auth import verify_token
from app.db.session import engine, SessionLocal
from app.db.models import Base
from app.routes import zones, auth, sos, realtime, infrastructure
from app.core.watchdog import watchdog
import asyncio
from sync_firestore import restore_db, backup_db

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

async def periodic_backup():
    while True:
        await asyncio.sleep(60) # Backup every 60 seconds
        db_session = SessionLocal()
        try:
            backup_db(db_session)
        except Exception as e:
            print(f"Periodic backup failed: {e}")
        finally:
            db_session.close()

@app.on_event("startup")
async def startup_event():
    # If DB is empty, restore from Firebase
    db_session = SessionLocal()
    try:
        from app.db import models
        org_count = db_session.query(models.Organization).count()
        user_count = db_session.query(models.User).count()
        if org_count == 0 and user_count == 0:
            print("DB is empty. Restoring from Firestore backups...")
            restore_db(db_session)
    finally:
        db_session.close()
    
    # Start periodic backup
    asyncio.create_task(periodic_backup())
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
