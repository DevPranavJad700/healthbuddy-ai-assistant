# HealthBuddy AI Operator Runbook

## Required Environment Variables

- `ENVIRONMENT`
- `SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_MINUTES`
- `DATABASE_URL`
- `CORS_ORIGINS`
- `MAX_REQUEST_SIZE_MB`
- `UPLOAD_MAX_SIZE_MB`
- `RATE_LIMIT_REQUESTS_PER_MINUTE`
- `RATE_LIMIT_ROUTE_OVERRIDES`
- `AUTH_MAX_ATTEMPTS`
- `AUTH_LOCKOUT_MINUTES`
- `AUTH_MIN_PASSWORD_LENGTH`
- `DEFAULT_INPUT_TOKENS_PER_CHAR`
- `DEFAULT_OUTPUT_TOKENS_PER_CHAR`
- `COST_RATE_INPUT_PER_1K_TOKENS_USD`
- `COST_RATE_OUTPUT_PER_1K_TOKENS_USD`
- `RESPONSE_CACHE_TTL_SECONDS`
- `RESPONSE_CACHE_MAX_ENTRIES`
- `DB_AUTO_CREATE_ON_STARTUP`
- `DB_RUN_MIGRATIONS_ON_STARTUP`
- `LLM_PROVIDER`
- `LLM_MODEL`
- `STARTUP_PROVIDER_CONNECTIVITY_CHECK`
- `STARTUP_PROVIDER_CHECK_FAIL_FAST`
- `EMBEDDING_MODEL`
- `CHROMA_DB_PATH`
- `CHROMA_COLLECTION_NAME`

## Safe Defaults

- `ENVIRONMENT=production`
- `SECRET_KEY` at least 32 random characters
- `CORS_ORIGINS` restricted to known frontend domains
- `MAX_REQUEST_SIZE_MB=10`
- `UPLOAD_MAX_SIZE_MB=8`
- `RATE_LIMIT_REQUESTS_PER_MINUTE=90`
- `RATE_LIMIT_ROUTE_OVERRIDES=/api/v1/auth/login=10,/api/v1/chat=60`
- `AUTH_MAX_ATTEMPTS=5`
- `AUTH_LOCKOUT_MINUTES=15`
- `AUTH_MIN_PASSWORD_LENGTH=10`
- `DEFAULT_INPUT_TOKENS_PER_CHAR=0.25`
- `DEFAULT_OUTPUT_TOKENS_PER_CHAR=0.25`
- `COST_RATE_INPUT_PER_1K_TOKENS_USD=0.0005`
- `COST_RATE_OUTPUT_PER_1K_TOKENS_USD=0.0015`
- `RESPONSE_CACHE_TTL_SECONDS=120`
- `RESPONSE_CACHE_MAX_ENTRIES=1000`
- `ACCESS_TOKEN_EXPIRE_MINUTES=30` in production
- `REFRESH_TOKEN_EXPIRE_MINUTES=10080` in production
- `DB_AUTO_CREATE_ON_STARTUP=false` in staging/production
- `DB_RUN_MIGRATIONS_ON_STARTUP=true` in staging/production

## Startup Verification Steps

1. Start server:
   - Linux production: `gunicorn app.main:app -c gunicorn_conf.py`
   - Local fallback: `python -m uvicorn app.main:app --app-dir . --host 0.0.0.0 --port 8000`
2. Check liveness:
   - `GET /api/live` must return `200`
3. Check health:
   - `GET /api/health` must return `200`
4. Check readiness:
   - `GET /api/ready` must return `200`
5. Check metrics:
   - `GET /api/metrics` must return Prometheus text payload
6. Confirm request tracing:
   - Response headers include `X-Request-ID`
7. Confirm no startup security validation errors in logs
8. Confirm auth abuse monitor for admins:
   - `GET /api/v1/auth/protection-status` returns `200` for admin token
9. Confirm provider connectivity check result in startup logs

## Reverse Proxy and TLS

1. Use Caddy or Nginx in front of FastAPI.
2. Enforce TLS termination at the proxy.
3. Enable gzip/zstd compression and security headers.
4. Configure request size limits at proxy and app layers.
5. Keep `/api/live`, `/api/health`, and `/api/ready` reachable for platform probes.

## Persistent Storage

1. Use managed PostgreSQL for `DATABASE_URL` in production.
2. Use persistent volumes/object storage for:
   - `data/chroma_db`
   - `data/knowledge_base`
   - uploaded documents if retained
3. Schedule backups and test restore monthly.

## Backup and Integrity Operations

1. Create backup:
   - `powershell -File scripts/backup_data.ps1`
2. Restore backup:
   - `powershell -File scripts/restore_data.ps1 -BackupDir ./backups/healthbuddy_YYYYMMDD_HHMMSS`
3. Integrity checks:
   - `python scripts/check_data_integrity.py`
4. Retention purge:
   - `python scripts/purge_expired_data.py`

## Data Retention and Deletion

1. Follow the retention/deletion playbook in `docs/DATA_RETENTION_AND_DELETION.md`.
2. Document each deletion run with operator, timestamp, and scope.
3. Validate post-deletion integrity:
   - `python scripts/check_data_integrity.py`

## Release and Rollback

1. Follow the release/rollback checklist in `docs/RELEASE_AND_ROLLBACK_CHECKLIST.md`.
2. Always take a backup before a release:
   - `powershell -File scripts/backup_data.ps1`
3. Keep the previous image tag and environment bundle ready for rollback.

## Alerting Setup

1. Import Prometheus alert rules template:
   - `deploy/prometheus-alert-rules.yml`
2. Wire alerts to your paging/incident channel.
3. Validate alert firing in staging before production rollout.

## Troubleshooting

- `429 Too Many Requests`:
  - Check login lockout and global request rate settings.
- `413 Request body too large`:
  - Check `MAX_REQUEST_SIZE_MB` and `UPLOAD_MAX_SIZE_MB`.
- `500 Chat error`:
  - Inspect structured logs for `error_class` and `request_id`.
- Slow startup:
  - First model download can take several minutes. Optional `HF_TOKEN` improves reliability.

## Pre-Release Checklist

1. Run API tests:
   - `python -m pytest tests/test_api.py -q`
2. Run data integrity checks:
   - `python scripts/check_data_integrity.py`
3. Verify `.env` contains production-safe values
4. Verify health and readiness endpoints
5. Verify auth lockout, request-size, and rate-limit protections
