# Performance Plan: Camelot-VPS Hub

## 1. Load Targets

- **Concurrent Users:** 50 operators.
- **API Throughput:** 1000 req/s.
- **P99 Latency:** <200ms.
- **RAM Cap:** 1.1GB/8GB.

## 2. Stress Tests

- **Scenario 1:** 50 concurrent HUD sessions, 10s refresh.
- **Scenario 2:** 1000 retrieval queries/s, Qdrant + Neo4j.
- **Scenario 3:** 100 SMS/min, Multivoice consent checks.

## 3. Optimization

- **Caching:** Redis for context packets, idempotency keys.
- **Indexing:** Neo4j fulltext, Qdrant payload indexes.
- **Cgroups:** MemoryMax, CPUQuota for all services.
