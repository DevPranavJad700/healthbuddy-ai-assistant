# Deployment Readiness Status

This document tracks what is now implemented in-repo versus what must be completed in your infrastructure.

## Implemented in Repository

1. Security/config hardening

- Production safety checks for weak `SECRET_KEY`, localhost CORS in prod, and SQLite in prod.
- Environment templates include timeout/retry, strict MIME checks, static cache TTL.
- `.env.production` added to `.gitignore`.

2. Runtime/process management

- `gunicorn_conf.py` added.
- `docker-compose.production.yml` with app + postgres + redis + caddy added.
- `deploy/Caddyfile` added with TLS/security headers/compression.
- Liveness/readiness/health probes available (`/api/live`, `/api/ready`, `/api/health`).

3. Data/persistence

- PostgreSQL-ready config template and compose service included.
- Persistent volumes defined for app data/postgres/redis.
- Backup/restore scripts already present in `scripts/`.

4. Observability/reliability

- Structured request logging with request id and latency.
- Request logs include subject/session correlation (`subject`, `session_id`) when available.
- Prometheus metrics endpoint added (`/api/metrics`).
- Provider failure and fallback counters added.
- LLM timeout + retry/backoff policy added.
- Startup provider connectivity checks added (configurable fail-fast mode).

5. Security/abuse controls

- API rate limiting and request-size limits already enforced.
- Upload hardening: strict MIME type checks + basic file signature validation.

6. CI/CD quality gates

- Workflow added: tests, lint gate, Bandit, pip-audit, Docker build, Trivy scan, smoke test.
- Post-deploy smoke script added (`tests/smoke_post_deploy.py`).

7. Product readiness

- Provider outage user-facing message improved.
- Privacy notice page (`/privacy`) and consent flow in frontend added.
- Analytics dashboard extended with provider failures/fallback responses/error rate.
- Retention/deletion workflow documented (`docs/DATA_RETENTION_AND_DELETION.md`).
- Release and rollback checklist documented (`docs/RELEASE_AND_ROLLBACK_CHECKLIST.md`).
- Terms of use page added (`/terms`).

8. Operations alerts and retention

- Prometheus alert rules template added (`deploy/prometheus-alert-rules.yml`).
- Retention purge script added (`scripts/purge_expired_data.py`).

## Required External Actions (Manual)

1. Rotate Groq key immediately in Groq Console and update deployment secret store.
2. Store secrets in deployment platform secret manager (not in files).
3. Set real production domains in `CORS_ORIGINS` and reverse proxy host config.
4. Provision managed PostgreSQL/Redis and update `DATABASE_URL`/`REDIS_URL`.
5. Configure DNS + TLS certificates for your production domain.
6. Configure alerting from metrics (5xx, latency p95, provider failures).
7. Add legal/privacy policy text review and compliance approval.
