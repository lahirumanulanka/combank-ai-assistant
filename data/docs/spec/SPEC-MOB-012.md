---
doc_id: SPEC-MOB-012
title: "Instant Transfer v2"
document_type: spec
department: product
access_level: internal
created_date: "2026-05-02"
service: mobile-payments
owner_team: mobile-squad
tags: [spec, mobile, transfer, idempotency, redis]
---
> FICTIONAL MOCK DATA generated for a technical assessment. Not affiliated with any real bank.

# Instant Transfer v2

## Problem
Customers sometimes get duplicate or rejected transfers when the app retries after a timeout. This happened in
INC-2026-01-15 and INC-2026-05-21.

## Goals
- No duplicate debits, even when the app retries.
- Transfers complete in under 1.5 seconds for 95% of requests.

## Requirements
- R1: Every transfer carries a client-generated idempotency key that is valid for 24 hours.
- R2: Idempotency keys must be stored in a dedicated, persistent Redis cluster with
  `maxmemory-policy noeviction` (decision from MTG-2026-04-ARB).
- R3: p95 end-to-end latency below 1.5 s.
- R4: The app shows a clear status ("processing", "done", "failed") instead of "Please try again".

## Out of scope
- International transfers.
- Changes to daily limits (see PUB-FAQ-001).

## Rollout
Feature flag `instant_transfer_v2`, starting with 5% of users in September 2026.
