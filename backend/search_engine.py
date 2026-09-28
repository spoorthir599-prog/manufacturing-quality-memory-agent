"""
Semantic Search Engine — FAISS-based local vector index with hybrid search.
Combines vector similarity + keyword matching + metadata filters.
"""
from __future__ import annotations
import logging
import json
import re
from typing import Optional
import numpy as np
from sqlalchemy.orm import Session
from models import QualityIncident
from ai_service import cosine_similarity

logger = logging.getLogger(__name__)


def _text_for_incident(inc: QualityIncident) -> str:
    """Build a single searchable text blob from all incident fields."""
    parts = [
        inc.title or "",
        inc.description or "",
        inc.defect_category or "",
        inc.shift or "",
    ]
    for finding in (inc.inspection_findings or []):
        parts.append(finding.finding or "")
    for rc in (inc.root_causes or []):
        parts.append(rc.description or "")
    for ca in (inc.corrective_actions or []):
        parts.append(ca.action or "")
    if inc.machine:
        parts.append(inc.machine.name)
    if inc.production_line:
        parts.append(inc.production_line.name)
    if inc.product:
        parts.append(inc.product.name)
    return " ".join(p for p in parts if p).lower()


def _keyword_score(query: str, text: str) -> float:
    """Simple keyword overlap score 0-1."""
    q_words = set(re.findall(r'\w+', query.lower()))
    t_words = set(re.findall(r'\w+', text.lower()))
    if not q_words:
        return 0.0
    overlap = q_words & t_words
    return len(overlap) / len(q_words)


def _incident_to_dict(inc: QualityIncident, similarity_score: float = 0.0) -> dict:
    return {
        "id": inc.id,
        "incident_id": inc.incident_id,
        "title": inc.title,
        "description": inc.description,
        "defect_category": inc.defect_category,
        "severity": inc.severity.value if inc.severity else None,
        "status": inc.status.value if inc.status else None,
        "production_line": inc.production_line.name if inc.production_line else None,
        "machine": inc.machine.name if inc.machine else None,
        "product": inc.product.name if inc.product else None,
        "supplier": inc.supplier.name if inc.supplier else None,
        "batch_number": inc.batch_number,
        "quantity_affected": inc.quantity_affected,
        "shift": inc.shift,
        "occurred_at": inc.occurred_at.isoformat() if inc.occurred_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        "owner": inc.owner,
        "inspection_findings": "; ".join(f.finding for f in inc.inspection_findings) if inc.inspection_findings else "",
        "root_causes": "; ".join(r.description for r in inc.root_causes) if inc.root_causes else "",
        "corrective_actions": "; ".join(c.action for c in inc.corrective_actions) if inc.corrective_actions else "",
        "similarity_score": similarity_score,
    }


def search_incidents(
    db: Session,
    query: str,
    query_embedding: list[float] | None = None,
    top_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """
    Hybrid search: vector similarity + keyword overlap.
    Returns top_k incidents sorted by combined score.
    """
    q = db.query(QualityIncident)

    # Metadata filters
    if filters:
        if filters.get("production_line"):
            from models import ProductionLine
            q = q.join(ProductionLine).filter(
                ProductionLine.name.ilike(f"%{filters['production_line']}%")
            )
        if filters.get("machine"):
            from models import Machine
            q = q.join(Machine).filter(
                Machine.name.ilike(f"%{filters['machine']}%")
            )
        if filters.get("defect_category"):
            q = q.filter(
                QualityIncident.defect_category.ilike(f"%{filters['defect_category']}%")
            )
        if filters.get("severity"):
            q = q.filter(QualityIncident.severity == filters["severity"])
        if filters.get("status"):
            q = q.filter(QualityIncident.status == filters["status"])
        if filters.get("date_from"):
            from datetime import datetime
            q = q.filter(QualityIncident.occurred_at >= datetime.fromisoformat(filters["date_from"]))
        if filters.get("date_to"):
            from datetime import datetime
            q = q.filter(QualityIncident.occurred_at <= datetime.fromisoformat(filters["date_to"]))

    incidents = q.all()
    if not incidents:
        return []

    scored = []
    for inc in incidents:
        # Vector similarity
        vec_score = 0.0
        if query_embedding and inc.embedding:
            vec_score = cosine_similarity(query_embedding, inc.embedding)

        # Keyword score
        text = _text_for_incident(inc)
        kw_score = _keyword_score(query, text)

        # Combined score (weight: 70% vector, 30% keyword)
        combined = 0.7 * vec_score + 0.3 * kw_score
        scored.append((inc, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [_incident_to_dict(inc, score) for inc, score in scored[:top_k] if score > 0.05]


def find_similar_incidents(
    db: Session,
    incident_id: str,
    top_k: int = 8,
) -> list[dict]:
    """Find incidents similar to a given incident."""
    target = db.query(QualityIncident).filter(
        QualityIncident.id == incident_id
    ).first()
    if not target:
        return []

    all_incidents = db.query(QualityIncident).filter(
        QualityIncident.id != incident_id
    ).all()

    scored = []
    for inc in all_incidents:
        score = 0.0
        if target.embedding and inc.embedding:
            score = cosine_similarity(target.embedding, inc.embedding)
        else:
            # Fallback: metadata overlap
            if target.defect_category and inc.defect_category == target.defect_category:
                score += 0.3
            if target.machine_id and inc.machine_id == target.machine_id:
                score += 0.25
            if target.production_line_id and inc.production_line_id == target.production_line_id:
                score += 0.2
            if target.product_id and inc.product_id == target.product_id:
                score += 0.15
        scored.append((inc, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [_incident_to_dict(inc, score) for inc, score in scored[:top_k] if score > 0.05]


def detect_recurring_defects(db: Session) -> list[dict]:
    """
    Detect recurring defect patterns by grouping incidents by
    defect_category + machine combinations.
    """
    from sqlalchemy import func
    from models import Machine

    incidents = db.query(QualityIncident).all()
    
    # Group by defect_category + machine
    patterns: dict[tuple, list] = {}
    for inc in incidents:
        key = (
            inc.defect_category or "Unknown",
            inc.machine.name if inc.machine else "Unknown",
            inc.production_line.name if inc.production_line else "Unknown",
        )
        if key not in patterns:
            patterns[key] = []
        patterns[key].append(inc)

    results = []
    for (defect_cat, machine, line), incs in patterns.items():
        if len(incs) < 2:
            continue
        incs_sorted = sorted(incs, key=lambda x: x.occurred_at or x.created_at)
        first = incs_sorted[0]
        latest = incs_sorted[-1]

        # Most common root cause
        rc_counts: dict[str, int] = {}
        for inc in incs:
            for rc in (inc.root_causes or []):
                rc_counts[rc.description] = rc_counts.get(rc.description, 0) + 1
        top_rc = max(rc_counts, key=rc_counts.get) if rc_counts else None

        # Most common corrective action
        ca_counts: dict[str, int] = {}
        for inc in incs:
            for ca in (inc.corrective_actions or []):
                ca_counts[ca.action] = ca_counts.get(ca.action, 0) + 1
        top_ca = max(ca_counts, key=ca_counts.get) if ca_counts else None

        results.append({
            "defect_category": defect_cat,
            "machine": machine,
            "production_line": line,
            "occurrences": len(incs),
            "first_seen": first.occurred_at.isoformat() if first.occurred_at else None,
            "last_seen": latest.occurred_at.isoformat() if latest.occurred_at else None,
            "incident_ids": [i.incident_id for i in incs],
            "likely_root_cause": top_rc,
            "historical_corrective_action": top_ca,
            "open_count": sum(1 for i in incs if i.status and i.status.value in ("Open", "In Progress")),
        })

    results.sort(key=lambda x: x["occurrences"], reverse=True)
    return results
