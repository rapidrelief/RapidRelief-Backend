from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Report, User
from app.models.schemas import ReportCreate, ReportResponse
from app.core.auth import verify_token
import time

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter()

@router.post("/super_admin/report", response_model=ReportResponse)
def create_report(
    report: ReportCreate,
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # For FYP prototype testing, we allow any logged-in user to send reports
    # so you don't need separate Super Admin and Org Admin accounts
    db_user = db.query(User).filter(User.firebase_uid == user["uid"]).first()
    if not db_user:
        raise HTTPException(status_code=403, detail="User not found in database")
    
    new_report = Report(
        organization_id=report.organization_id,
        priority=report.priority,
        subject=report.subject,
        message=report.message,
        report_type=report.report_type,
        is_read=False,
        created_at=time.time(),
        last_activity_at=time.time(),
        replies="[]"
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

@router.get("/super_admin/reports")
def get_super_admin_reports(
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == user["uid"]).first()
    if not db_user or (not db_user.is_super_admin and db_user.role not in ["super_admin", "SUPER_ADMIN"]):
        raise HTTPException(status_code=403, detail="Not a Super Admin")

    all_reports = db.query(Report).order_by(Report.created_at.desc()).all()
    current_time = time.time()
    filtered = []
    for r in all_reports:
        activity = r.last_activity_at or r.created_at
        if not r.is_read:
            filtered.append(r)
        elif (current_time - activity) <= 3600:
            filtered.append(r)
    
    return {"status": "success", "reports": filtered}

@router.post("/super_admin/reports/{report_id}/reply")
def reply_report_super_admin(
    report_id: int,
    reply: dict,
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == user["uid"]).first()
    if not db_user or (not db_user.is_super_admin and db_user.role not in ["super_admin", "SUPER_ADMIN"]):
        raise HTTPException(status_code=403, detail="Not a Super Admin")
        
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    import json
    replies = json.loads(report.replies or "[]")
    replies.append({
        "sender": "SUPER_ADMIN",
        "content": reply.get("content", ""),
        "timestamp": time.time()
    })
    report.replies = json.dumps(replies)
    report.last_activity_at = time.time()
    report.is_read = False # Make it unread for Org Admin
    db.commit()
    return {"status": "success"}

@router.get("/org_admin/reports")
def get_reports(
    firebase_uid: str,
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not db_user or not db_user.organization_id:
        raise HTTPException(status_code=403, detail="Not an organization admin")
    
    # Auto-expire reports older than 1 hour (3600 seconds) since last activity, unread stays
    current_time = time.time()
    all_reports = db.query(Report).filter(Report.organization_id == db_user.organization_id).order_by(Report.created_at.desc()).all()
    filtered = []
    for r in all_reports:
        activity = r.last_activity_at or r.created_at
        if not r.is_read:
            filtered.append(r)
        elif (current_time - activity) <= 3600:
            filtered.append(r)
    
    return {"status": "success", "reports": filtered}

@router.post("/org_admin/reports/{report_id}/reply")
def reply_report_org_admin(
    report_id: int,
    reply: dict,
    firebase_uid: str,
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not db_user or not db_user.organization_id:
        raise HTTPException(status_code=403, detail="Not an organization admin")
        
    report = db.query(Report).filter(Report.id == report_id, Report.organization_id == db_user.organization_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    import json
    replies = json.loads(report.replies or "[]")
    replies.append({
        "sender": "ORG_ADMIN",
        "content": reply.get("content", ""),
        "timestamp": time.time()
    })
    report.replies = json.dumps(replies)
    report.last_activity_at = time.time()
    report.is_read = False # Make it unread for Super Admin
    db.commit()
    return {"status": "success"}

@router.post("/org_admin/reports/{report_id}/read")
def mark_report_read(
    report_id: int,
    firebase_uid: str,
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not db_user or not db_user.organization_id:
        raise HTTPException(status_code=403, detail="Not an organization admin")
    
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report or report.organization_id != db_user.organization_id:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report.is_read = True
    db.commit()
    return {"status": "success"}
