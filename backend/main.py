"""
Manufacturing Quality Memory Agent — FastAPI Backend
"""
from __future__ import annotations
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from config import settings
from database import get_db, create_tables
from models import (
    QualityIncident, InspectionFinding, RootCause, CorrectiveAction,
    ProductionLine, Machine, Product, Supplier, Document, User,
    SeverityEnum, IncidentStatusEnum, EffectivenessEnum,
)
from ai_service import get_embedding, chat_completion
from search_engine import search_incidents, find_similar_incidents, detect_recurring_defects

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Manufacturing Quality Memory Agent",
    description="AI-powered manufacturing quality intelligence platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
async def startup():
    create_tables()
    logger.info("Database tables created/verified")


# ── Helper serialisers ─────────────────────────────────────────────────────────

def serialise_incident(inc: QualityIncident) -> dict:
    return {
        "id": inc.id,
        "incident_id": inc.incident_id,
        "title": inc.title,
        "description": inc.description,
        "defect_category": inc.defect_category,
        "severity": inc.severity.value if inc.severity else None,
        "status": inc.status.value if inc.status else None,
        "production_line": inc.production_line.name if inc.production_line else None,
        "production_line_id": inc.production_line_id,
        "machine": inc.machine.name if inc.machine else None,
        "machine_id": inc.machine_id,
        "product": inc.product.name if inc.product else None,
        "product_id": inc.product_id,
        "supplier": inc.supplier.name if inc.supplier else None,
        "supplier_id": inc.supplier_id,
        "batch_number": inc.batch_number,
        "quantity_affected": inc.quantity_affected,
        "shift": inc.shift,
        "operator": inc.operator,
        "owner": inc.owner,
        "process_parameters": inc.process_parameters,
        "occurred_at": inc.occurred_at.isoformat() if inc.occurred_at else None,
        "reported_at": inc.reported_at.isoformat() if inc.reported_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        "created_at": inc.created_at.isoformat() if inc.created_at else None,
        "inspection_findings": [
            {
                "id": f.id,
                "finding": f.finding,
                "measurement": f.measurement,
                "specification": f.specification,
                "deviation": f.deviation,
                "inspector": f.inspector,
                "inspection_date": f.inspection_date.isoformat() if f.inspection_date else None,
            }
            for f in inc.inspection_findings
        ],
        "root_causes": [
            {
                "id": r.id,
                "category": r.category,
                "description": r.description,
                "identified_by": r.identified_by,
                "confidence": r.confidence,
                "identified_at": r.identified_at.isoformat() if r.identified_at else None,
            }
            for r in inc.root_causes
        ],
        "corrective_actions": [
            {
                "id": c.id,
                "action": c.action,
                "preventive_action": c.preventive_action,
                "owner": c.owner,
                "due_date": c.due_date.isoformat() if c.due_date else None,
                "completed_date": c.completed_date.isoformat() if c.completed_date else None,
                "effectiveness": c.effectiveness.value if c.effectiveness else None,
                "effectiveness_notes": c.effectiveness_notes,
                "recurrence_after_action": c.recurrence_after_action,
            }
            for c in inc.corrective_actions
        ],
        "documents": [{"id": d.id, "filename": d.filename, "processing_status": d.processing_status} for d in inc.documents],
    }


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    total = db.query(QualityIncident).count()
    open_count = db.query(QualityIncident).filter(
        QualityIncident.status.in_([IncidentStatusEnum.OPEN, IncidentStatusEnum.IN_PROGRESS])
    ).count()
    resolved = db.query(QualityIncident).filter(
        QualityIncident.status == IncidentStatusEnum.RESOLVED
    ).count()

    # CAs
    total_ca = db.query(CorrectiveAction).count()
    open_ca = db.query(CorrectiveAction).filter(
        CorrectiveAction.completed_date == None
    ).count()
    completed_ca = total_ca - open_ca

    # Recurring (patterns with 2+ incidents)
    patterns = detect_recurring_defects(db)
    recurring_count = sum(1 for p in patterns if p["occurrences"] >= 2)

    # By severity
    critical_count = db.query(QualityIncident).filter(
        QualityIncident.severity == SeverityEnum.CRITICAL
    ).count()
    high_count = db.query(QualityIncident).filter(
        QualityIncident.severity == SeverityEnum.HIGH
    ).count()

    # Top machines
    machine_counts = (
        db.query(Machine.name, func.count(QualityIncident.id).label("count"))
        .join(QualityIncident, QualityIncident.machine_id == Machine.id)
        .group_by(Machine.name)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    # Top lines
    line_counts = (
        db.query(ProductionLine.name, func.count(QualityIncident.id).label("count"))
        .join(QualityIncident, QualityIncident.production_line_id == ProductionLine.id)
        .group_by(ProductionLine.name)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    # Top defect categories
    cat_counts = (
        db.query(QualityIncident.defect_category, func.count(QualityIncident.id).label("count"))
        .filter(QualityIncident.defect_category != None)
        .group_by(QualityIncident.defect_category)
        .order_by(desc("count"))
        .limit(8)
        .all()
    )

    # Monthly trend (last 12 months)
    monthly = []
    for m in range(11, -1, -1):
        d = datetime.utcnow() - timedelta(days=30 * m)
        start = d.replace(day=1, hour=0, minute=0, second=0)
        end = (start + timedelta(days=32)).replace(day=1)
        count = db.query(QualityIncident).filter(
            QualityIncident.occurred_at >= start,
            QualityIncident.occurred_at < end,
        ).count()
        monthly.append({"month": start.strftime("%b %Y"), "count": count})

    # Recent incidents
    recent = db.query(QualityIncident).order_by(
        desc(QualityIncident.occurred_at)
    ).limit(8).all()

    recurrence_rate = round((recurring_count / total * 100) if total > 0 else 0, 1)

    return {
        "summary": {
            "total_incidents": total,
            "open_incidents": open_count,
            "resolved_incidents": resolved,
            "critical_incidents": critical_count,
            "high_incidents": high_count,
            "recurring_defect_patterns": recurring_count,
            "total_corrective_actions": total_ca,
            "open_corrective_actions": open_ca,
            "completed_corrective_actions": completed_ca,
            "recurrence_rate": recurrence_rate,
        },
        "top_machines": [{"name": name, "count": count} for name, count in machine_counts],
        "top_lines": [{"name": name, "count": count} for name, count in line_counts],
        "defect_categories": [{"category": cat, "count": count} for cat, count in cat_counts],
        "monthly_trend": monthly,
        "recent_incidents": [serialise_incident(i) for i in recent],
        "top_recurring_patterns": patterns[:5],
    }


# ── Production Lines ───────────────────────────────────────────────────────────

@app.get("/api/production-lines")
def list_lines(db: Session = Depends(get_db)):
    lines = db.query(ProductionLine).all()
    return [{"id": l.id, "name": l.name, "description": l.description, "location": l.location} for l in lines]


# ── Machines ───────────────────────────────────────────────────────────────────

@app.get("/api/machines")
def list_machines(db: Session = Depends(get_db)):
    machines = db.query(Machine).all()
    return [
        {
            "id": m.id, "name": m.name, "machine_type": m.machine_type,
            "model": m.model, "serial_number": m.serial_number,
            "production_line": m.production_line.name if m.production_line else None,
            "production_line_id": m.production_line_id,
            "operating_hours": m.operating_hours,
            "last_maintenance_date": m.last_maintenance_date.isoformat() if m.last_maintenance_date else None,
        }
        for m in machines
    ]


# ── Products ───────────────────────────────────────────────────────────────────

@app.get("/api/products")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return [{"id": p.id, "name": p.name, "product_code": p.product_code, "category": p.category} for p in products]


# ── Suppliers ──────────────────────────────────────────────────────────────────

@app.get("/api/suppliers")
def list_suppliers(db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).all()
    return [{"id": s.id, "name": s.name, "code": s.code, "country": s.country} for s in suppliers]


# ── Quality Incidents CRUD ─────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    title: str
    description: str
    defect_category: Optional[str] = None
    severity: str = "Medium"
    production_line_id: Optional[str] = None
    machine_id: Optional[str] = None
    product_id: Optional[str] = None
    supplier_id: Optional[str] = None
    batch_number: Optional[str] = None
    quantity_affected: Optional[int] = None
    shift: Optional[str] = None
    operator: Optional[str] = None
    owner: Optional[str] = None
    occurred_at: Optional[str] = None
    process_parameters: Optional[dict] = None


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    defect_category: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    production_line_id: Optional[str] = None
    machine_id: Optional[str] = None
    product_id: Optional[str] = None
    supplier_id: Optional[str] = None
    batch_number: Optional[str] = None
    quantity_affected: Optional[int] = None
    shift: Optional[str] = None
    operator: Optional[str] = None
    owner: Optional[str] = None
    occurred_at: Optional[str] = None
    resolved_at: Optional[str] = None
    process_parameters: Optional[dict] = None


@app.get("/api/incidents")
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    defect_category: Optional[str] = None,
    production_line: Optional[str] = None,
    machine: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(QualityIncident)

    if status:
        q = q.filter(QualityIncident.status == status)
    if severity:
        q = q.filter(QualityIncident.severity == severity)
    if defect_category:
        q = q.filter(QualityIncident.defect_category.ilike(f"%{defect_category}%"))
    if production_line:
        q = q.join(ProductionLine).filter(ProductionLine.name.ilike(f"%{production_line}%"))
    if machine:
        q = q.join(Machine).filter(Machine.name.ilike(f"%{machine}%"))
    if search:
        q = q.filter(
            QualityIncident.title.ilike(f"%{search}%") |
            QualityIncident.description.ilike(f"%{search}%") |
            QualityIncident.incident_id.ilike(f"%{search}%")
        )

    total = q.count()
    incidents = q.order_by(desc(QualityIncident.occurred_at)).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialise_incident(i) for i in incidents],
    }


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")
    return serialise_incident(inc)


@app.post("/api/incidents", status_code=201)
async def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    # Auto-generate incident ID
    count = db.query(QualityIncident).count()
    qir_id = f"QIR-{2000 + count + 1}"

    occurred = None
    if payload.occurred_at:
        try:
            occurred = datetime.fromisoformat(payload.occurred_at)
        except Exception:
            occurred = datetime.utcnow()
    else:
        occurred = datetime.utcnow()

    severity = SeverityEnum(payload.severity) if payload.severity else SeverityEnum.MEDIUM

    inc = QualityIncident(
        incident_id=qir_id,
        title=payload.title,
        description=payload.description,
        defect_category=payload.defect_category,
        severity=severity,
        status=IncidentStatusEnum.OPEN,
        production_line_id=payload.production_line_id,
        machine_id=payload.machine_id,
        product_id=payload.product_id,
        supplier_id=payload.supplier_id,
        batch_number=payload.batch_number,
        quantity_affected=payload.quantity_affected,
        shift=payload.shift,
        operator=payload.operator,
        owner=payload.owner,
        occurred_at=occurred,
        process_parameters=payload.process_parameters,
    )

    # Generate embedding
    text = f"{payload.title} {payload.description} {payload.defect_category or ''}"
    inc.embedding = await get_embedding(text)

    db.add(inc)
    db.commit()
    db.refresh(inc)
    return serialise_incident(inc)


@app.patch("/api/incidents/{incident_id}")
async def update_incident(incident_id: str, payload: IncidentUpdate, db: Session = Depends(get_db)):
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")

    update_data = payload.dict(exclude_none=True)

    if "severity" in update_data:
        update_data["severity"] = SeverityEnum(update_data["severity"])
    if "status" in update_data:
        update_data["status"] = IncidentStatusEnum(update_data["status"])
    if "occurred_at" in update_data:
        update_data["occurred_at"] = datetime.fromisoformat(update_data["occurred_at"])
    if "resolved_at" in update_data:
        update_data["resolved_at"] = datetime.fromisoformat(update_data["resolved_at"])

    for k, v in update_data.items():
        setattr(inc, k, v)

    # Re-embed if description changed
    if "title" in update_data or "description" in update_data:
        text = f"{inc.title} {inc.description} {inc.defect_category or ''}"
        inc.embedding = await get_embedding(text)

    db.commit()
    db.refresh(inc)
    return serialise_incident(inc)


@app.delete("/api/incidents/{incident_id}", status_code=204)
def delete_incident(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")
    db.delete(inc)
    db.commit()


# ── Findings / Root Causes / Corrective Actions (sub-resources) ────────────────

class FindingCreate(BaseModel):
    finding: str
    measurement: Optional[str] = None
    specification: Optional[str] = None
    deviation: Optional[str] = None
    inspector: Optional[str] = None
    inspection_date: Optional[str] = None


@app.post("/api/incidents/{incident_id}/findings", status_code=201)
def add_finding(incident_id: str, payload: FindingCreate, db: Session = Depends(get_db)):
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")

    f = InspectionFinding(
        incident_id=inc.id,
        finding=payload.finding,
        measurement=payload.measurement,
        specification=payload.specification,
        deviation=payload.deviation,
        inspector=payload.inspector,
        inspection_date=datetime.fromisoformat(payload.inspection_date) if payload.inspection_date else None,
    )
    db.add(f)
    db.commit()
    return {"id": f.id, "finding": f.finding}


class RootCauseCreate(BaseModel):
    description: str
    category: Optional[str] = "Machine"
    identified_by: Optional[str] = None
    confidence: Optional[float] = 1.0


@app.post("/api/incidents/{incident_id}/root-causes", status_code=201)
def add_root_cause(incident_id: str, payload: RootCauseCreate, db: Session = Depends(get_db)):
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")

    rc = RootCause(
        incident_id=inc.id,
        description=payload.description,
        category=payload.category,
        identified_by=payload.identified_by,
        confidence=payload.confidence,
        identified_at=datetime.utcnow(),
    )
    db.add(rc)
    db.commit()
    return {"id": rc.id, "description": rc.description}


class CorrectiveActionCreate(BaseModel):
    action: str
    preventive_action: Optional[str] = None
    owner: Optional[str] = None
    due_date: Optional[str] = None
    root_cause_id: Optional[str] = None


@app.post("/api/incidents/{incident_id}/corrective-actions", status_code=201)
def add_corrective_action(incident_id: str, payload: CorrectiveActionCreate, db: Session = Depends(get_db)):
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")

    ca = CorrectiveAction(
        incident_id=inc.id,
        action=payload.action,
        preventive_action=payload.preventive_action,
        owner=payload.owner,
        root_cause_id=payload.root_cause_id,
        due_date=datetime.fromisoformat(payload.due_date) if payload.due_date else None,
        effectiveness=EffectivenessEnum.PENDING,
    )
    db.add(ca)
    db.commit()
    return {"id": ca.id, "action": ca.action}


# ── AI Agent ───────────────────────────────────────────────────────────────────

class AgentQuery(BaseModel):
    message: str
    conversation_history: list[dict] = []
    filters: Optional[dict] = None
    incident_id: Optional[str] = None  # investigate specific incident


@app.post("/api/agent/query")
async def agent_query(payload: AgentQuery, db: Session = Depends(get_db)):
    """
    Main AI agent endpoint.
    1. Embed the user query
    2. Search similar incidents
    3. Pass context to LLM
    4. Return structured response
    """
    user_message = payload.message

    # Get query embedding
    query_embedding = await get_embedding(user_message)

    # Retrieve similar incidents
    similar = search_incidents(
        db,
        query=user_message,
        query_embedding=query_embedding,
        top_k=12,
        filters=payload.filters,
    )

    # If investigating a specific incident, also fetch its similar ones
    if payload.incident_id and not similar:
        similar = find_similar_incidents(db, payload.incident_id, top_k=8)

    # Build messages for LLM
    messages = payload.conversation_history.copy()
    messages.append({"role": "user", "content": user_message})

    # Generate AI response
    ai_response = await chat_completion(
        messages=messages,
        context_incidents=similar,
        temperature=0.2,
    )

    return {
        "response": ai_response,
        "retrieved_incidents": similar[:8],
        "total_retrieved": len(similar),
        "ai_provider": "azure" if settings.azure_available else "local",
    }


@app.post("/api/agent/investigate/{incident_id}")
async def investigate_incident(incident_id: str, db: Session = Depends(get_db)):
    """Trigger full AI investigation of a specific incident."""
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")

    # Build investigation query
    query = f"{inc.title}. {inc.description}. Machine: {inc.machine.name if inc.machine else ''}. Line: {inc.production_line.name if inc.production_line else ''}. Defect category: {inc.defect_category or ''}."

    query_embedding = await get_embedding(query)

    similar = search_incidents(
        db,
        query=query,
        query_embedding=query_embedding,
        top_k=12,
    )
    # Exclude the incident itself
    similar = [s for s in similar if s["id"] != inc.id]

    investigation_prompt = f"""Investigate this quality incident and provide a comprehensive analysis:

Incident: {inc.incident_id}
Title: {inc.title}
Description: {inc.description}
Machine: {inc.machine.name if inc.machine else 'Unknown'}
Production Line: {inc.production_line.name if inc.production_line else 'Unknown'}
Product: {inc.product.name if inc.product else 'Unknown'}
Defect Category: {inc.defect_category}
Severity: {inc.severity.value if inc.severity else 'Unknown'}
Shift: {inc.shift or 'Unknown'}

Based on the historical incidents provided, identify:
1. Similar historical patterns
2. Probable root cause (based on evidence only)
3. Previously successful corrective actions
4. Recommended investigation steps
"""

    ai_response = await chat_completion(
        messages=[{"role": "user", "content": investigation_prompt}],
        context_incidents=similar,
        temperature=0.2,
    )

    return {
        "incident": serialise_incident(inc),
        "investigation_summary": ai_response,
        "similar_incidents": similar[:8],
        "total_similar": len(similar),
        "ai_provider": "azure" if settings.azure_available else "local",
    }


# ── Search ─────────────────────────────────────────────────────────────────────

@app.get("/api/search")
async def semantic_search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    production_line: Optional[str] = None,
    machine: Optional[str] = None,
    defect_category: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query_embedding = await get_embedding(q)
    filters = {}
    if production_line:
        filters["production_line"] = production_line
    if machine:
        filters["machine"] = machine
    if defect_category:
        filters["defect_category"] = defect_category
    if severity:
        filters["severity"] = severity

    results = search_incidents(db, q, query_embedding, top_k=top_k, filters=filters)
    return {"query": q, "results": results, "total": len(results)}


# ── Similar Incidents ──────────────────────────────────────────────────────────

@app.get("/api/incidents/{incident_id}/similar")
def get_similar_incidents(incident_id: str, top_k: int = Query(6, ge=1, le=20), db: Session = Depends(get_db)):
    inc = db.query(QualityIncident).filter(
        (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
    ).first()
    if not inc:
        raise HTTPException(404, "Incident not found")

    similar = find_similar_incidents(db, inc.id, top_k=top_k)
    return {"incident_id": incident_id, "similar": similar}


# ── Recurring Defects ──────────────────────────────────────────────────────────

@app.get("/api/recurring-defects")
def get_recurring_defects(db: Session = Depends(get_db)):
    patterns = detect_recurring_defects(db)
    return {"patterns": patterns, "total": len(patterns)}


# ── Root Causes ────────────────────────────────────────────────────────────────

@app.get("/api/root-causes")
def list_root_causes(db: Session = Depends(get_db)):
    rcs = db.query(RootCause).all()
    return [
        {
            "id": r.id,
            "incident_id": r.incident.incident_id if r.incident else None,
            "category": r.category,
            "description": r.description,
            "identified_by": r.identified_by,
            "confidence": r.confidence,
            "corrective_actions": [
                {"action": c.action, "effectiveness": c.effectiveness.value if c.effectiveness else None}
                for c in r.corrective_actions
            ],
        }
        for r in rcs
    ]


# ── Corrective Actions ─────────────────────────────────────────────────────────

@app.get("/api/corrective-actions")
def list_corrective_actions(
    effectiveness: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(CorrectiveAction)
    if effectiveness:
        q = q.filter(CorrectiveAction.effectiveness == effectiveness)
    cas = q.order_by(desc(CorrectiveAction.completed_date)).all()
    return [
        {
            "id": c.id,
            "incident_id": c.incident.incident_id if c.incident else None,
            "action": c.action,
            "preventive_action": c.preventive_action,
            "owner": c.owner,
            "due_date": c.due_date.isoformat() if c.due_date else None,
            "completed_date": c.completed_date.isoformat() if c.completed_date else None,
            "effectiveness": c.effectiveness.value if c.effectiveness else None,
            "effectiveness_notes": c.effectiveness_notes,
            "recurrence_after_action": c.recurrence_after_action,
            "root_cause": c.root_cause.description if c.root_cause else None,
        }
        for c in cas
    ]


# ── Analytics ──────────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    # By severity
    severity_data = []
    for sev in SeverityEnum:
        cnt = db.query(QualityIncident).filter(QualityIncident.severity == sev).count()
        severity_data.append({"severity": sev.value, "count": cnt})

    # By defect category
    cat_data = (
        db.query(QualityIncident.defect_category, func.count(QualityIncident.id).label("count"))
        .filter(QualityIncident.defect_category != None)
        .group_by(QualityIncident.defect_category)
        .order_by(desc("count"))
        .all()
    )

    # By machine
    machine_data = (
        db.query(Machine.name, func.count(QualityIncident.id).label("count"))
        .join(QualityIncident, QualityIncident.machine_id == Machine.id)
        .group_by(Machine.name)
        .order_by(desc("count"))
        .all()
    )

    # By line
    line_data = (
        db.query(ProductionLine.name, func.count(QualityIncident.id).label("count"))
        .join(QualityIncident, QualityIncident.production_line_id == ProductionLine.id)
        .group_by(ProductionLine.name)
        .order_by(desc("count"))
        .all()
    )

    # By shift
    shift_data = (
        db.query(QualityIncident.shift, func.count(QualityIncident.id).label("count"))
        .filter(QualityIncident.shift != None)
        .group_by(QualityIncident.shift)
        .all()
    )

    # CA effectiveness
    eff_data = []
    for eff in EffectivenessEnum:
        cnt = db.query(CorrectiveAction).filter(CorrectiveAction.effectiveness == eff).count()
        eff_data.append({"effectiveness": eff.value, "count": cnt})

    # MTTR (mean time to resolve in days)
    resolved = db.query(QualityIncident).filter(
        QualityIncident.resolved_at != None,
        QualityIncident.occurred_at != None,
    ).all()
    if resolved:
        durations = [(r.resolved_at - r.occurred_at).days for r in resolved if r.resolved_at > r.occurred_at]
        mttr = round(sum(durations) / len(durations), 1) if durations else 0
    else:
        mttr = 0

    # Monthly trend (12 months)
    monthly = []
    for m in range(11, -1, -1):
        d = datetime.utcnow() - timedelta(days=30 * m)
        start = d.replace(day=1, hour=0, minute=0, second=0)
        end = (start + timedelta(days=32)).replace(day=1)
        cnt = db.query(QualityIncident).filter(
            QualityIncident.occurred_at >= start,
            QualityIncident.occurred_at < end,
        ).count()
        monthly.append({"month": start.strftime("%b %Y"), "count": cnt})

    return {
        "by_severity": severity_data,
        "by_defect_category": [{"category": c, "count": n} for c, n in cat_data],
        "by_machine": [{"machine": m, "count": n} for m, n in machine_data],
        "by_line": [{"line": l, "count": n} for l, n in line_data],
        "by_shift": [{"shift": s, "count": n} for s, n in shift_data],
        "corrective_action_effectiveness": eff_data,
        "monthly_trend": monthly,
        "mttr_days": mttr,
    }


# ── Document Upload & Processing ───────────────────────────────────────────────

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    incident_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Save file
    save_path = UPLOAD_DIR / file.filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Resolve incident
    inc = None
    if incident_id:
        inc = db.query(QualityIncident).filter(
            (QualityIncident.id == incident_id) | (QualityIncident.incident_id == incident_id)
        ).first()

    doc = Document(
        filename=file.filename,
        file_path=str(save_path),
        file_type=file.content_type or "unknown",
        file_size=save_path.stat().st_size,
        incident_id=inc.id if inc else None,
        processing_status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Process document
    try:
        extracted_text = await _extract_text(save_path, file.content_type)
        doc.extracted_text = extracted_text[:50000]

        # Count extracted items (simple heuristics)
        doc.extracted_findings = extracted_text.lower().count("finding") + extracted_text.lower().count("inspection")
        doc.extracted_defects = extracted_text.lower().count("defect") + extracted_text.lower().count("non-conformance")
        doc.extracted_root_causes = extracted_text.lower().count("root cause") + extracted_text.lower().count("cause")
        doc.extracted_measurements = extracted_text.lower().count("mm") + extracted_text.lower().count("measurement")
        doc.extracted_corrective_actions = extracted_text.lower().count("corrective") + extracted_text.lower().count("action taken")

        # Generate embedding
        doc.embedding = await get_embedding(extracted_text[:8000])
        doc.processing_status = "done"
        doc.processed_at = datetime.utcnow()

    except Exception as e:
        logger.error(f"Document processing error: {e}")
        doc.processing_status = "error"
        doc.processing_error = str(e)

    db.commit()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "processing_status": doc.processing_status,
        "extracted_findings": doc.extracted_findings,
        "extracted_defects": doc.extracted_defects,
        "extracted_root_causes": doc.extracted_root_causes,
        "extracted_measurements": doc.extracted_measurements,
        "extracted_corrective_actions": doc.extracted_corrective_actions,
    }


async def _extract_text(path: Path, content_type: str) -> str:
    """Extract text from uploaded documents."""
    try:
        if content_type == "application/pdf" or str(path).endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        elif content_type in ("text/csv", "application/csv") or str(path).endswith(".csv"):
            import pandas as pd
            df = pd.read_csv(str(path))
            return df.to_string()

        elif str(path).endswith((".xlsx", ".xls")):
            import pandas as pd
            df = pd.read_excel(str(path))
            return df.to_string()

        else:
            # Try reading as plain text
            return path.read_text(encoding="utf-8", errors="ignore")

    except Exception as e:
        return f"[Extraction error: {e}]"


@app.get("/api/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(desc(Document.uploaded_at)).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "processing_status": d.processing_status,
            "incident_id": d.incident.incident_id if d.incident else None,
            "extracted_findings": d.extracted_findings,
            "extracted_defects": d.extracted_defects,
            "extracted_root_causes": d.extracted_root_causes,
            "extracted_measurements": d.extracted_measurements,
            "extracted_corrective_actions": d.extracted_corrective_actions,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in docs
    ]


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai_provider": "azure" if settings.azure_available else "local",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
