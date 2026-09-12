/**
 * HealthBuddy AI — Config Module
 * API routes, localStorage keys, SVGs, and i18n dictionaries.
 */

export const API_BASE = "/api/v1";

export const API = {
  chat: `${API_BASE}/chat`,
  chatStream: `${API_BASE}/chat/stream`,
  chatFeedback: `${API_BASE}/chat/feedback`,
  clinicianReviewRequest: `${API_BASE}/chat/clinician-review`,
  authLogin: `${API_BASE}/auth/login`,
  authRegister: `${API_BASE}/auth/register`,
  authLogout: `${API_BASE}/auth/logout`,
  authExportMyData: `${API_BASE}/auth/export-my-data`,
  authDeleteMyData: `${API_BASE}/auth/delete-my-data`,
  authSession: `${API_BASE}/auth/session`,
  authRefresh: `${API_BASE}/auth/refresh`,
  authGoogleStart: `${API_BASE}/auth/google/start`,
  authGoogleStatus: `${API_BASE}/auth/google/status`,
  authProfile: `${API_BASE}/auth/profile`,
  chatHistory: `${API_BASE}/chat/history`,
  chatSessions: `${API_BASE}/chat/sessions`,
  documents: `${API_BASE}/documents`,
  uploadDocument: `${API_BASE}/documents/upload`,
  symptomCheck: `${API_BASE}/symptoms/check`,
  symptomList: `${API_BASE}/symptoms/list`,
  goals: `${API_BASE}/personalization/goals`,
  complianceConsent: `${API_BASE}/compliance/consent`,
  complianceConsentMe: `${API_BASE}/compliance/consent/me`,
  complianceConsentRevoke: `${API_BASE}/compliance/consent/revoke`,
  clinicianQueue: `${API_BASE}/analytics/clinician-reviews`,
  health: "/api/health",
};

export const LOCAL_HISTORY_KEY = "healthbuddy.localHistory";
export const AUTH_TOKEN_KEY = "healthbuddy.jwt";
export const AUTH_REFRESH_TOKEN_KEY = "healthbuddy.refresh_jwt";
export const MESSAGE_DRAFT_KEY = "healthbuddy.messageDraft";
export const ONBOARDING_DISMISSED_KEY = "healthbuddy.onboardingDismissed";
export const ONBOARDING_INTENT_KEY = "healthbuddy.onboardingIntent";
export const PROFILE_ONBOARDING_DONE_KEY = "healthbuddy.profileOnboardingDone";
export const ACCESSIBILITY_PREFS_KEY = "healthbuddy.accessibilityPrefs";
export const UI_LANGUAGE_KEY = "healthbuddy.uiLanguage";
export const PRIVACY_EXPORT_META_KEY = "healthbuddy.privacyExportMeta";
export const PRIVACY_AUDIT_TRAIL_KEY = "healthbuddy.privacyAuditTrail";
export const AUTH_FORM_PREFS_KEY = "healthbuddy.authFormPrefs";

export const USER_AVATAR_SVG =
  '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
export const BOT_AVATAR_SVG =
  '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line></svg>';
export const DOC_AVATAR_SVG =
  '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>';
export const CHAT_ICON_SVG =
  '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>';

export const EMERGENCY_NUMBERS = {
  us: "US/Canada: 911",
  eu: "EU: 112",
  uk: "UK: 999 or 112",
  au: "Australia: 000",
  in: "India: 112",
};

export const RTL_LANGUAGES = new Set(["ar"]);

export const I18N = {
  en: {
    language_label: "Language",
    header_title: "Chat with HealthBuddy",
    emergency_help_label: "Emergency help now:",
    country_label: "Country",
    privacy_label: "Privacy promise:",
    privacy_copy: "We do not sell your health data. You control export and deletion from account settings.",
    safety_title: "Safety Promise",
    safety_can_do_label: "Can do:",
    safety_can_do_copy: "General education, symptom guidance, and care-seeking triage support.",
    safety_cannot_do_label: "Cannot do:",
    safety_cannot_do_copy: "Diagnose disease, replace a licensed clinician, or prescribe medication.",
    disclaimer: "For informational purposes only. Always consult a healthcare professional.",
    input_placeholder: "Ask a health question...",
    retry_last_send: "Retry last send",
  },
  hi: {
    language_label: "भाषा",
    header_title: "हेल्थबडी से चैट करें",
    emergency_help_label: "आपातकालीन सहायता अभी:",
    country_label: "देश",
    privacy_label: "गोपनीयता वादा:",
    privacy_copy: "हम आपका स्वास्थ्य डेटा नहीं बेचते। आप अकाउंट सेटिंग्स से एक्सपोर्ट और डिलीट नियंत्रित करते हैं।",
    safety_title: "सुरक्षा वादा",
    safety_can_do_label: "क्या कर सकता है:",
    safety_can_do_copy: "सामान्य जानकारी, लक्षण मार्गदर्शन और देखभाल-आधारित ट्रायेज सहायता।",
    safety_cannot_do_label: "क्या नहीं कर सकता:",
    safety_cannot_do_copy: "बीमारी का निदान, लाइसेंसधारी चिकित्सक का विकल्प या दवा लिखना।",
    disclaimer: "यह केवल जानकारी के लिए है। हमेशा स्वास्थ्य विशेषज्ञ से परामर्श लें।",
    input_placeholder: "अपना स्वास्थ्य प्रश्न पूछें...",
    retry_last_send: "पिछला संदेश फिर भेजें",
  },
  es: {
    language_label: "Idioma",
    header_title: "Chatea con HealthBuddy",
    emergency_help_label: "Ayuda de emergencia ahora:",
    country_label: "País",
    privacy_label: "Promesa de privacidad:",
    privacy_copy: "No vendemos sus datos de salud. Puede exportar y eliminar desde la configuración de su cuenta.",
    safety_title: "Promesa de Seguridad",
    safety_can_do_label: "Puede hacer:",
    safety_can_do_copy: "Educación general, orientación sobre síntomas y apoyo de triaje para buscar atención.",
    safety_cannot_do_label: "No puede hacer:",
    safety_cannot_do_copy: "Diagnosticar enfermedades, reemplazar a un médico colegiado o recetar medicamentos.",
    disclaimer: "Sólo para fines informativos. Consulte siempre a un profesional de la salud.",
    input_placeholder: "Haga una pregunta de salud...",
    retry_last_send: "Reintentar último envío",
  },
  ar: {
    language_label: "اللغة",
    header_title: "تحدث مع هيلث بادي",
    emergency_help_label: "المساعدة في حالات الطوارئ الآن:",
    country_label: "البلد",
    privacy_label: "وعد الخصوصية:",
    privacy_copy: "نحن لا نبيع بياناتك الصحية. يمكنك التحكم في التصدير والحذف من إعدادات الحساب.",
    safety_title: "وعد الأمان",
    safety_can_do_label: "ما يمكنه فعله:",
    safety_can_do_copy: "التثقيف العام، والتوجيه بشأن الأعراض، ودعم الفرز لطلب الرعاية.",
    safety_cannot_do_label: "ما لا يمكنه فعله:",
    safety_cannot_do_copy: "تشخيص الأمراض، أو استبدال الطبيب المعالج، أو وصف الأدوية.",
    disclaimer: "لأغراض إعلامية فقط. استشر دائمًا أخصائي الرعاية الصحية.",
    input_placeholder: "اطرح سؤالاً صحياً...",
    retry_last_send: "إعادة محاولة الإرسال الأخير",
  },
};
