"""Purge old operational/assistant records based on retention policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.database import (
    SessionLocal,
    ChatLog,
    SymptomCheck,
    OutcomeEvent,
    ClinicianReview,
    ConsentRecord,
    AuditEvent,
)


TABLES = [
    ("chat_logs", ChatLog, settings.data_retention_days),
    ("symptom_checks", SymptomCheck, settings.data_retention_days),
    ("outcome_events", OutcomeEvent, settings.data_retention_days),
    ("clinician_reviews", ClinicianReview, settings.data_retention_days),
    ("consent_records", ConsentRecord, settings.consent_retention_days),
    ("audit_events", AuditEvent, settings.audit_retention_days),
]


def run_purge(default_retention_days: int) -> dict[str, int]:
    deleted_counts: dict[str, int] = {}

    db = SessionLocal()
    try:
        for table_name, model, retention_days in TABLES:
            effective_days = retention_days if retention_days and retention_days > 0 else default_retention_days
            cutoff = datetime.now(UTC) - timedelta(days=max(1, effective_days))
            q = db.query(model).filter(model.created_at < cutoff)
            deleted_counts[table_name] = q.delete(synchronize_session=False)
        db.commit()
        return deleted_counts
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    results = run_purge(settings.data_retention_days)
    total = sum(results.values())
    print(
        "Retention purge complete "
        f"(default_days={settings.data_retention_days}, "
        f"audit_days={settings.audit_retention_days}, "
        f"consent_days={settings.consent_retention_days})"
    )
    for name, count in results.items():
        print(f"- {name}: deleted={count}")
    print(f"Total deleted: {total}")
