from fastapi import APIRouter
from pydantic import BaseModel 
from app.firebase.firebase import db

router = APIRouter()

class UserModel(BaseModel):
    uid: str
    fullName: str
    email: str
    phone: str
    emergency: str
    address: str
    cnic: str

@router.post("/signup")
async def signup(user: UserModel):
    try:
        db.collection("user").document(user.uid).set(user.dict())

        return {
            "status": "success",
            "message": "User data stored successfully"
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }