# Clinical Governance Workflow

## Purpose

Define external clinician review board governance for triage rules and medical content.

## Review Board Roles

- Clinical Chair: final approval authority for triage rule releases.
- Safety Reviewer: checks red-flag coverage and escalation safety.
- Localization Reviewer: validates multilingual medical fidelity.
- Compliance Observer: ensures policy/legal alignment.

## Triage Rule Approval Flow

1. Draft rule proposal with rationale and references.
2. Clinical peer review (minimum 2 reviewers).
3. Simulation evaluation on red-flag benchmark set.
4. Safety sign-off and release candidate tagging.
5. Final chair approval and version publish.

## Required Approval Evidence

- Rule version and changelog.
- Source references (WHO/CDC/NICE/local ministry where applicable).
- Benchmark deltas (triage pass, hallucination pass, safety pass).
- Rollback strategy and owner.

## Escalation Queue Governance

- Emergency triage SLA: <= 1 hour clinician touch.
- Urgent triage SLA: <= 4 hours clinician touch.
- Self-care/manual review SLA: <= 24 hours.
- Closure requires reviewer notes and closure reason.
