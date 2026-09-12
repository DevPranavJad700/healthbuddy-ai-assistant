# Security Enterprise Hardening

## Secrets and Keys

- Use vault/KMS in production, not plaintext env-only workflows.
- Rotate API and signing keys on schedule.

## Access Control

- RBAC/ABAC for admin and clinician functions.
- Least privilege for operational endpoints.

## Data Protection

- Field-level encryption for highly sensitive records.
- Encrypted backups with periodic restore verification.

## Supply Chain

- Generate SBOM in CI.
- Enforce dependency vulnerability scans.
- Sign release artifacts and retain provenance records.

## Testing

- Scheduled penetration tests.
- Routine security regression tests for auth and data access boundaries.
