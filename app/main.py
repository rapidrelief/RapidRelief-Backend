from fastapi import FastAPI
from app.routes import devices, events

app = FastAPI(title="Flood Alert Backend")

app.include_router(devices.router, prefix="/api")
app.include_router(events.router, prefix="/api")

@app.get("/")
def root():
    return {"status": "Backend Running"}