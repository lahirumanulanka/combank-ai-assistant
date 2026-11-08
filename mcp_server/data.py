from scripts.generate_incidents import INCIDENTS

BANNER = "FICTIONAL MOCK DATA for a technical assessment. Not affiliated with any real bank."

EMPLOYEES = [
    {"id": "E1001", "name": "Nadeesha Fernando", "team": "payments-platform", "role": "Engineering Manager",
     "email": "nadeesha.f@example-bank.test", "on_call_for": []},
    {"id": "E1002", "name": "Kasun Jayasinghe", "team": "payments-platform", "role": "Senior SRE",
     "email": "kasun.j@example-bank.test", "on_call_for": ["payment-gateway"]},
    {"id": "E1003", "name": "Dilini Perera", "team": "payments-platform", "role": "Software Engineer",
     "email": "dilini.p@example-bank.test", "on_call_for": ["card-switch"]},
    {"id": "E1004", "name": "Ruwan Silva", "team": "platform-engineering", "role": "Staff Engineer",
     "email": "ruwan.s@example-bank.test", "on_call_for": ["core-banking-adapter"]},
    {"id": "E1005", "name": "Ishara Wickramasinghe", "team": "platform-engineering", "role": "SRE",
     "email": "ishara.w@example-bank.test", "on_call_for": ["api-gateway"]},
    {"id": "E1006", "name": "Tharindu Bandara", "team": "information-security", "role": "Security Engineer",
     "email": "tharindu.b@example-bank.test", "on_call_for": [], "owns": "TLS and mTLS certificates"},
    {"id": "E1007", "name": "Sachini Gunawardena", "team": "information-security", "role": "CISO Office Lead",
     "email": "sachini.g@example-bank.test", "on_call_for": []},
    {"id": "E1008", "name": "Pradeep Rathnayake", "team": "mobile-squad", "role": "Mobile Lead",
     "email": "pradeep.r@example-bank.test", "on_call_for": ["mobile-payments"]},
    {"id": "E1009", "name": "Hasini Kumari", "team": "identity-platform", "role": "Identity Engineer",
     "email": "hasini.k@example-bank.test", "on_call_for": ["identity"]},
    {"id": "E1010", "name": "Chamara Dissanayake", "team": "data-platform", "role": "Data Engineer",
     "email": "chamara.d@example-bank.test", "on_call_for": ["data-platform"]},
    {"id": "E1011", "name": "Amaya Senanayake", "team": "platform-engineering", "role": "ML Engineer",
     "email": "amaya.s@example-bank.test", "on_call_for": ["knowledge-assistant"]},
    {"id": "E1012", "name": "Lahiru Abeysekara", "team": "operations", "role": "Incident Commander",
     "email": "lahiru.a@example-bank.test", "on_call_for": []},
]

SERVICES = [
    {"name": "payment-gateway", "owner_team": "payments-platform", "tier": 1,
     "depends_on": ["card-switch", "core-banking-adapter", "redis-idempotency"], "related_docs": ["RB-SEC-001"]},
    {"name": "card-switch", "owner_team": "payments-platform", "tier": 1,
     "depends_on": ["core-banking-adapter"], "related_docs": ["RB-SEC-001"]},
    {"name": "core-banking-adapter", "owner_team": "platform-engineering", "tier": 1,
     "depends_on": ["core-banking-system"], "related_docs": ["ARCH-CORE-001"]},
    {"name": "mobile-payments", "owner_team": "mobile-squad", "tier": 1,
     "depends_on": ["payment-gateway", "redis-idempotency"], "related_docs": ["SPEC-MOB-012"]},
    {"name": "identity", "owner_team": "identity-platform", "tier": 1,
     "depends_on": ["hsm"], "related_docs": ["ARCH-IAM-001"]},
    {"name": "api-gateway", "owner_team": "platform-engineering", "tier": 1,
     "depends_on": ["identity"], "related_docs": []},
    {"name": "data-platform", "owner_team": "data-platform", "tier": 3,
     "depends_on": ["core-banking-system"], "related_docs": []},
    {"name": "knowledge-assistant", "owner_team": "platform-engineering", "tier": 3,
     "depends_on": ["api-gateway"], "related_docs": []},
]

INCIDENT_RECORDS = [
    {"id": incident.doc_id, "date": incident.date, "service": incident.service, "severity": incident.severity,
     "status": "closed", "duration_min": incident.duration_min}
    for incident in INCIDENTS
]
