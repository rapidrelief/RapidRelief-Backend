from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Message, User, Organization
from app.models.schemas import MessageCreate, MessageResponse
from app.core.auth import verify_token
import time

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter()

@router.get("/debug/{uid}")
def debug_user(uid: str, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.firebase_uid == uid).first()
    if not u:
        return {"error": "User not found"}
    return {
        "email": u.email,
        "role": u.role,
        "is_super_admin": u.is_super_admin
    }

@router.post("/send", response_model=MessageResponse)
def send_message(
    msg: MessageCreate,
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # Get sender info
    sender = db.query(User).filter(User.firebase_uid == user["uid"]).first()
    if not sender:
        raise HTTPException(status_code=403, detail="Sender not found")

    sender_name = sender.name or sender.email or "Unknown"

    new_msg = Message(
        sender_uid=sender.firebase_uid,
        sender_name=sender_name,
        receiver_uid=msg.receiver_uid,
        subject=msg.subject,
        content=msg.content,
        is_read=False,
        created_at=time.time()
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    return new_msg

@router.get("/inbox")
def get_inbox(
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == user["uid"]).first()
    if not db_user:
        raise HTTPException(status_code=403, detail="User not found")

    # Fetch messages directed to this specific user
    filters = [Message.receiver_uid == db_user.firebase_uid]

    # If Super Admin, fetch messages directed to "SUPER_ADMIN"
    if db_user.is_super_admin or db_user.role == "super_admin" or db_user.role == "SUPER_ADMIN":
        filters.append(Message.receiver_uid == "SUPER_ADMIN")
    
    # If Org Admin, fetch messages directed to their Org ID (e.g. "ORG-1001")
    if db_user.role == "ORG_ADMIN" and db_user.organization_id:
        filters.append(Message.receiver_uid == f"ORG-{1000 + db_user.organization_id}")

    from sqlalchemy import or_
    messages = db.query(Message).filter(or_(*filters)).order_by(Message.created_at.desc()).all()
    
    return {"status": "success", "messages": messages}

@router.post("/{message_id}/read")
def mark_message_read(
    message_id: int,
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    msg.is_read = True
    db.commit()
    return {"status": "success"}

@router.get("/contacts")
def get_contacts(
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == user["uid"]).first()
    if not db_user:
        raise HTTPException(status_code=403, detail="User not found")

    contacts = []

    # Super Admin contact (available to everyone except Super Admin)
    is_sa = db_user.is_super_admin or db_user.role == "super_admin" or db_user.role == "SUPER_ADMIN"
    if not is_sa:
        contacts.append({
            "id": "SUPER_ADMIN",
            "name": "Super Admin Dashboard",
            "type": "super_admin"
        })

    # Other Organizations (available to Org Admins and Super Admins)
    orgs = db.query(Organization).filter(Organization.status == "approved").all()
    for org in orgs:
        # Don't add own organization
        if db_user.role == "ORG_ADMIN" and db_user.organization_id == org.id:
            continue
        contacts.append({
            "id": f"ORG-{1000 + org.id}",
            "name": f"{org.name} (Organization)",
            "type": "organization"
        })

    # Rescuers belonging to the user's organization (if Org Admin)
    if db_user.role == "ORG_ADMIN" and db_user.organization_id:
        rescuers = db.query(User).filter(
            User.organization_id == db_user.organization_id,
            User.role == "RESCUER"
        ).all()
        for res in rescuers:
            contacts.append({
                "id": res.firebase_uid,
                "name": f"{res.name or res.email} (Rescuer)",
                "type": "rescuer"
            })
            
    # Rescuers (all) if Super Admin
    if is_sa:
        rescuers = db.query(User).filter(User.role == "RESCUER").all()
        for res in rescuers:
            org_name = ""
            if res.organization_id:
                org = db.query(Organization).filter(Organization.id == res.organization_id).first()
                if org:
                    org_name = f" - {org.name}"
            contacts.append({
                "id": res.firebase_uid,
                "name": f"{res.name or res.email} (Rescuer{org_name})",
                "type": "rescuer"
            })

    return {"status": "success", "contacts": contacts}
