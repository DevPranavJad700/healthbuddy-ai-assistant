# Release and Rollback Checklist

Use this checklist for every staging or production release.

## Pre-Release Gates

1. Configuration

- Confirm environment file uses production-safe values.
- Confirm SECRET_KEY length >= 32.
- Confirm CORS_ORIGINS contains only approved domains.
- Confirm DB_AUTO_CREATE_ON_STARTUP=false in production.
- Confirm DB_RUN_MIGRATIONS_ON_STARTUP=true only when migration plan is approved.

2. Quality

- Run: python -m pytest -q
- Run: python tests/verify_all.py (against live local/staging instance)
- Confirm no unresolved high-severity security findings in CI.

3. Data Safety

- Run: powershell -File scripts/backup_data.ps1
- Verify backup artifact is stored in approved location.

4. Readiness

- Validate endpoints: /api/live, /api/health, /api/ready, /api/metrics.
- Confirm request tracing header X-Request-ID is present.

## Release Steps

1. Apply schema migrations

- Run: alembic upgrade head

2. Deploy application artifact

- Deploy container/image tag and verify startup logs.

3. Post-deploy smoke

- Run: python tests/smoke_post_deploy.py

4. Monitor for 30 minutes

- Track 5xx rate, latency, provider failure counters, and auth failures.

## Rollback Criteria

Trigger rollback if any of the following occur:

- Health or readiness fails continuously for 5 minutes.
- 5xx error rate exceeds agreed threshold for more than 10 minutes.
- Critical auth/session breakage prevents user access.
- Data corruption signal from integrity checks.

## Rollback Procedure

1. Stop rollout and route traffic to previous stable version.
2. Re-deploy previous image tag and configuration bundle.
3. If schema/data issue occurred, restore latest valid backup:

- powershell -File scripts/restore_data.ps1 -BackupDir <backup-path>

4. Validate:

- /api/live, /api/health, /api/ready
- python scripts/check_data_integrity.py

5. Announce rollback status and open incident follow-up.

## Post-Rollback Actions

- Capture timeline, impact, and root cause hypotheses.
- Add corrective action items before next release attempt.
- Update this checklist if new failure class is discovered.
