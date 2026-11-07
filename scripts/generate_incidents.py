import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

BANNER = "> FICTIONAL MOCK DATA generated for a technical assessment. Not affiliated with any real bank."


@dataclass(frozen=True)
class Incident:
    doc_id: str
    title: str
    service: str
    severity: str
    root_cause: str
    start: str
    duration_min: int
    detail: str
    impact: str
    actions: list[str]
    tags: list[str]
    payment_related: bool = True
    department: str = "payments"
    access_level: str = "internal"
    owner_team: str = "payments-platform"

    @property
    def date(self) -> str:
        return self.doc_id.removeprefix("INC-")


ROOT_CAUSE_TEXT = {
    "connection_pool_exhaustion": (
        "{detail} pushed the core banking adapter's fixed pool of 64 connections to 64/64. Online payment "
        "requests queued until they timed out and the adapter logged `ERR_CONN_POOL_EXHAUSTED`. Batch jobs and "
        "online traffic share the same pool with no isolation (see ARCH-CORE-001 \"Known risks\")."
    ),
    "expired_tls_certificate": (
        "{detail} expired. Certificates are renewed by hand using the Cert Register spreadsheet and there is no "
        "automated expiry alert, so nobody noticed in time. Connections failed with "
        "`SSL handshake failed: certificate has expired` (see RB-SEC-001 \"Known gaps\")."
    ),
    "idempotency_cache_eviction": (
        "Idempotency keys are stored in a shared Redis cluster with `maxmemory-policy allkeys-lru`. {detail} "
        "caused keys to be evicted early, so retried requests were not recognised: some transfers were posted "
        "twice and others were rejected with `IDEMPOTENCY_KEY_NOT_FOUND`."
    ),
    "config_drift_deployment": (
        "{detail} Staging and production configuration had drifted apart because environment settings are "
        "edited by hand, and the difference was not caught before release."
    ),
    "key_rotation_failure": (
        "{detail} The new signing key became active before all apps had downloaded it, so tokens were rejected "
        "with `invalid_signature` (see ARCH-IAM-001)."
    ),
    "disk_full": "{detail} The ETL worker disk filled up and jobs failed with `No space left on device`.",
    "quota_exhausted": (
        "{detail} The pilot used its whole monthly LangSmith trace quota and tracing calls failed with "
        "`429 quota exceeded`."
    ),
}

FIRST_SYMPTOM = {
    "connection_pool_exhaustion": "p99 latency rises above 8 s and timeouts begin.",
    "expired_tls_certificate": "Error rate jumps; logs show `SSL handshake failed`.",
    "idempotency_cache_eviction": "Customers report duplicate or failed transfers.",
    "config_drift_deployment": "Decline rate rises shortly after a deployment.",
    "key_rotation_failure": "Login failures spike on internet banking and the mobile app.",
    "disk_full": "Nightly ETL jobs stop making progress.",
    "quota_exhausted": "Assistant traces stop appearing in LangSmith.",
}

FOLLOW_UPS = {
    "connection_pool_exhaustion": [
        "Dynamic pool sizing with a guaranteed floor for online traffic (owner: platform-engineering).",
        "Run batch jobs on a dedicated adapter instance.",
        "Load test at 3x baseline before peak days.",
    ],
    "expired_tls_certificate": [
        "Automated certificate rotation with 30-day expiry alerts (owner: information-security).",
        "Weekly scan for certificates that expire within 45 days.",
    ],
    "idempotency_cache_eviction": [
        "Move idempotency keys to a dedicated Redis cluster with `noeviction` and persistence.",
        "Alert when Redis starts evicting keys.",
    ],
    "config_drift_deployment": [
        "Keep environment configuration as code in git.",
        "Add an automated drift check between staging and production.",
    ],
    "key_rotation_failure": [
        "Publish new signing keys 7 days before they become active.",
        "Automate the rotation steps in RB-IAM-001.",
    ],
    "disk_full": ["Alert when disk usage passes 80%.", "Clean up temporary ETL files automatically."],
    "quota_exhausted": ["Alert at 80% of the trace quota.", "Sample traces in non-production environments."],
}

INCIDENTS = [
    Incident(
        doc_id="INC-2025-09-30",
        title="Card authorization failures - September month-end",
        service="card-switch", severity="SEV2", root_cause="connection_pool_exhaustion",
        start="19:40", duration_min=65,
        detail="The month-end settlement batch",
        impact="About 9% of card authorizations were declined for 65 minutes; 4,100 card payments failed.",
        actions=["Paused the settlement batch.", "Added 2 adapter replicas."],
        tags=["payments", "cards", "outage", "connection-pool", "month-end"],
    ),
    Incident(
        doc_id="INC-2025-11-18",
        title="Card authorization timeouts during evening peak",
        service="card-switch", severity="SEV2", root_cause="connection_pool_exhaustion",
        start="20:10", duration_min=50,
        detail="The evening shopping peak together with a delayed nightly batch",
        impact="Card authorizations slowed to 9 seconds; merchants saw about 2,800 declines.",
        actions=["Stopped the delayed batch.", "Scaled adapter replicas from 4 to 6."],
        tags=["payments", "cards", "timeout", "connection-pool"],
    ),
    Incident(
        doc_id="INC-2025-12-02",
        title="Partner gateway TLS handshake failures (PayHub)",
        service="payment-gateway", severity="SEV3", root_cause="expired_tls_certificate",
        start="08:30", duration_min=95,
        detail="The client certificate for the PayHub partner connection",
        impact="Bill payments through PayHub failed for 95 minutes; about 1,200 payments were delayed.",
        actions=["Requested an emergency certificate from PayHub.", "Installed the new certificate."],
        tags=["payments", "partner", "payhub", "certificate", "tls"],
    ),
    Incident(
        doc_id="INC-2025-12-24",
        title="Christmas Eve payment failures - gateway unresponsive",
        service="payment-gateway", severity="SEV1", root_cause="connection_pool_exhaustion",
        start="18:00", duration_min=110,
        detail="Christmas Eve traffic at 3.1x baseline together with the year-end reconciliation batch",
        impact="About 35% of payments failed for almost 2 hours; 14,900 transactions failed and many customers "
               "complained on social media. Post-incident review: MTG-2026-02-PIR.",
        actions=["Paused the reconciliation batch.", "Scaled adapter replicas from 4 to 10.",
                 "Restarted stuck gateway pods."],
        tags=["payments", "outage", "connection-pool", "christmas", "peak"],
    ),
    Incident(
        doc_id="INC-2026-01-15",
        title="Duplicate and failed fund transfers in mobile app",
        service="mobile-payments", severity="SEV2", root_cause="idempotency_cache_eviction",
        start="12:20", duration_min=80,
        detail="A memory spike from a promotional campaign cache",
        impact="312 customers were debited twice and 1,050 transfers were wrongly rejected; all duplicates "
               "were refunded within 2 days.",
        actions=["Flushed the campaign cache.", "Reversed the duplicate debits."],
        tags=["payments", "mobile", "duplicate", "redis", "idempotency"],
        owner_team="mobile-squad",
    ),
    Incident(
        doc_id="INC-2026-02-09",
        title="Elevated declines after release 4.12",
        service="payment-gateway", severity="SEV3", root_cause="config_drift_deployment",
        start="10:05", duration_min=140,
        detail="Release 4.12 turned on the `strict_cvv` feature flag in production only.",
        impact="Card-not-present payments were declined three times more often than normal for over 2 hours.",
        actions=["Turned off `strict_cvv` in production.", "Compared staging and production flags."],
        tags=["payments", "release", "feature-flag", "declines", "config"],
    ),
    Incident(
        doc_id="INC-2026-02-27",
        title="Internet banking login outage - IdP signing key",
        service="identity", severity="SEV1", root_cause="key_rotation_failure",
        start="07:45", duration_min=70,
        detail="A planned signing key rotation skipped the 7-day pre-publish step.",
        impact="Customers could not log in to internet banking or the mobile app for 70 minutes.",
        actions=["Rolled back to the previous signing key.", "Re-published the new key."],
        tags=["identity", "login", "outage", "key-rotation"],
        payment_related=False, department="security", access_level="confidential",
        owner_team="identity-platform",
    ),
    Incident(
        doc_id="INC-2026-03-14",
        title="Payment gateway timeouts during salary-day peak",
        service="payment-gateway", severity="SEV2", root_cause="connection_pool_exhaustion",
        start="17:05", duration_min=75,
        detail="Salary-day traffic at 2.4x baseline while the reconciliation batch held 40+ connections",
        impact="About 18% of API payments timed out; 2,340 transactions failed and the contact centre "
               "received 212 calls. No financial loss.",
        actions=["Scaled adapter replicas from 4 to 8.", "Paused the reconciliation batch."],
        tags=["payments", "outage", "timeout", "connection-pool", "salary-day"],
    ),
    Incident(
        doc_id="INC-2026-04-03",
        title="Card scheme connection certificate expiry",
        service="card-switch", severity="SEV2", root_cause="expired_tls_certificate",
        start="00:05", duration_min=55,
        detail="The mTLS certificate for one of the two card scheme links",
        impact="Half of international card authorizations failed for 55 minutes.",
        actions=["Moved traffic to the second scheme link.", "Installed a renewed certificate."],
        tags=["payments", "cards", "certificate", "mtls", "scheme"],
    ),
    Incident(
        doc_id="INC-2026-05-05",
        title="Nightly ETL delay - data platform",
        service="data-platform", severity="SEV3", root_cause="disk_full",
        start="02:00", duration_min=240,
        detail="A new audit log table doubled the size of the nightly extracts.",
        impact="Morning management reports were 4 hours late. No customer impact.",
        actions=["Freed disk space on the ETL workers.", "Re-ran the failed jobs."],
        tags=["data-platform", "etl", "delay", "disk"],
        payment_related=False, department="platform", owner_team="data-platform",
    ),
    Incident(
        doc_id="INC-2026-05-21",
        title="Bill payment failures - idempotency cache eviction",
        service="mobile-payments", severity="SEV3", root_cause="idempotency_cache_eviction",
        start="19:30", duration_min=45,
        detail="Month-end bill payment volume that filled Redis memory",
        impact="About 900 bill payments were rejected and 40 were posted twice; all were fixed the next day.",
        actions=["Increased Redis memory.", "Reversed the duplicate payments."],
        tags=["payments", "mobile", "bill-payment", "redis", "idempotency"],
        owner_team="mobile-squad",
    ),
    Incident(
        doc_id="INC-2026-06-30",
        title="Quarter-end batch starves online payment connections",
        service="core-banking-adapter", severity="SEV2", root_cause="connection_pool_exhaustion",
        start="21:15", duration_min=60,
        detail="The quarter-end interest batch, which opened 50 connections,",
        impact="Online payments failed or slowed for an hour; about 3,600 transactions failed.",
        actions=["Throttled the interest batch.", "Added 3 adapter replicas."],
        tags=["payments", "core-banking", "batch", "connection-pool", "quarter-end"],
        department="platform", owner_team="platform-engineering",
    ),
    Incident(
        doc_id="INC-2026-07-21",
        title="Internal mTLS certificate expiry - API payments down 42 minutes",
        service="payment-gateway", severity="SEV1", root_cause="expired_tls_certificate",
        start="09:14", duration_min=42,
        detail="The internal mTLS certificate between payment-gateway and the core banking adapter, which was "
               "missing from the Cert Register,",
        impact="All API payments failed for 42 minutes; about 31,000 payment attempts were rejected before "
               "posting. Post-incident review: MTG-2026-07-PIR.",
        actions=["Issued an emergency certificate from the internal CA.", "Deployed it to all gateway pods."],
        tags=["payments", "outage", "certificate", "mtls", "expiry"],
    ),
    Incident(
        doc_id="INC-2026-08-12",
        title="Misconfigured retry policy after infrastructure migration",
        service="payment-gateway", severity="SEV3", root_cause="config_drift_deployment",
        start="14:40", duration_min=90,
        detail="After the move to the new Kubernetes cluster the gateway retry policy was 0 retries in "
               "production, while staging still had 3.",
        impact="Short network blips turned into failed payments; about 1,700 payments failed.",
        actions=["Restored the retry policy.", "Audited all migrated configuration values."],
        tags=["payments", "migration", "retry", "config"],
    ),
    Incident(
        doc_id="INC-2026-09-27",
        title="Redis failover evicts idempotency keys - duplicate debits",
        service="mobile-payments", severity="SEV2", root_cause="idempotency_cache_eviction",
        start="11:05", duration_min=35,
        detail="A Redis primary failover followed by memory pressure on the new primary",
        impact="528 customers were debited twice; all were refunded within 24 hours.",
        actions=["Paused instant transfers for 10 minutes.", "Reversed the duplicate debits."],
        tags=["payments", "mobile", "duplicate", "redis", "failover"],
        owner_team="mobile-squad",
    ),
    Incident(
        doc_id="INC-2026-10-08",
        title="Knowledge assistant pilot - LangSmith quota exhausted",
        service="knowledge-assistant", severity="SEV4", root_cause="quota_exhausted",
        start="15:00", duration_min=300,
        detail="Load testing of the assistant pilot sent 10 times more traces than planned.",
        impact="No customer impact. Assistant traces were missing for 5 hours.",
        actions=["Turned off tracing for load tests.", "Raised the monthly quota."],
        tags=["knowledge-assistant", "langsmith", "quota", "observability"],
        payment_related=False, department="platform", owner_team="platform-engineering",
    ),
]


def timeline(incident: Incident) -> list[str]:
    start = datetime.strptime(f"{incident.date} {incident.start}", "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=incident.duration_min)
    fix_time = start + timedelta(minutes=incident.duration_min * 2 // 3)

    def at(moment: datetime) -> str:
        return moment.strftime("%H:%M")

    lines = [
        f"{at(start)} - {FIRST_SYMPTOM[incident.root_cause]}",
        f"{at(start + timedelta(minutes=4))} - Alert fires; on-call engineer acknowledges.",
        f"{at(start + timedelta(minutes=7))} - Incident declared {incident.severity}.",
    ]
    lines += [f"{at(fix_time)} - {action}" for action in incident.actions]
    lines.append(f"{at(end)} - Incident resolved; monitoring continued for 2 hours.")
    return lines


def render(incident: Incident) -> str:
    root_cause = ROOT_CAUSE_TEXT[incident.root_cause].format(detail=incident.detail)
    timeline_md = "\n".join(f"- {line}" for line in timeline(incident))
    follow_ups_md = "\n".join(f"{i}. {item}" for i, item in enumerate(FOLLOW_UPS[incident.root_cause], 1))
    tags = ", ".join(incident.tags)

    return f"""---
doc_id: {incident.doc_id}
title: "{incident.title}"
document_type: incident
department: {incident.department}
access_level: {incident.access_level}
created_date: "{incident.date}"
service: {incident.service}
severity: {incident.severity}
owner_team: {incident.owner_team}
tags: [{tags}]
---
{BANNER}

# {incident.title}

**Incident ID:** {incident.doc_id} · **Severity:** {incident.severity} · **Service:** {incident.service} · \
**Date:** {incident.date} · **Duration:** {incident.duration_min} minutes

## Timeline
{timeline_md}

## Impact
{incident.impact}

## Root cause
{root_cause}

## Resolution
{" ".join(incident.actions)}

## Follow-up actions
{follow_ups_md}
"""


def ground_truth() -> dict:
    return {
        incident.doc_id: {
            "date": incident.date,
            "service": incident.service,
            "severity": incident.severity,
            "root_cause": incident.root_cause,
            "payment_related": incident.payment_related,
        }
        for incident in INCIDENTS
    }


def main(data_dir: Path = Path("data")) -> None:
    incident_dir = data_dir / "docs" / "incident"
    incident_dir.mkdir(parents=True, exist_ok=True)

    for incident in INCIDENTS:
        (incident_dir / f"{incident.doc_id}.md").write_text(render(incident))

    (data_dir / "ground_truth.json").write_text(json.dumps(ground_truth(), indent=2) + "\n")
    print(f"Wrote {len(INCIDENTS)} incidents to {incident_dir} and ground truth to {data_dir / 'ground_truth.json'}")


if __name__ == "__main__":
    main()
