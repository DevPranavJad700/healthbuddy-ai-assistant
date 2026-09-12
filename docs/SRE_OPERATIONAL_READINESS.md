# SRE Operational Readiness

## Environments

- Enforce dev/staging/prod parity with immutable deploy artifacts.

## Reliability Practices

- Define SLO/SLI for chat latency, error rate, and safety-path response.
- Track error budgets and escalation thresholds.

## Release Strategy

- Blue/green or canary rollout with automated rollback gates.
- Block release on quality/safety KPI regressions.

## Incident Management

- On-call runbook ownership and escalation tree.
- Post-incident RCA within 48 hours for Sev-1 incidents.

## Graceful Degradation

- Queue user requests during provider outage.
- Return bounded fallback responses with transparent status.
