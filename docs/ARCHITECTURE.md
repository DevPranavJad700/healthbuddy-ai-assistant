# HealthBuddy AI — Architecture Overview

## Frontend Modular ES Architecture

The frontend is modularized into native ES modules served directly by FastAPI:

```text
┌────────────────────────────────────────────────────────┐
│  index.html (<script type="module" src="app.js">)      │
└──────────────────────────┬─────────────────────────────┘
                           │ imports
┌──────────────────────────▼─────────────────────────────┐
│  app.js (Main Orchestrator & Window Bindings)          │
│  ├── modules/config.js     (Routes, Keys, SVGs, I18N)  │
│  ├── modules/state.js      (Central state & token ops) │
│  ├── modules/utils.js      (Formatting, escaping, a11y)│
│  ├── modules/auth.js       (Login, register, GDPR)     │
│  ├── modules/chat.js       (SSE stream, bubble render) │
│  ├── modules/symptoms.js   (Symptom triage & lookup)   │
│  ├── modules/analytics.js  (Chart.js, Clinician queue) │
│  ├── modules/documents.js  (RAG uploads & management)  │
│  ├── modules/goals.js      (Goals CRUD & presets)      │
│  ├── modules/voice.js      (Web Speech API)            │
│  └── modules/onboarding.js (Profile wizard & checklist)│
├────────────────────────────────────────────────────────┤
│  liquid-theme.js (Three.js WebGL theme background)     │
├────────────────────────────────────────────────────────┤
│  sw.js (Service Worker / PWA cache)                    │
└──────────────────────────┴─────────────────────────────┘
```

### Zero Build Step Required
Native browser ES modules (ESM) are supported in 100% of modern browsers.
FastAPI serves the `/frontend` directory under `/static`.

---

## Backend Services Architecture

```text
FastAPI Application (app.main)
├── API Routers (/api/v1/)
│   ├── auth.py          (JWT, registration, OTP verification)
│   ├── chat.py          (SSE streaming, safety triage, RAG orchestration)
│   ├── symptoms.py      (Symptom checker, clinical assessments)
│   ├── documents.py     (Uploads, vector store indexing)
│   ├── fhir.py          (HL7 / FHIR R4 interoperability bundle export)
│   ├── multimodal.py    (Medical image OCR and vision extraction)
│   ├── personalization.py (Goals, health profile, context)
│   ├── compliance.py    (HIPAA, GDPR, audit trail, consent)
│   └── admin.py         (User management, platform metrics)
├── Core Infrastructure
│   ├── config.py        (Pydantic settings, environment variables)
│   ├── security.py      (JWT encoding/decoding, RBAC, admin authorization)
│   └── database.py      (SQLAlchemy ORM models and session management)
└── AI & Services Layer
    ├── rag_service.py   (Retrieval-Augmented Generation, LCEL chains)
    ├── vector_store.py  (ChromaDB embedding & similarity search)
    ├── safety_layer.py  (Clinical red-flag detection, prompt guardrails)
    ├── triage_rules.py  (Authoritative emergency triage assessment)
    ├── redis_client.py  (Singleton connection pool, rate limiting, caching)
    └── fhir_service.py  (FHIR R4 resource generation)
```
