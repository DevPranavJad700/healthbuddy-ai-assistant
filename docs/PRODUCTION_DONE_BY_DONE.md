# Production Done-by-Done Checklist

Use this checklist to track closure of each production hardening task.

## 1. Production Configuration

- [x] `ENVIRONMENT=production` set in `.env`
- [x] Strong `SECRET_KEY` set (32+ chars)
- [x] Explicit `CORS_ORIGINS` set to frontend domains
- [x] Limits set: `MAX_REQUEST_SIZE_MB`, `UPLOAD_MAX_SIZE_MB`, `RATE_LIMIT_REQUESTS_PER_MINUTE`
- [x] Optional `HF_TOKEN` field added

Acceptance criteria:

- Startup passes production validation checks.
- Health and readiness endpoints return `200`.

## 2. Runtime Warnings Cleanup

- [x] Pydantic class config updated to v2 `model_config`
- [x] Hugging Face generation-config conflict removed
- [x] Retrieval score handling normalized in vector search

Acceptance criteria:

- No local deprecation warnings from these three issues during tests.

## 3. Auth and Abuse Protection

- [x] Login throttling by username
- [x] Login throttling by IP
- [x] Temporary lockout implemented
- [x] Password policy enforced (length + complexity)

Acceptance criteria:

- Excess failed login attempts return `429`.
- Weak passwords are rejected with `400`.

## 4. Security and Auditability

- [x] Audit logs added for register/login/profile update
- [x] Audit logs added for document upload/delete
- [x] Audit logs added for session list/read/clear
- [x] Unauthorized session endpoints remain blocked

Acceptance criteria:

- Sensitive action logs are emitted with action/status/user context.

## 5. Data Safety

- [x] Backup script added (`scripts/backup_data.ps1`)
- [x] Restore script added (`scripts/restore_data.ps1`)
- [x] Integrity check script added (`scripts/check_data_integrity.py`)

Acceptance criteria:

- Backup and restore scripts run without manual file edits.
- Integrity script returns pass/fail for app and vector DBs.

## 6. Test Quality Gates

- [x] Isolated test DB fixture retained
- [x] Added tests for `429` rate-limit behavior
- [x] Added tests for `413` request-size behavior
- [x] Added tests for `413` upload-size behavior
- [x] Added tests for production startup validation failures
- [x] Added cross-user/unauthorized access tests

Acceptance criteria:

- `python -m pytest tests/test_api.py -q` passes.

## 7. Observability In-App

- [x] Structured request logs include request id, path, status, latency
- [x] Explicit error classification for chat failures
- [x] Lightweight runtime counters for chat errors/safety/emergencies

Acceptance criteria:

- Responses include `X-Request-ID`.
- Dashboard payload includes runtime counters.

## 8. Operator Documentation

- [x] Runbook updated with env vars and safe defaults
- [x] Startup verification steps documented
- [x] Troubleshooting section documented
- [x] Pre-release checklist documented
- [x] Retention/deletion workflow documented
- [x] Release rollback checklist documented

Acceptance criteria:

- New operator can run, validate, and troubleshoot without tribal knowledge.
