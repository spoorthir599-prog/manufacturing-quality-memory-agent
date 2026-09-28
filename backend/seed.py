"""
Seed script — generates 100+ realistic manufacturing quality incidents
with recurring patterns for meaningful AI demonstration.
"""
from __future__ import annotations
import asyncio
import random
from datetime import datetime, timedelta
from database import SessionLocal, create_tables
from models import (
    ProductionLine, Machine, Product, Supplier, QualityIncident,
    InspectionFinding, RootCause, CorrectiveAction, User,
    SeverityEnum, IncidentStatusEnum, EffectivenessEnum,
)
from ai_service import get_embedding

random.seed(42)

# ── Reference data ─────────────────────────────────────────────────────────────

LINES = [
    {"name": "Line 1", "description": "Primary CNC machining line", "location": "Building A"},
    {"name": "Line 2", "description": "Welding and fabrication line", "location": "Building A"},
    {"name": "Line 3", "description": "Precision aluminium machining", "location": "Building B"},
    {"name": "Line 4", "description": "Injection moulding line", "location": "Building C"},
    {"name": "Line 5", "description": "Assembly and testing line", "location": "Building C"},
]

MACHINES = [
    {"name": "CNC-01", "machine_type": "CNC Machining Centre", "model": "Haas VF-2", "serial_number": "HV2-00142", "line": "Line 1"},
    {"name": "CNC-02", "machine_type": "CNC Machining Centre", "model": "Haas VF-4", "serial_number": "HV4-00278", "line": "Line 1"},
    {"name": "CNC-03", "machine_type": "CNC Turning Centre", "model": "Mazak QT-200", "serial_number": "MQT-00391", "line": "Line 3"},
    {"name": "CNC-04", "machine_type": "CNC Milling Centre", "model": "DMG MORI DMU 50", "serial_number": "DMU-00184", "line": "Line 3"},
    {"name": "WLD-01", "machine_type": "MIG Welder", "model": "Lincoln Electric Power MIG 350MP", "serial_number": "LNE-00552", "line": "Line 2"},
    {"name": "WLD-02", "machine_type": "TIG Welder", "model": "Miller Dynasty 350", "serial_number": "MLD-00219", "line": "Line 2"},
    {"name": "INJ-01", "machine_type": "Injection Moulding Machine", "model": "Arburg Allrounder 470", "serial_number": "ARB-00076", "line": "Line 4"},
    {"name": "INJ-02", "machine_type": "Injection Moulding Machine", "model": "Engel e-mac 280", "serial_number": "ENG-00134", "line": "Line 4"},
    {"name": "CMM-01", "machine_type": "Coordinate Measuring Machine", "model": "Zeiss Contura 7", "serial_number": "ZSS-00088", "line": "Line 5"},
    {"name": "CVR-01", "machine_type": "Conveyor System", "model": "Dorner 2200 Series", "serial_number": "DRN-00301", "line": "Line 5"},
]

PRODUCTS = [
    {"name": "Aluminium Housing AX-200", "product_code": "AX-200", "category": "Machined Components"},
    {"name": "Mounting Bracket MB-150", "product_code": "MB-150", "category": "Fabricated Parts"},
    {"name": "Drive Shaft DS-400", "product_code": "DS-400", "category": "Machined Components"},
    {"name": "Valve Body VB-100", "product_code": "VB-100", "category": "Machined Components"},
    {"name": "Gear Housing GH-300", "product_code": "GH-300", "category": "Machined Components"},
    {"name": "Pump Casing PC-220", "product_code": "PC-220", "category": "Fabricated Parts"},
    {"name": "Control Panel CP-50", "product_code": "CP-50", "category": "Injection Moulded"},
    {"name": "Cover Plate CV-180", "product_code": "CV-180", "category": "Injection Moulded"},
    {"name": "Bearing Housing BH-260", "product_code": "BH-260", "category": "Machined Components"},
    {"name": "Sensor Bracket SB-120", "product_code": "SB-120", "category": "Fabricated Parts"},
    {"name": "Manifold Assembly MA-350", "product_code": "MA-350", "category": "Assembly"},
    {"name": "End Cap EC-90", "product_code": "EC-90", "category": "Machined Components"},
    {"name": "Coupling Ring CR-140", "product_code": "CR-140", "category": "Machined Components"},
    {"name": "Support Frame SF-500", "product_code": "SF-500", "category": "Fabricated Parts"},
    {"name": "Nozzle Body NB-210", "product_code": "NB-210", "category": "Injection Moulded"},
]

SUPPLIERS = [
    {"name": "Metalworks AG", "code": "SUP-001", "country": "Germany"},
    {"name": "Precision Alloys Ltd", "code": "SUP-002", "country": "UK"},
    {"name": "SteelTech Industries", "code": "SUP-003", "country": "USA"},
    {"name": "PolyForm Solutions", "code": "SUP-004", "country": "Netherlands"},
    {"name": "FastenerWorld GmbH", "code": "SUP-005", "country": "Austria"},
]

SHIFTS = ["Day", "Afternoon", "Night"]
OPERATORS = [
    "John Martinez", "Sarah Chen", "David Okonkwo", "Emma Fischer",
    "Raj Patel", "Maria Santos", "Liu Wei", "Ahmed Hassan",
]
OWNERS = [
    "Alice Thompson", "Bob Nakamura", "Carlos Rivera", "Diana Wu",
    "Edward Kowalski", "Fiona Brennan",
]

# ── Recurring incident patterns ────────────────────────────────────────────────

PATTERNS = [
    # Pattern 1: CNC-03 spindle calibration (most important for demo)
    {
        "machine": "CNC-03",
        "line": "Line 3",
        "product": "AX-200",
        "defect_category": "Dimensional Deviation",
        "title_template": "Mounting hole diameter out of tolerance — {product}",
        "desc_templates": [
            "Mounting hole diameter measured at {val}mm, specification requires {spec}mm ±0.1mm. Deviation of {dev}mm outside tolerance.",
            "CNC machining producing mounting holes with dimensional deviation on {product}. Measured diameter {val}mm vs nominal {spec}mm.",
            "Dimensional deviation detected on mounting hole features. Hole diameter {val}mm exceeds upper tolerance limit by {dev}mm.",
            "Quality inspection failed: mounting hole diameter {dev}mm outside tolerance. Production batch {batch} affected.",
            "Inspection finding: mounting hole diameter deviation of ±{dev}mm on aluminium housing components.",
        ],
        "findings": [
            "Spindle runout measured at 0.08mm — exceeds 0.02mm specification",
            "Tool holder showing signs of wear and vibration",
            "Dimensional deviation consistent with spindle calibration drift",
            "Part measurement: hole Ø24.25mm vs nominal Ø24.00mm",
            "Thermal expansion of spindle bearing detected during production run",
        ],
        "root_causes": [
            "Spindle calibration drift — last calibrated >600 operating hours ago",
            "Spindle calibration drift due to extended operation without recalibration",
            "CNC spindle bearing wear causing calibration deviation",
            "Inadequate preventive maintenance schedule for spindle calibration",
        ],
        "corrective_actions": [
            "Immediate CNC-03 spindle recalibration performed. Preventive calibration schedule set to every 500 operating hours.",
            "Spindle recalibration + replacement of worn tool holder. Calibration log updated.",
            "Full spindle calibration and verification. Added to 500-hour PM schedule.",
            "Emergency recalibration completed. Parts inspected and non-conforming parts quarantined.",
        ],
        "effectiveness": [EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.PARTIALLY_EFFECTIVE],
        "count": 9,
        "val_range": (23.9, 24.35),
        "spec": "24.00",
    },
    # Pattern 2: Welding temperature variation
    {
        "machine": "WLD-01",
        "line": "Line 2",
        "product": "MB-150",
        "defect_category": "Weld Quality",
        "title_template": "Weld porosity / incomplete fusion — {product}",
        "desc_templates": [
            "Weld porosity detected in fillet welds on mounting brackets. Visual inspection reveals gas pockets and incomplete fusion.",
            "MIG welding producing inconsistent bead profile with porosity defects on batch {batch}.",
            "Weld quality failure: incomplete fusion at joint interface. Tensile test showed {dev}% below specification.",
            "Welding defect detected during final inspection: porosity and undercut on fillet welds.",
            "Batch {batch}: weld inspection found multiple porosity defects and irregular bead geometry.",
        ],
        "findings": [
            "Wire feed speed inconsistent — recorded at 8.2 m/min vs 9.5 m/min set point",
            "Shielding gas flow rate below specification: 14 L/min vs 18 L/min required",
            "Welding temperature variation detected: ±35°C from target preheat",
            "Moisture contamination on base material surface",
            "Contact tip wear causing arc instability",
        ],
        "root_causes": [
            "Welding parameter drift — wire feed speed reduction due to drive roll wear",
            "Shielding gas regulator malfunction causing insufficient gas coverage",
            "Preheat temperature not maintained — thermocouple calibration out of date",
            "Base material moisture absorption from improper storage",
        ],
        "corrective_actions": [
            "Replace drive roll assembly and recalibrate wire feed speed. Inspect all welds from affected batch.",
            "Shielding gas regulator replaced and flow rate verified. Welding procedure re-qualified.",
            "Preheat process updated with calibrated temperature monitoring. Storage protocol revised.",
            "Material dried per procedure, storage conditions improved, welds re-inspected.",
        ],
        "effectiveness": [EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.PARTIALLY_EFFECTIVE, EffectivenessEnum.PENDING],
        "count": 8,
        "val_range": (0, 0),
        "spec": "N/A",
    },
    # Pattern 3: Injection moulding pressure
    {
        "machine": "INJ-01",
        "line": "Line 4",
        "product": "CP-50",
        "defect_category": "Injection Moulding Defect",
        "title_template": "Short shot / sink mark — moulding pressure deviation — {product}",
        "desc_templates": [
            "Control panel covers showing short shot defects. Injection pressure dropped below {dev} bar set point.",
            "Sink marks detected on Class-A surface of cover panels. Mould filling incomplete in {dev}% of parts.",
            "Injection moulding defect: short shot on thin-wall sections. Pressure variation during fill phase.",
            "Batch {batch}: multiple parts with sink marks and incomplete fill. Cavity pressure deviation noted.",
            "Surface defects (sink marks, voids) on moulded covers — pressure fluctuation in injection phase.",
        ],
        "findings": [
            "Injection pressure fluctuating ±18 bar from 145 bar set point",
            "Barrel temperature Zone 3 showing deviation: 228°C vs 240°C set",
            "Check valve wear causing backflow during injection",
            "Mould temperature controller malfunction — coolant flow reduced",
            "Resin viscosity variation from new material batch",
        ],
        "root_causes": [
            "Check valve ring wear causing pressure loss during injection stroke",
            "Barrel heater zone failure leading to melt temperature non-uniformity",
            "Mould cooling circuit blockage affecting part solidification",
            "Raw material viscosity deviation from approved supplier specification",
        ],
        "corrective_actions": [
            "Check valve assembly replaced and barrel conditions verified. Process parameters re-validated.",
            "Barrel heater replacement and temperature profile re-established. Sample parts approved.",
            "Mould cooling channels cleaned and flow rate verified. Cycle time adjusted.",
            "Material quarantined, supplier notified. New batch tested and approved before production.",
        ],
        "effectiveness": [EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.PARTIALLY_EFFECTIVE],
        "count": 7,
        "val_range": (0, 0),
        "spec": "N/A",
    },
    # Pattern 4: Sensor calibration
    {
        "machine": "CMM-01",
        "line": "Line 5",
        "product": "DS-400",
        "defect_category": "Measurement System Error",
        "title_template": "CMM measurement inconsistency — sensor calibration — {product}",
        "desc_templates": [
            "CMM measurement results inconsistent between operators. Gauge R&R study shows {dev}% variation.",
            "Drive shaft diameter measurements showing inconsistency. CMM probe calibration suspected.",
            "Measurement system analysis indicates CMM-01 out of calibration — results unreliable.",
            "Quality records showing conflicting measurements for same parts. CMM calibration drift identified.",
            "CMM measurement error: repeated measurements of same feature show {dev}mm variation.",
        ],
        "findings": [
            "CMM probe qualification sphere shows 0.012mm deviation — exceeds 0.005mm limit",
            "Stylus tip wear causing measurement offset",
            "Temperature-induced machine geometry errors during summer months",
            "Probe change repeatability: 0.018mm vs 0.008mm specification",
        ],
        "root_causes": [
            "CMM probe calibration expired — last calibrated 14 months ago (limit: 12 months)",
            "Stylus tip wear beyond acceptable limit causing consistent measurement offset",
            "Environmental temperature fluctuation affecting CMM geometry accuracy",
        ],
        "corrective_actions": [
            "CMM recalibrated by accredited service. New calibration certificate issued. All parts re-measured.",
            "Stylus replaced and probe qualified. Measurement uncertainty re-assessed.",
            "Environmental controls (HVAC) repaired. CMM placed in temperature-controlled area.",
        ],
        "effectiveness": [EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE],
        "count": 6,
        "val_range": (0, 0),
        "spec": "N/A",
    },
    # Pattern 5: Raw material variation
    {
        "machine": "CNC-01",
        "line": "Line 1",
        "product": "GH-300",
        "defect_category": "Material Non-Conformance",
        "title_template": "Raw material hardness / composition deviation — {product}",
        "desc_templates": [
            "Gear housing machining showing excessive tool wear. Material hardness test shows {dev} HB above specification.",
            "Incoming aluminium alloy batch fails hardness test — {dev} HB vs max 95 HB specification.",
            "Material composition deviation detected. Supplier COC values differ from in-house analysis.",
            "Production interrupted: material hardness non-conformance on batch {batch}. Tool life reduced by {dev}%.",
            "Raw material inspection failure: alloy composition outside approved specification — silicon content high.",
        ],
        "findings": [
            "Material hardness: 108 HB vs 75-95 HB specification",
            "Spectrometer analysis: silicon content 12.8% vs max 12.0% specification",
            "Supplier certificate of conformance values not matching in-house verification",
            "Increased cutting forces and tool wear rates during machining",
        ],
        "root_causes": [
            "Supplier material batch deviation — different alloy heat treatment",
            "Supplier quality control failure — out-of-spec material passed inspection",
            "Material traceability breakdown — incorrect batch linked to shipment",
        ],
        "corrective_actions": [
            "Material batch quarantined. Supplier corrective action issued. Incoming inspection enhanced.",
            "Supplier audit conducted. Incoming material testing protocol updated to include hardness and composition.",
            "Alternative approved supplier qualified. Material traceability requirements updated in supplier agreement.",
        ],
        "effectiveness": [EffectivenessEnum.EFFECTIVE, EffectivenessEnum.PARTIALLY_EFFECTIVE, EffectivenessEnum.PENDING],
        "count": 7,
        "val_range": (0, 0),
        "spec": "N/A",
    },
    # Pattern 6: Tool wear
    {
        "machine": "CNC-02",
        "line": "Line 1",
        "product": "VB-100",
        "defect_category": "Surface Finish Defect",
        "title_template": "Surface roughness failure — tool wear — {product}",
        "desc_templates": [
            "Valve body seating surface Ra {dev} µm — exceeds Ra 0.8 µm specification. Tool wear suspected.",
            "Surface finish failure on machined seating surface. Ra measurement {dev} µm vs 0.8 µm limit.",
            "CNC-02 producing components with unacceptable surface roughness. Batch {batch} affected.",
            "Surface quality inspection: Ra {dev} µm on critical seating surface. Tool change required.",
            "Roughness measurement failure: milling insert worn beyond regrind limit after {dev} hours.",
        ],
        "findings": [
            "Tool insert flank wear measured at 0.42mm — exceeds 0.3mm regrind limit",
            "Built-up edge formation on cutting tool edge",
            "Cutting speed reduced by operator to compensate for chatter",
            "Coolant supply partially blocked — thermal damage to tool edge",
        ],
        "root_causes": [
            "Insufficient tool change frequency — tool life limit exceeded",
            "Coolant supply blockage causing tool overheating and accelerated wear",
            "Incorrect cutting parameters for new material batch hardness",
        ],
        "corrective_actions": [
            "Tool change frequency increased from 250 to 180 parts. Tool condition monitoring added to checklist.",
            "Coolant system cleaned and flow rate verified. Tool inserts replaced.",
            "Cutting parameters revised to match material hardness. Process validated.",
        ],
        "effectiveness": [EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE],
        "count": 8,
        "val_range": (0.9, 2.1),
        "spec": "0.8",
    },
    # Pattern 7: Conveyor alignment
    {
        "machine": "CVR-01",
        "line": "Line 5",
        "product": "MA-350",
        "defect_category": "Assembly Defect",
        "title_template": "Conveyor misalignment causing assembly damage — {product}",
        "desc_templates": [
            "Manifold assemblies arriving at station 3 with surface damage. Conveyor belt tracking misaligned.",
            "Assembly damage detected: components impacting side guides due to conveyor belt misalignment.",
            "Batch {batch}: multiple manifold assemblies damaged in transit on assembly line conveyor.",
            "Conveyor belt tracking fault — components contacting belt edges causing scratch marks on finished surfaces.",
            "Surface damage on assembled manifolds traced to conveyor alignment deviation.",
        ],
        "findings": [
            "Conveyor belt tracking offset: 18mm from centreline",
            "Belt tension uneven — left side 15% lower than right side",
            "Guide rail bracket loose at station 2",
            "Belt splice damage causing intermittent height variation",
        ],
        "root_causes": [
            "Conveyor belt tracking drift — adjustment mechanism loose",
            "Uneven belt tension due to worn tensioner spring",
            "Guide rail mounting hardware not torqued to specification during last PM",
        ],
        "corrective_actions": [
            "Conveyor belt re-tracked and tracking locks tightened. Belt tension equalised.",
            "Belt tensioner spring replaced and tracking re-calibrated.",
            "Guide rail brackets re-torqued and thread-locked. PM checklist updated.",
        ],
        "effectiveness": [EffectivenessEnum.EFFECTIVE, EffectivenessEnum.EFFECTIVE, EffectivenessEnum.PARTIALLY_EFFECTIVE],
        "count": 5,
        "val_range": (0, 0),
        "spec": "N/A",
    },
]

# Additional one-off incidents for diversity
ONE_OFF_INCIDENTS = [
    {
        "machine": "WLD-02",
        "line": "Line 2",
        "product": "SF-500",
        "defect_category": "Weld Quality",
        "title": "TIG weld crack detected on support frame",
        "description": "Hairline crack discovered in TIG weld on support frame during dye penetrant inspection. Crack approximately 12mm in length at toe of weld.",
        "finding": "Crack at weld toe consistent with hydrogen-induced cracking. Preheat temperature insufficient.",
        "root_cause": "Insufficient preheat temperature for material thickness — hydrogen embrittlement",
        "corrective_action": "Preheat procedure updated for materials >25mm thickness. All frames re-inspected.",
        "severity": SeverityEnum.HIGH,
    },
    {
        "machine": "INJ-02",
        "line": "Line 4",
        "product": "NB-210",
        "defect_category": "Dimensional Deviation",
        "title": "Nozzle body thread form out of tolerance",
        "description": "Nozzle body threads failing gauge verification. Go/No-go gauge failing on 15% of parts from batch NB-0087.",
        "finding": "Thread pitch diameter 0.12mm undersized. Injection mould cavity showing wear.",
        "root_cause": "Injection mould thread insert wear — exceeded service life",
        "corrective_action": "Mould thread inserts replaced. All nozzle bodies from affected batch re-inspected.",
        "severity": SeverityEnum.MEDIUM,
    },
    {
        "machine": "CNC-04",
        "line": "Line 3",
        "product": "BH-260",
        "defect_category": "Surface Finish Defect",
        "title": "Bearing housing bore surface chatter marks",
        "description": "Chatter marks detected on bearing housing bore. Surface roughness Ra 2.4 µm vs Ra 0.4 µm specification.",
        "finding": "Machine vibration signature indicates spindle bearing play. Resonance at 4,200 RPM.",
        "root_cause": "Spindle bearing wear causing vibration and chatter during boring operation",
        "corrective_action": "Spindle bearing replaced. Vibration analysis performed post-repair. Parts re-inspected.",
        "severity": SeverityEnum.HIGH,
    },
    {
        "machine": "CNC-01",
        "line": "Line 1",
        "product": "EC-90",
        "defect_category": "Dimensional Deviation",
        "title": "End cap outer diameter oversize",
        "description": "End cap outer diameter measuring 45.18mm vs nominal 45.00mm ±0.05mm. Batch EC-0212 affected.",
        "finding": "Offset tool wear compensation not applied after tool change. Program not updated.",
        "root_cause": "Operator error — tool length offset not updated in CNC program after tool change",
        "corrective_action": "Tool offset procedure updated. Mandatory first-article inspection after every tool change added to work instruction.",
        "severity": SeverityEnum.MEDIUM,
    },
    {
        "machine": "CNC-03",
        "line": "Line 3",
        "product": "CR-140",
        "defect_category": "Dimensional Deviation",
        "title": "Coupling ring bore diameter deviation — CNC-03",
        "description": "Coupling ring bore diameter out of tolerance. Measurement shows 50.32mm vs 50.00mm ±0.02mm. Batch CR-0156.",
        "finding": "Same spindle calibration drift pattern as previous mounting hole deviation incidents on CNC-03.",
        "root_cause": "CNC-03 spindle calibration drift — recalibration interval exceeded",
        "corrective_action": "Spindle recalibrated. Calibration verification added to start-of-shift checklist.",
        "severity": SeverityEnum.HIGH,
    },
    {
        "machine": "CMM-01",
        "line": "Line 5",
        "product": "PC-220",
        "defect_category": "Measurement System Error",
        "title": "Pump casing bore measurement anomaly",
        "description": "Pump casing bore measurements showing unexpected variation between CMM and hand gauging. Discrepancy of 0.04mm.",
        "finding": "CMM thermal drift during uncontrolled room temperature event (AC failure).",
        "root_cause": "CMM temperature compensation not active — environmental temperature exceeded specification",
        "corrective_action": "CMM temperature compensation enabled. Environmental alarm set. Re-measurement of all parts in batch.",
        "severity": SeverityEnum.MEDIUM,
    },
]


async def seed():
    create_tables()
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(ProductionLine).count() > 0:
            print("Database already seeded. Skipping.")
            return

        print("Seeding database...")

        # ── Production Lines ──
        line_map: dict[str, ProductionLine] = {}
        for ld in LINES:
            pl = ProductionLine(**ld)
            db.add(pl)
            db.flush()
            line_map[pl.name] = pl
        print(f"  Created {len(LINES)} production lines")

        # ── Machines ──
        machine_map: dict[str, Machine] = {}
        for md in MACHINES:
            m = Machine(
                name=md["name"],
                machine_type=md["machine_type"],
                model=md["model"],
                serial_number=md["serial_number"],
                production_line_id=line_map[md["line"]].id,
                operating_hours=random.uniform(200, 1200),
                last_maintenance_date=datetime.utcnow() - timedelta(days=random.randint(10, 180)),
            )
            db.add(m)
            db.flush()
            machine_map[m.name] = m
        print(f"  Created {len(MACHINES)} machines")

        # ── Products ──
        product_map: dict[str, Product] = {}
        for pd in PRODUCTS:
            p = Product(**pd)
            db.add(p)
            db.flush()
            product_map[p.product_code] = p
        print(f"  Created {len(PRODUCTS)} products")

        # ── Suppliers ──
        supplier_map: dict[str, Supplier] = {}
        for sd in SUPPLIERS:
            s = Supplier(**sd)
            db.add(s)
            db.flush()
            supplier_map[s.code] = s
        print(f"  Created {len(SUPPLIERS)} suppliers")

        # ── Users ──
        for name in set(OWNERS):
            u = User(name=name, email=f"{name.lower().replace(' ', '.')}@qualitymem.com", role="Quality Engineer")
            db.add(u)

        # ── Incidents from patterns ──
        incident_counter = 1000
        all_incidents: list[QualityIncident] = []

        for pattern in PATTERNS:
            machine = machine_map[pattern["machine"]]
            line = line_map[pattern["line"]]
            # Find product by code
            prod_code = pattern["product"]
            product = product_map.get(prod_code)
            
            eff_list = pattern["effectiveness"]
            desc_templates = pattern["desc_templates"]
            finding_list = pattern["findings"]
            rc_list = pattern["root_causes"]
            ca_list = pattern["corrective_actions"]

            for i in range(pattern["count"]):
                incident_counter += 1
                qir_id = f"QIR-{incident_counter}"
                
                # Spread over last 12 months
                days_ago = random.randint(10, 365)
                occurred = datetime.utcnow() - timedelta(days=days_ago)
                
                batch = f"{prod_code}-{random.randint(1000, 9999)}"
                dev = round(random.uniform(0.1, 0.35), 2) if pattern["val_range"][0] else random.randint(8, 25)
                val = round(random.uniform(*pattern["val_range"]), 2) if pattern["val_range"][0] else dev
                spec = pattern["spec"]
                
                title = pattern["title_template"].format(product=prod_code)
                desc_tmpl = desc_templates[i % len(desc_templates)]
                desc = desc_tmpl.format(val=val, spec=spec, dev=dev, batch=batch)

                severity = random.choice([SeverityEnum.MEDIUM, SeverityEnum.HIGH, SeverityEnum.HIGH, SeverityEnum.CRITICAL])
                status = IncidentStatusEnum.RESOLVED if days_ago > 30 else random.choice(
                    [IncidentStatusEnum.OPEN, IncidentStatusEnum.IN_PROGRESS]
                )
                resolved_at = occurred + timedelta(days=random.randint(3, 14)) if status == IncidentStatusEnum.RESOLVED else None

                inc = QualityIncident(
                    incident_id=qir_id,
                    title=title,
                    description=desc,
                    defect_category=pattern["defect_category"],
                    severity=severity,
                    status=status,
                    production_line_id=line.id,
                    machine_id=machine.id,
                    product_id=product.id if product else None,
                    supplier_id=random.choice(list(supplier_map.values())).id,
                    batch_number=batch,
                    quantity_affected=random.randint(5, 200),
                    shift=random.choice(SHIFTS),
                    operator=random.choice(OPERATORS),
                    owner=random.choice(OWNERS),
                    occurred_at=occurred,
                    resolved_at=resolved_at,
                    process_parameters={
                        "spindle_speed": f"{random.randint(2000, 4000)} RPM",
                        "feed_rate": f"{random.randint(200, 600)} mm/min",
                        "coolant_flow": f"{random.randint(8, 20)} L/min",
                    },
                )
                db.add(inc)
                db.flush()

                # Inspection Finding
                f_text = finding_list[i % len(finding_list)]
                finding = InspectionFinding(
                    incident_id=inc.id,
                    finding=f_text,
                    inspector=random.choice(OPERATORS),
                    inspection_date=occurred + timedelta(hours=random.randint(2, 48)),
                )
                db.add(finding)

                # Root Cause (not always identified immediately)
                if random.random() > 0.15:
                    rc_text = rc_list[i % len(rc_list)]
                    rc = RootCause(
                        incident_id=inc.id,
                        category="Machine",
                        description=rc_text,
                        identified_by=random.choice(OWNERS),
                        identified_at=occurred + timedelta(days=random.randint(1, 5)),
                        confidence=random.uniform(0.7, 1.0),
                    )
                    db.add(rc)
                    db.flush()

                    # Corrective Action
                    if status in (IncidentStatusEnum.RESOLVED, IncidentStatusEnum.CLOSED) or random.random() > 0.3:
                        ca_text = ca_list[i % len(ca_list)]
                        eff = eff_list[i % len(eff_list)]
                        ca = CorrectiveAction(
                            incident_id=inc.id,
                            root_cause_id=rc.id,
                            action=ca_text,
                            preventive_action="Updated PM schedule and work instructions.",
                            owner=random.choice(OWNERS),
                            due_date=occurred + timedelta(days=7),
                            completed_date=resolved_at,
                            effectiveness=eff,
                            effectiveness_notes="Verified by follow-up inspection after corrective action.",
                            recurrence_after_action=(eff != EffectivenessEnum.EFFECTIVE),
                        )
                        db.add(ca)

                all_incidents.append(inc)

        # ── One-off incidents ──
        for ood in ONE_OFF_INCIDENTS:
            incident_counter += 1
            qir_id = f"QIR-{incident_counter}"
            days_ago = random.randint(30, 200)
            occurred = datetime.utcnow() - timedelta(days=days_ago)
            machine = machine_map[ood["machine"]]
            line = line_map[ood["line"]]
            prod = product_map.get(ood["product"])
            
            inc = QualityIncident(
                incident_id=qir_id,
                title=ood["title"],
                description=ood["description"],
                defect_category=ood["defect_category"],
                severity=ood["severity"],
                status=IncidentStatusEnum.RESOLVED,
                production_line_id=line.id,
                machine_id=machine.id,
                product_id=prod.id if prod else None,
                supplier_id=random.choice(list(supplier_map.values())).id,
                batch_number=f"BATCH-{random.randint(1000, 9999)}",
                quantity_affected=random.randint(5, 100),
                shift=random.choice(SHIFTS),
                operator=random.choice(OPERATORS),
                owner=random.choice(OWNERS),
                occurred_at=occurred,
                resolved_at=occurred + timedelta(days=random.randint(3, 10)),
            )
            db.add(inc)
            db.flush()

            db.add(InspectionFinding(
                incident_id=inc.id,
                finding=ood["finding"],
                inspector=random.choice(OPERATORS),
                inspection_date=occurred + timedelta(hours=4),
            ))

            rc = RootCause(
                incident_id=inc.id,
                category="Machine",
                description=ood["root_cause"],
                identified_by=random.choice(OWNERS),
                identified_at=occurred + timedelta(days=2),
                confidence=0.9,
            )
            db.add(rc)
            db.flush()

            db.add(CorrectiveAction(
                incident_id=inc.id,
                root_cause_id=rc.id,
                action=ood["corrective_action"],
                owner=random.choice(OWNERS),
                due_date=occurred + timedelta(days=7),
                completed_date=occurred + timedelta(days=random.randint(3, 8)),
                effectiveness=EffectivenessEnum.EFFECTIVE,
            ))
            all_incidents.append(inc)

        db.commit()
        print(f"  Created {len(all_incidents)} quality incidents")

        # ── Generate embeddings ──
        print("  Generating embeddings (this may take a moment)...")
        for i, inc in enumerate(all_incidents):
            text = f"{inc.title} {inc.description} {inc.defect_category}"
            inc.embedding = await get_embedding(text)
            if (i + 1) % 10 == 0:
                db.commit()
                print(f"    Embedded {i+1}/{len(all_incidents)}")

        db.commit()
        print(f"  ✓ Embeddings generated for {len(all_incidents)} incidents")
        print("\nDatabase seeding complete!")
        print(f"Total incidents: {len(all_incidents)}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed())
