from fastapi import APIRouter
from pydantic import BaseModel 
from app.firebase.firebase import db
from firebase_admin import auth as firebase_auth
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import User, Organization
from app.models.schemas import RegisterOrgRequest, ApproveOrgRequest, CreateRescuerRequest, SuperAdminFlagRequest
import time
import secrets
import string
import random

def generate_rescuer_id():
    return "RES-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
        db.collection("users").document(user.uid).set(user.dict())

        return {
            "status": "success",
            "message": "User data stored successfully"
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/register_org")
def register_organization(req: RegisterOrgRequest):
    session = SessionLocal()
    try:
        new_org = Organization(
            name=req.org_name,
            address=req.address,
            created_at=time.time()
        )
        session.add(new_org)
        session.flush()

        new_admin = User(
            firebase_uid=req.admin_firebase_uid,
            email=req.admin_email,
            role="ORG_ADMIN",
            organization_id=new_org.id,
            name=req.admin_name,
            phone=req.admin_phone
        )
        session.add(new_admin)
        session.commit()
        return {"status": "success", "message": "Organization application submitted"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@router.post("/super_admin/flag")
def flag_super_admin(req: SuperAdminFlagRequest, db_session: Session = Depends(get_db)):
    # Simple hardcoded secret for bootstrapping
    if req.secret_key != "RAPID_RELIEF_SUPER_SECRET":
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    user = db_session.query(User).filter(User.firebase_uid == req.firebase_uid).first()
    if not user:
        # Create a stub user if they haven't registered
        user = User(
            firebase_uid=req.firebase_uid,
            email="superadmin@rapidrelief.app", # Default
            role="SUPER_ADMIN",
            is_super_admin=True
        )
        db_session.add(user)
    else:
        user.is_super_admin = True
        user.role = "SUPER_ADMIN"
    
    db_session.commit()
    
    # Sync to Firestore
    try:
        db.collection("users").document(req.firebase_uid).set({
            "uid": req.firebase_uid,
            "role": "super_admin",
            "is_super_admin": True,
            "email": user.email
        }, merge=True)
    except Exception as e:
        print(f"Firestore sync failed for super admin: {e}")
        
    return {"status": "success", "message": "User elevated to Super Admin"}

@router.post("/approve_organization")
def approve_organization(req: ApproveOrgRequest, db_session: Session = Depends(get_db)):
    # Verify super admin
    admin = db_session.query(User).filter(User.firebase_uid == req.super_admin_uid).first()
    if not admin or not admin.is_super_admin:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    org = db_session.query(Organization).filter(Organization.id == req.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    org.status = "approved"
    db_session.commit()
    
    # Sync Org Admin to Firestore
    try:
        org_admin = db_session.query(User).filter(User.organization_id == org.id, User.role == "ORG_ADMIN").first()
        if org_admin:
            db.collection("users").document(org_admin.firebase_uid).set({
                "uid": org_admin.firebase_uid,
                "email": org_admin.email,
                "role": "org_admin",
                "organization_id": org.id,
                "organization_name": org.name
            }, merge=True)
    except Exception as e:
        print(f"Firestore sync failed for org admin: {e}")
        
    return {"status": "success", "message": "Organization approved"}

@router.post("/create_rescuer")
def create_rescuer(req: CreateRescuerRequest, db_session: Session = Depends(get_db)):
    # Verify Org Admin
    admin = db_session.query(User).filter(User.firebase_uid == req.admin_uid).first()
    if not admin or admin.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized. Must be an ORG_ADMIN.")
    
    org = db_session.query(Organization).filter(Organization.id == admin.organization_id).first()
    if not org or org.status != "approved":
        raise HTTPException(status_code=403, detail="Organization is not approved yet")
    
    # Create the user in Firebase Auth
    try:
        temp_password = secrets.token_urlsafe(12)
        user_record = firebase_auth.create_user(
            email=req.rescuer_email,
            password=temp_password,
            display_name=req.rescuer_name
            # Not adding phone_number as Firebase strictly validates E.164 formatting
        )
        firebase_uid = user_record.uid
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Firebase Error: {str(e)}")

    # Create the rescuer in SQLite
    rescuer = User(
        firebase_uid=firebase_uid,
        email=req.rescuer_email,
        name=req.rescuer_name,
        phone=req.rescuer_phone,
        role="RESCUER",
        organization_id=org.id
    )
    db_session.add(rescuer)
    db_session.commit()
    
    
    rescuer_id = generate_rescuer_id()
    
    # Sync to Firestore so mobile app can login
    try:
        db.collection("users").document(firebase_uid).set({
            "uid": firebase_uid,
            "email": req.rescuer_email,
            "fullName": req.rescuer_name,
            "phone": req.rescuer_phone,
            "role": "rescuer",
            "organization_id": org.id,
            "organization_name": org.name,
            "rescuerId": rescuer_id,
            "status": "Offline",
            "cnic": "",
            "address": "",
            "emergency": ""
        }, merge=True)
    except Exception as e:
        print(f"Firestore sync failed for rescuer: {e}")
        
    return {"status": "success", "message": "Rescuer created successfully"}

@router.get("/my_profile/{firebase_uid}")
def get_my_profile(firebase_uid: str, db_session: Session = Depends(get_db)):
    user = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    org_status = "none"
    if user.organization_id:
        org = db_session.query(Organization).filter(Organization.id == user.organization_id).first()
        if org:
            org_status = org.status

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
            "name": user.name,
            "is_super_admin": user.is_super_admin,
            "password_changed": user.password_changed
        },
        "organization_status": org_status
    }

@router.get("/super_admin/approved_organizations")
def get_approved_organizations(db_session: Session = Depends(get_db)):
    orgs = db_session.query(Organization).filter(Organization.status == "approved").all()
    result = []
    for org in orgs:
        users = db_session.query(User).filter(User.organization_id == org.id).all()
        admin_user = next((u for u in users if u.role == "ORG_ADMIN"), None)
        rescuers = [u for u in users if u.role == "RESCUER"]
        
        rescuer_list = []
        for r in rescuers:
            rescuer_list.append({
                "id": r.id,
                "firebase_uid": r.firebase_uid,
                "name": r.name,
                "email": r.email,
                "phone": r.phone,
                "qualifications": getattr(r, 'qualifications', None)
            })

        result.append({
            "id": org.id,
            "name": org.name,
            "address": org.address,
            "joined_date": org.created_at,
            "admin_name": admin_user.name if admin_user else "Unknown",
            "admin_phone": admin_user.phone if admin_user else "Unknown",
            "admin_email": admin_user.email if admin_user else "Unknown",
            "total_rescuers": len(rescuers),
            "rescuers": rescuer_list
        })
    return result

@router.delete("/super_admin/user/{uid}")
def delete_user(uid: str, db_session: Session = Depends(get_db)):
    target = db_session.query(User).filter(User.firebase_uid == uid).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete from Firebase Auth
    try:
        firebase_auth.delete_user(uid)
    except Exception as e:
        print(f"Firebase delete user failed for {uid}: {e}")

    db_session.delete(target)
    db_session.commit()
    return {"status": "success", "message": "User deleted"}

@router.delete("/super_admin/organization/{org_id}")
def delete_organization(org_id: int, db_session: Session = Depends(get_db)):
    org = db_session.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    users = db_session.query(User).filter(User.organization_id == org.id).all()
    
    for u in users:
        # Delete from Firebase Auth
        try:
            firebase_auth.delete_user(u.firebase_uid)
        except Exception as e:
            print(f"Firebase delete user failed for {u.firebase_uid}: {e}")
        
        db_session.delete(u)
    
    # Delete the organization
    db_session.delete(org)
    db_session.commit()
    return {"status": "success", "message": "Organization and its users deleted"}

@router.get("/pending_organizations")
def get_pending_organizations(db_session: Session = Depends(get_db)):
    orgs = db_session.query(Organization).filter(Organization.status == "pending").all()
    result = []
    for org in orgs:
        # Get the org admin user
        admin = db_session.query(User).filter(User.organization_id == org.id, User.role == "ORG_ADMIN").first()
        result.append({
            "id": org.id,
            "name": org.name,
            "created_at": org.created_at,
            "admin_name": admin.name if admin else "Unknown",
            "admin_email": admin.email if admin else "Unknown",
            "admin_phone": admin.phone if admin else "Unknown"
        })
    return {"status": "success", "organizations": result}

@router.get("/org_admin/rescuers")
def get_org_rescuers(firebase_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    rescuers = db_session.query(User).filter(User.organization_id == caller.organization_id, User.role == "RESCUER").all()
    result = []
    for r in rescuers:
        try:
            doc = db.collection("users").document(r.firebase_uid).get()
            doc_data = doc.to_dict() if doc.exists else {}
        except Exception:
            doc_data = {}
            
        result.append({
            "id": r.id,
            "firebase_uid": r.firebase_uid,
            "name": r.name,
            "email": r.email,
            "phone": r.phone,
            "rescuer_id": doc_data.get("rescuerId", "N/A"),
            "status": doc_data.get("status", "Offline"),
            "cnic": doc_data.get("cnic", ""),
            "address": doc_data.get("address", ""),
            "emergency": doc_data.get("emergency", "")
        })
    return result

@router.delete("/org_admin/rescuer/{uid}")
def delete_org_rescuer(uid: str, admin_uid: str, db_session: Session = Depends(get_db)):
    caller = db_session.query(User).filter(User.firebase_uid == admin_uid).first()
    if not caller or caller.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    target = db_session.query(User).filter(User.firebase_uid == uid).first()
    if not target or target.organization_id != caller.organization_id:
        raise HTTPException(status_code=404, detail="Rescuer not found in your organization")
    
    # Delete from Firebase Auth
    try:
        firebase_auth.delete_user(uid)
    except Exception as e:
        print(f"Firebase delete user failed for {uid}: {e}")

    db_session.delete(target)
    db_session.commit()
    return {"status": "success", "message": "Rescuer deleted"}