---
doc_id: RB-SEC-001
title: "Certificate Renewal and Rotation"
document_type: runbook
department: security
access_level: internal
created_date: "2025-10-12"
service: payment-gateway
owner_team: information-security
tags: [runbook, certificate, tls, mtls, renewal, expiry]
---
> FICTIONAL MOCK DATA generated for a technical assessment. Not affiliated with any real bank.

# Certificate Renewal and Rotation

## Scope
TLS and mTLS certificates for payment-gateway, card-switch scheme links, partner connections (for example PayHub)
and the internal service mesh.

## Renewal procedure (manual)
1. 30 days before expiry, the certificate owner opens a change request. Expiry dates are tracked in the
   "Cert Register" spreadsheet.
2. Generate a CSR on the HSM-backed key (see RB-SEC-002 for HSM access, restricted).
3. Submit the CSR to the internal CA or the partner's CA.
4. Install the new certificate in staging and run the handshake test.
5. Deploy to production in the approved change window and confirm traffic is healthy.

## Symptoms of an expired certificate
- Logs show `SSL handshake failed` or `certificate has expired`.
- Partner or scheme traffic drops to zero while internal health checks still pass.

## Known gaps
- No automated expiry alerting. Three incidents were caused by expired certificates
  (INC-2025-12-02, INC-2026-04-03, INC-2026-07-21).
- The Cert Register is updated by hand and is often out of date.
