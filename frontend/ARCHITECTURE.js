/**
 * HealthBuddy AI — Frontend Modular ES Architecture
 * 
 * The frontend is modularized into native ES modules served directly by FastAPI:
 * 
 * ARCHITECTURE:
 * ┌────────────────────────────────────────────────────────┐
 * │  index.html (<script type="module" src="app.js">)      │
 * └──────────────────────────┬─────────────────────────────┘
 *                            │ imports
 * ┌──────────────────────────▼─────────────────────────────┐
 * │  app.js (Main Orchestrator & Window Bindings)          │
 * │  ├── modules/config.js     (Routes, Keys, SVGs, I18N)  │
 * │  ├── modules/state.js      (Central state & token ops) │
 * │  ├── modules/utils.js      (Formatting, escaping, a11y)│
 * │  ├── modules/auth.js       (Login, register, GDPR)     │
 * │  ├── modules/chat.js       (SSE stream, bubble render) │
 * │  ├── modules/symptoms.js   (Symptom triage & lookup)   │
 * │  ├── modules/analytics.js  (Chart.js, Clinician queue) │
 * │  ├── modules/documents.js  (RAG uploads & management)  │
 * │  ├── modules/goals.js      (Goals CRUD & presets)      │
 * │  ├── modules/voice.js      (Web Speech API)            │
 * │  └── modules/onboarding.js (Profile wizard & checklist)│
 * ├────────────────────────────────────────────────────────┤
 * │  liquid-theme.js (Three.js WebGL theme background)     │
 * ├────────────────────────────────────────────────────────┤
 * │  sw.js (Service Worker / PWA cache)                    │
 * └────────────────────────────────────────────────────────┘
 * 
 * ZERO BUILD STEP REQUIRED:
 * Native browser ES modules (ESM) are supported in 100% of modern browsers.
 * FastAPI serves the `/frontend` directory under `/static`.
 */
