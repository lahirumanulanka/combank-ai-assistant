---
doc_id: ARCH-IAM-001
title: "Identity and Access Architecture"
document_type: architecture
department: security
access_level: confidential
created_date: "2025-11-03"
service: identity
owner_team: identity-platform
tags: [architecture, identity, oidc, sso, key-rotation, hsm]
---
> FICTIONAL MOCK DATA generated for a technical assessment. Not affiliated with any real bank.

# Identity and Access Architecture (CONFIDENTIAL)

## Overview
Staff and customers sign in through one identity provider (IdP) that speaks OpenID Connect (OIDC). Internet
banking, the mobile app and internal tools all trust tokens signed by this IdP.

## Components
- **IdP cluster:** 3 nodes in two data centres, active-active.
- **Signing keys:** RSA 3072-bit keys stored in the hardware security module (HSM).
- **Token lifetime:** access tokens 15 minutes, refresh tokens 8 hours.
- **MFA:** push notification or hardware token, required for staff (see POL-SEC-001 section 4.2).

## Key rotation
Signing keys rotate every 90 days. The new key is published 7 days before it becomes active so that all apps
can download it. The procedure is in RB-IAM-001.

## Known risks
- Some older apps cache the public keys for 30 days and may reject tokens after a rotation.
- Rotation is started by hand; a missed step caused INC-2026-02-27.
