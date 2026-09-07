# Monitoring & Alerting: Camelot-VPS Hub

## 1. Metrics

| Metric | Source | Alert |
|--------|--------|-------|
| RAM Usage | `camelot-vitals` | >90% → SIGSTOP low-priority |
| CPU Usage | `camelot-vitals` | >80% sustained 5min |
| API Latency (P99) | Prometheus | >200ms |
| Error Rate | Gideon | >5% |
| Receipt Chain | Ledger | Hash mismatch |

## 2. Logging

- Structured JSON logs, correlation IDs.
- Redacted PII, tenant-scoped log streams.

## 3. Dashboards

- Grafana: RAM, CPU, latency, error rate, receipt rate.
- HUD: Vitals panel, receipt timeline.
