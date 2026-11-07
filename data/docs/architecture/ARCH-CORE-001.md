---
doc_id: ARCH-CORE-001
title: "Core Banking Adapter and Connection Pooling"
document_type: architecture
department: platform
access_level: internal
created_date: "2025-08-20"
service: core-banking-adapter
owner_team: platform-engineering
tags: [architecture, core-banking, adapter, connection-pool, batch]
---
> FICTIONAL MOCK DATA generated for a technical assessment. Not affiliated with any real bank.

# Core Banking Adapter and Connection Pooling

## Purpose
The core banking adapter sits between payment services and the core banking system. It translates modern API
calls into the core system's protocol over a fixed set of persistent connections.

## Consumers
- Online payment API (payment-gateway)
- Card-switch settlement
- Reconciliation batch (nightly and month-end)

## Connection pooling
- Pool size: 64 connections per adapter, static, configured in `adapter.yaml`.
- Default deployment: 4 replicas.
- Connection timeout: 2 seconds; request timeout: 8 seconds.
- When all connections are busy the adapter logs `ERR_CONN_POOL_EXHAUSTED` and new requests wait in a queue.

## Known risks
- No workload isolation: batch jobs and online traffic share one pool. Under peak load, online requests may
  starve while batch jobs hold connections. Raised in MTG-2026-01-PAY.
- Pool size is not autoscaled; replicas must be added manually by the on-call engineer.
- The pool size has not been reviewed since 2024.

## Planned improvements
1. Dynamic pool sizing with a guaranteed floor for online payments.
2. A dedicated adapter instance for batch workloads.
