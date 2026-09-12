"""Export signed governance snapshot from local database."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal, ConsentRecord, AuditEvent
from app.services.consent_service import build_signed_snapshot


def export_payload(limit: int, action_prefix: str | None) -> dict:
    db = SessionLocal()
    try:
        consent_rows = (
            db.query(ConsentRecord)
            .order_by(ConsentRecord.created_at.desc())
            .limit(limit)
            .all()
        )

        audit_q = db.query(AuditEvent)
        if action_prefix:
            audit_q = audit_q.filter(AuditEvent.action.like(f"{action_prefix}%"))
        audit_rows = audit_q.order_by(AuditEvent.created_at.desc()).limit(limit).all()

        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "limit": limit,
            "action_prefix": action_prefix,
            "consents": [
                {
                    "id": c.id,
                    "user_id": c.user_id,
                    "session_id": c.session_id,
                    "consent_type": c.consent_type,
                    "policy_version": c.policy_version,
                    "granted": c.granted,
                    "scope": c.scope,
                    "source": c.source,
                    "metadata_json": c.metadata_json,
                    "created_at": c.created_at.isoformat() if c.created_at is not None else None,
                }
                for c in consent_rows
            ],
            "audit_events": [
                {
                    "id": a.id,
                    "action": a.action,
                    "status": a.status,
                    "user_id": a.user_id,
                    "details": a.details,
                    "created_at": a.created_at.isoformat() if a.created_at is not None else None,
                }
                for a in audit_rows
            ],
        }
        payload["snapshot_signature"] = build_signed_snapshot(payload)
        return payload
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Export signed governance snapshot")
    parser.add_argument("--output", default="./data/audit_snapshot.json")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--action-prefix", default=None)
    args = parser.parse_args()

    payload = export_payload(limit=max(1, args.limit), action_prefix=args.action_prefix)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved signed snapshot to {out}")


if __name__ == "__main__":
    main()
