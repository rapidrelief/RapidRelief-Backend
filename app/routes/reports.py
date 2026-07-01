from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Report, User
from app.models.schemas import ReportCreate, ReportResponse
from app.core.auth import verify_token
import time

router = APIRouter()

@router.post("/super_admin/report", response_model=ReportResponse)
def create_report(
    report: ReportCreate,
    user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    # Verify Super Admin
    db_user = db.query(User).filter(User.firebase_uid == user["uid"]).first()
    if not db_user or db_user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    new_report = Report(
        organization_id=report.organization_id,
        priority=report.priority,
        subject=report.subject,
        message=report.message,
        report_type=report.report_type,
        is_read=False,
        created_at=time.time()
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

@router.get("/org_admin/reports")
def get_reports(
    firebase_uid: str,
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not db_user or not db_user.organization_id:
        raise HTTPException(status_code=403, detail="Not an organization admin")
    
    reports = db.query(Report).filter(
        Report.organization_id == db_user.organization_id
    ).order_by(Report.created_at.desc()).all()
    
    return {"status": "success", "reports": reports}

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
