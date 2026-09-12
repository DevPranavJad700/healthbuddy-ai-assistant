# Accessibility Audit Checklist (WCAG AA)

## Core Tests

- Keyboard-only navigation for all primary flows
- Screen reader validation (labels, landmarks, announcements)
- Focus visibility and tab order checks
- Contrast checks for text and controls
- Error and status messaging accessibility

## Chat-specific

- Message updates announced via ARIA live region
- Explainability panels operable by keyboard
- Form inputs and dropdowns with proper labels

## Acceptance

- No critical WCAG AA failures in release candidate.
- Accessibility regression tests included in CI where practical.
