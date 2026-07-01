import requests
import json

# Assuming local uvicorn is NOT running, we will start it or just test the router locally using FastAPI TestClient
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# We need a zone id, let's use 1 if it exists
response = client.get("/prediction/zone/1")
print(response.status_code)
print(json.dumps(response.json(), indent=2))
