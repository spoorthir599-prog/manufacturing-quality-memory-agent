from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, ForeignKey, Boolean, JSON, Enum
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum
import uuid

Base = declarative_base()

def gen_id():
    return str(uuid.uuid4())

# ── Enums ──────────────────────────────────────────────────────────────────────

class SeverityEnum(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

class IncidentStatusEnum(str, enum.Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"

class EffectivenessEnum(str, enum.Enum):
    EFFECTIVE = "Effective"
    PARTIALLY_EFFECTIVE = "Partially Effective"
    INEFFECTIVE = "Ineffective"
    PENDING = "Pending"

# ── Core Lookup Tables ─────────────────────────────────────────────────────────

class ProductionLine(Base):
    __tablename__ = "production_lines"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    incidents = relationship("QualityIncident", back_populates="production_line")
    machines = relationship("Machine", back_populates="production_line")


class Machine(Base):
    __tablename__ = "machines"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False, unique=True)
    machine_type = Column(String)
    model = Column(String)
    serial_number = Column(String)
    production_line_id = Column(String, ForeignKey("production_lines.id"))
    last_maintenance_date = Column(DateTime)
    operating_hours = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    production_line = relationship("ProductionLine", back_populates="machines")
    incidents = relationship("QualityIncident", back_populates="machine")


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    product_code = Column(String, unique=True)
    description = Column(Text)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    incidents = relationship("QualityIncident", back_populates="product")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    code = Column(String, unique=True)
    contact = Column(String)
    country = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    incidents = relationship("QualityIncident", back_populates="supplier")

# ── Core Quality Incident ──────────────────────────────────────────────────────

class QualityIncident(Base):
    __tablename__ = "quality_incidents"

    id = Column(String, primary_key=True, default=gen_id)
    incident_id = Column(String, unique=True, nullable=False)  # QIR-XXXX
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    defect_category = Column(String)
    severity = Column(Enum(SeverityEnum), default=SeverityEnum.MEDIUM)
    status = Column(Enum(IncidentStatusEnum), default=IncidentStatusEnum.OPEN)

    # Relationships
    production_line_id = Column(String, ForeignKey("production_lines.id"))
    machine_id = Column(String, ForeignKey("machines.id"))
    product_id = Column(String, ForeignKey("products.id"))
    supplier_id = Column(String, ForeignKey("suppliers.id"))

    # Production details
    batch_number = Column(String)
    quantity_affected = Column(Integer)
    shift = Column(String)
    operator = Column(String)
    process_parameters = Column(JSON)  # dict of param→value

    # Dates
    occurred_at = Column(DateTime, nullable=False)
    reported_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Owner / assignment
    owner = Column(String)
    
    # AI embedding — stored as JSON array of floats
    embedding = Column(JSON)

    # Relationships
    production_line = relationship("ProductionLine", back_populates="incidents")
    machine = relationship("Machine", back_populates="incidents")
    product = relationship("Product", back_populates="incidents")
    supplier = relationship("Supplier", back_populates="incidents")
    inspection_findings = relationship("InspectionFinding", back_populates="incident", cascade="all, delete-orphan")
    root_causes = relationship("RootCause", back_populates="incident", cascade="all, delete-orphan")
    corrective_actions = relationship("CorrectiveAction", back_populates="incident", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="incident")


class InspectionFinding(Base):
    __tablename__ = "inspection_findings"

    id = Column(String, primary_key=True, default=gen_id)
    incident_id = Column(String, ForeignKey("quality_incidents.id"), nullable=False)
    finding = Column(Text, nullable=False)
    measurement = Column(String)
    specification = Column(String)
    deviation = Column(String)
    inspector = Column(String)
    inspection_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("QualityIncident", back_populates="inspection_findings")


class RootCause(Base):
    __tablename__ = "root_causes"

    id = Column(String, primary_key=True, default=gen_id)
    incident_id = Column(String, ForeignKey("quality_incidents.id"), nullable=False)
    category = Column(String)  # Machine, Method, Material, Man, Measurement, Environment
    description = Column(Text, nullable=False)
    identified_by = Column(String)
    identified_at = Column(DateTime)
    confidence = Column(Float, default=1.0)  # 0-1
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("QualityIncident", back_populates="root_causes")
    corrective_actions = relationship("CorrectiveAction", back_populates="root_cause")


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(String, primary_key=True, default=gen_id)
    incident_id = Column(String, ForeignKey("quality_incidents.id"), nullable=False)
    root_cause_id = Column(String, ForeignKey("root_causes.id"))
    action = Column(Text, nullable=False)
    preventive_action = Column(Text)
    owner = Column(String)
    due_date = Column(DateTime)
    completed_date = Column(DateTime)
    effectiveness = Column(Enum(EffectivenessEnum), default=EffectivenessEnum.PENDING)
    effectiveness_notes = Column(Text)
    recurrence_after_action = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("QualityIncident", back_populates="corrective_actions")
    root_cause = relationship("RootCause", back_populates="corrective_actions")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_id)
    incident_id = Column(String, ForeignKey("quality_incidents.id"), nullable=True)
    filename = Column(String, nullable=False)
    file_path = Column(String)
    file_type = Column(String)
    file_size = Column(Integer)
    extracted_text = Column(Text)
    extracted_findings = Column(Integer, default=0)
    extracted_defects = Column(Integer, default=0)
    extracted_root_causes = Column(Integer, default=0)
    extracted_measurements = Column(Integer, default=0)
    extracted_corrective_actions = Column(Integer, default=0)
    processing_status = Column(String, default="pending")  # pending|processing|done|error
    processing_error = Column(Text)
    embedding = Column(JSON)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

    incident = relationship("QualityIncident", back_populates="documents")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    role = Column(String, default="Engineer")
    department = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
