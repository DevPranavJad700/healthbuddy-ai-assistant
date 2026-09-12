# Data Retention and Deletion Workflow

This document defines how to retain, delete, and verify user-related data in HealthBuddy AI.

## Scope

Covers data in:

- SQLite or PostgreSQL relational database
- Vector store files under data/chroma_db
- Uploaded files under data/pdfs and data/knowledge_base
- Audit and operational logs

## Retention Policy Baseline

- Chat sessions and analytics events: retain 365 days by default.
- Clinician review records: retain 365 days by default.
- Uploaded user documents: retain 90 days by default unless required longer.
- Auth protection counters and in-memory rate data: ephemeral.
- Operational logs: retain 30-90 days depending on deployment policy.

Adjust these values only through approved policy changes.

## Deletion Triggers

- User account deletion request.
- Data minimization job for expired records.
- Legal/compliance request approved by data owner.

## Operational Procedure

1. Capture scope and approval

- Record request ID, approver, and target identity (user_id, username, email).

2. Create backup before deletion

- Run: powershell -File scripts/backup_data.ps1
- Save backup path in ticket.

3. Delete relational records

- Remove user profile, goals, sessions, outcome events, and clinician review records tied to the user.
- If soft-delete policy is enabled in infra, mark records as deleted and redact PII.

4. Delete related documents and vectors

- Remove uploaded files mapped to the user.
- Rebuild or prune vector entries for deleted documents.

5. Verify integrity

- Run: python scripts/check_data_integrity.py
- Run API smoke checks against health and document listing endpoints.

6. Record completion

- Document operator, timestamp, affected entities, and verification output.

## Emergency Rollback

If deletion scope was incorrect:

1. Stop write traffic.
2. Restore backup using scripts/restore_data.ps1.
3. Re-run integrity checks.
4. Open an incident record and notify stakeholders.

## Compliance Notes

- Do not keep raw backups beyond approved retention window.
- Ensure backup storage is encrypted and access-controlled.
- Keep an auditable trail for each deletion event.
