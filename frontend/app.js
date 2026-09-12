/**
 * HealthBuddy AI — Frontend Modular Entry Point
 * Orchestrates ES modules: config, state, utils, auth, chat, symptoms, analytics, documents, goals, voice, onboarding.
 */

import {
  API,
  API_BASE,
  I18N,
  RTL_LANGUAGES,
  EMERGENCY_NUMBERS,
  UI_LANGUAGE_KEY,
  MESSAGE_DRAFT_KEY,
} from "./modules/config.js";

import {
  state,
  getAuthToken,
} from "./modules/state.js";

import {
  esc,
  showToast,
  autoResize,
} from "./modules/utils.js";

import {
  authHeaders,
  setAuthMode,
  setAuthModalOpen,
  setProfileOnboardingOpen,
  setDangerZoneOpen,
  loadAuthFormPreferences,
  saveAuthFormPreferences,
  setAuthPasswordVisible,
  handleAuth,
  handleLogout,
  handleDeleteMyData,
  handleExportMyData,
  adminDeleteUserData,
  refreshSessionState,
  syncAuthUI,
  loadConsentCenterState,
  recordConsent,
  revokeConsent,
  openConsentCenterWithContext,
  setConsentCenterOpen,
  loadPrivacyCenterData,
  setPrivacyCenterOpen,
  addPrivacyAuditEvent,
  onAuthChange,
} from "./modules/auth.js";

import {
  sendMessage,
  clearChat,
  startNewChat,
  loadSessions,
  loadSession,
  deleteHistorySession,
  exportSession,
  loadChatHistory,
} from "./modules/chat.js";

import {
  addSymptom,
  removeSymptom,
  loadSymptomSuggestions,
  checkSymptoms,
  renderSymptoms,
  updateEmergencyNumber,
} from "./modules/symptoms.js";

import {
  loadDashboard,
  loadClinicianQueue,
  refreshQueueSummaryCounts,
  updateReview,
} from "./modules/analytics.js";

import {
  uploadFile,
  loadDocuments,
  deleteDoc,
} from "./modules/documents.js";

import {
  loadGoals,
  addGoal,
  deleteGoal,
} from "./modules/goals.js";

import { initVoiceInput } from "./modules/voice.js";

import {
  initOnboardingModal,
  showProfileWizard,
  hideProfileWizard,
  renderWizardStep,
  wizardFinish,
  maybeShowProfileWizard,
  maybeShowOnboardingModal,
  makeTagInput,
  updateOnboardingChecklist,
  syncOnboardingIntentSelector,
  setOnboardingIntent,
  setShortcutsModalOpen,
  setAccessibilityModalOpen,
  initRotatingPlaceholders,
} from "./modules/onboarding.js";

// ── Global Window Bindings (for inline HTML onclick & E2E tests) ──
window.deleteGoal = deleteGoal;
window.exportSession = exportSession;
window.loadSession = loadSession;
window.deleteHistorySession = deleteHistorySession;
window.removeSymptom = removeSymptom;
window.deleteDoc = deleteDoc;
window.updateReview = updateReview;
window.handleDeleteMyData = handleDeleteMyData;
window.handleExportMyData = handleExportMyData;
window.handleAuth = handleAuth;
window.handleLogout = handleLogout;
window.setAuthModalOpen = setAuthModalOpen;
window.setAuthMode = setAuthMode;
window.addGoal = addGoal;
window.adminDeleteUserData = adminDeleteUserData;
window.maybeShowOnboardingModal = maybeShowOnboardingModal;
window.maybeShowProfileWizard = maybeShowProfileWizard;
window.updateOnboardingChecklist = updateOnboardingChecklist;
window.openConsentCenterWithContext = openConsentCenterWithContext;

// ── Localization ──────────────────────────────────────────────────
function getLanguageBundle(lang) {
  return I18N[lang] || I18N.en;
}

function t(key) {
  const bundle = getLanguageBundle(state.uiLanguage);
  return bundle[key] || I18N.en[key] || key;
}

function applyLanguageDirection(lang) {
  const rtl = RTL_LANGUAGES.has(lang);
  document.documentElement.setAttribute("lang", lang);
  document.documentElement.setAttribute("dir", rtl ? "rtl" : "ltr");
  document.body.classList.toggle("hb-rtl", rtl);
}

function applyLocalizedSafetyTexts() {
  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  setTxt("languageLabel", t("language_label"));
  setTxt("headerTitle", t("header_title"));
  setTxt("emergencyHelpLabel", t("emergency_help_label"));
  setTxt("trustCountryLabel", t("country_label"));
  setTxt("privacyPromiseLabel", t("privacy_label"));
  setTxt("privacyPromiseCopy", t("privacy_copy"));
  setTxt("safetyPromiseTitle", t("safety_title"));
  setTxt("safetyCanDoLabel", t("safety_can_do_label"));
  setTxt("safetyCanDoCopy", t("safety_can_do_copy"));
  setTxt("safetyCannotDoLabel", t("safety_cannot_do_label"));
  setTxt("safetyCannotDoCopy", t("safety_cannot_do_copy"));
  setTxt("safetyDisclaimerText", t("disclaimer"));
  setTxt("retryLastBtn", t("retry_last_send"));

  const msgInput = document.getElementById("messageInput");
  if (msgInput) msgInput.placeholder = t("input_placeholder");

  const langSelect = document.getElementById("uiLanguageSelect");
  if (langSelect) langSelect.value = state.uiLanguage;
}

export function applyLocalization(lang) {
  const selected = I18N[lang] ? lang : "en";
  state.uiLanguage = selected;
  localStorage.setItem(UI_LANGUAGE_KEY, selected);
  applyLanguageDirection(selected);
  applyLocalizedSafetyTexts();
}

async function hydrateLanguageFromProfile() {
  if (!getAuthToken()) {
    applyLocalization(state.uiLanguage || "en");
    return;
  }
  try {
    const r = await fetch(API.authProfile, { headers: authHeaders() });
    if (!r.ok) {
      applyLocalization(state.uiLanguage || "en");
      return;
    }
    const profile = await r.json().catch(() => ({}));
    const profileLang = String(profile?.preferred_language || "").toLowerCase();
    if (profileLang && I18N[profileLang]) {
      applyLocalization(profileLang);
      return;
    }
  } catch (_) {}
  applyLocalization(state.uiLanguage || "en");
}

// ── Sidebar & Layout ──────────────────────────────────────────────
export function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  if (window.innerWidth < 768) {
    state.sidebarOpen ? closeSidebar() : openSidebar();
  } else {
    sidebar.classList.toggle("collapsed");
  }
}

export function openSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  sidebar.classList.add("open");
  state.sidebarOpen = true;
  let o = document.querySelector(".sidebar-overlay");
  if (!o) {
    o = document.createElement("div");
    o.className = "sidebar-overlay";
    document.body.appendChild(o);
  }
  o.classList.add("active");
  o.onclick = closeSidebar;
}

export function closeSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  sidebar.classList.remove("open");
  state.sidebarOpen = false;
  const o = document.querySelector(".sidebar-overlay");
  if (o) o.classList.remove("active");
}

export function setActiveTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.toggle("active", content.id === tabId);
  });
}

// ── Particles Background ─────────────────────────────────────────
function initParticles() {
  const particles = document.getElementById("particles");
  if (!particles) return;
  for (let i = 0; i < 25; i++) {
    const p = document.createElement("div");
    p.className = "particle";
    p.style.left = `${Math.random() * 100}%`;
    p.style.animationDuration = `${8 + Math.random() * 12}s`;
    p.style.animationDelay = `${Math.random() * 10}s`;
    p.style.width = p.style.height = `${1 + Math.random() * 3}px`;
    particles.appendChild(p);
  }
}

// ── Health Check ─────────────────────────────────────────────────
async function checkHealth() {
  const dot = document.querySelector(".status-dot");
  const text = document.getElementById("statusText");
  const sub = document.getElementById("headerSubtitle");
  try {
    const r = await fetch(API.health);
    if (r.ok) {
      if (dot) dot.className = "status-dot online";
      if (text) text.textContent = "API online";
      if (sub) sub.title = "Safety guardrails active";
    } else {
      if (dot) dot.className = "status-dot error";
      if (text) text.textContent = "Server error";
    }
  } catch (_) {
    if (dot) dot.className = "status-dot error";
    if (text) text.textContent = "Server offline";
  }
}

// ── Connectivity / Offline Handling ──────────────────────────────
function handleConnectivity() {
  const banner = document.getElementById("connectionBanner");
  window.addEventListener("online", () => {
    state.isOnline = true;
    if (banner) banner.classList.add("hidden");
    showToast("Internet connection restored", "success");
    checkHealth();
  });
  window.addEventListener("offline", () => {
    state.isOnline = false;
    if (banner) banner.classList.remove("hidden");
    showToast("You are currently offline", "error");
  });
}

// ── Hook auth state changes ──────────────────────────────────────
onAuthChange(() => {
  updateOnboardingChecklist();
  loadGoals();
  loadDocuments();
  const clQueue = document.getElementById("clinicianQueue");
  if (clQueue && state.isAdmin) {
    loadClinicianQueue();
  }
});

// ── Initialize App & Listeners ───────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  applyLocalization(state.uiLanguage || "en");
  initParticles();
  handleConnectivity();
  loadAuthFormPreferences();
  setAuthPasswordVisible(false);
  setAuthMode("login");
  syncAuthUI();
  initVoiceInput();
  initOnboardingModal();
  initRotatingPlaceholders();

  // Draft message restore
  const msgInput = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendButton");
  if (msgInput) {
    const draft = localStorage.getItem(MESSAGE_DRAFT_KEY) || "";
    if (draft) {
      msgInput.value = draft;
      if (sendBtn) sendBtn.disabled = !draft.trim();
      autoResize(msgInput);
    }
  }

  // Bind main chat inputs
  if (sendBtn) sendBtn.addEventListener("click", () => sendMessage());
  if (msgInput) {
    msgInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    msgInput.addEventListener("input", () => {
      autoResize(msgInput);
      if (sendBtn) sendBtn.disabled = !msgInput.value.trim();
      const val = (msgInput.value || "").trim();
      if (val) localStorage.setItem(MESSAGE_DRAFT_KEY, val);
      else localStorage.removeItem(MESSAGE_DRAFT_KEY);
    });
  }

  // Chat controls
  const clearChatBtn = document.getElementById("clearChat");
  if (clearChatBtn) clearChatBtn.addEventListener("click", clearChat);
  const newChatBtn = document.getElementById("newChatBtn");
  if (newChatBtn) newChatBtn.addEventListener("click", startNewChat);

  // Sidebar toggle
  const menuToggle = document.getElementById("menuToggle");
  if (menuToggle) menuToggle.addEventListener("click", toggleSidebar);

  // File Upload
  const uploadZone = document.getElementById("uploadZone");
  const fileInput = document.getElementById("fileInput");
  if (uploadZone && fileInput) {
    uploadZone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      if (e.target.files[0]) uploadFile(e.target.files[0]);
    });
    uploadZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadZone.classList.add("drag-over");
    });
    uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
    uploadZone.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadZone.classList.remove("drag-over");
      if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
    });
  }

  // Suggestion chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (msgInput) {
        msgInput.value = chip.dataset.query;
        if (sendBtn) sendBtn.disabled = false;
        sendMessage();
      }
    });
  });

  // Sidebar tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      setActiveTab(btn.dataset.tab);
      if (btn.dataset.tab === "analytics-tab") loadDashboard();
      if (btn.dataset.tab === "goals-tab") loadGoals();
      if (btn.dataset.tab === "clinician-tab") loadClinicianQueue();
      if (btn.dataset.tab === "history-tab") loadChatHistory();
    });
  });

  // Symptom checker
  const addSymptomBtn = document.getElementById("addSymptomBtn");
  const checkSymptomsBtn = document.getElementById("checkSymptomsBtn");
  const symptomInput = document.getElementById("symptomInput");
  if (addSymptomBtn) addSymptomBtn.addEventListener("click", addSymptom);
  if (checkSymptomsBtn) checkSymptomsBtn.addEventListener("click", checkSymptoms);
  if (symptomInput) {
    symptomInput.addEventListener("change", () => {
      if (symptomInput.value) addSymptom();
    });
    symptomInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        addSymptom();
      }
    });
  }

  // Goals
  const addGoalBtn = document.getElementById("addGoalBtn");
  if (addGoalBtn) addGoalBtn.addEventListener("click", addGoal);
  document.querySelectorAll(".goal-preset-chip").forEach((chip) => {
    chip.addEventListener("click", async () => {
      const goal = chip.dataset.goal;
      if (!goal || chip.classList.contains("used")) return;
      const gInput = document.getElementById("goalInput");
      if (gInput) gInput.value = goal;
      await addGoal();
    });
  });

  // Auth Modals & Actions
  const authLoginBtn = document.getElementById("authLoginBtn");
  const authRegisterBtn = document.getElementById("authRegisterBtn");
  const openAuthModalBtn = document.getElementById("openAuthModalBtn");
  const closeAuthModalBtn = document.getElementById("closeAuthModalBtn");
  const authModal = document.getElementById("authModal");
  const authLogoutBtn = document.getElementById("authLogoutBtn");
  const authModeSignInBtn = document.getElementById("authModeSignInBtn");
  const authModeCreateBtn = document.getElementById("authModeCreateBtn");
  const authPasswordToggleBtn = document.getElementById("authPasswordToggleBtn");
  const authRememberMe = document.getElementById("authRememberMe");
  const authUsernameInput = document.getElementById("authUsernameInput");
  const authEmailInput = document.getElementById("authEmailInput");

  if (authLoginBtn) authLoginBtn.addEventListener("click", () => handleAuth("login"));
  if (authRegisterBtn) authRegisterBtn.addEventListener("click", () => handleAuth("register"));
  if (openAuthModalBtn) {
    openAuthModalBtn.addEventListener("click", () => {
      setAuthMode("login");
      setAuthModalOpen(true);
      authUsernameInput?.focus();
    });
  }
  if (closeAuthModalBtn) closeAuthModalBtn.addEventListener("click", () => setAuthModalOpen(false));
  if (authModal) {
    authModal.addEventListener("click", (e) => {
      if (e.target === authModal) setAuthModalOpen(false);
    });
  }
  if (authLogoutBtn) authLogoutBtn.addEventListener("click", handleLogout);
  if (authModeSignInBtn) {
    authModeSignInBtn.addEventListener("click", () => {
      setAuthMode("login");
      authUsernameInput?.focus();
    });
  }
  if (authModeCreateBtn) {
    authModeCreateBtn.addEventListener("click", () => {
      setAuthMode("register");
      authEmailInput?.focus();
    });
  }
  if (authPasswordToggleBtn) {
    authPasswordToggleBtn.addEventListener("click", () => {
      const pInput = document.getElementById("authPasswordInput");
      const isVisible = pInput?.type === "text";
      setAuthPasswordVisible(!isVisible);
    });
  }
  if (authRememberMe) authRememberMe.addEventListener("change", saveAuthFormPreferences);
  if (authUsernameInput) authUsernameInput.addEventListener("input", saveAuthFormPreferences);
  if (authEmailInput) authEmailInput.addEventListener("input", saveAuthFormPreferences);

  // Danger Zone & GDPR
  const dangerZoneToggleBtn = document.getElementById("dangerZoneToggleBtn");
  const deleteMyDataBtn = document.getElementById("deleteMyDataBtn");
  const exportMyDataBtn = document.getElementById("exportMyDataBtn");
  const adminDeleteUserBtn = document.getElementById("adminDeleteUserBtn");

  if (dangerZoneToggleBtn) {
    dangerZoneToggleBtn.addEventListener("click", () => {
      const panel = document.getElementById("dangerZonePanel");
      const isOpen = Boolean(panel && !panel.classList.contains("hidden"));
      setDangerZoneOpen(!isOpen);
    });
  }
  if (deleteMyDataBtn) deleteMyDataBtn.addEventListener("click", handleDeleteMyData);
  if (exportMyDataBtn) exportMyDataBtn.addEventListener("click", handleExportMyData);
  if (adminDeleteUserBtn) adminDeleteUserBtn.addEventListener("click", adminDeleteUserData);

  // Consent Center
  const openConsentCenterBtn = document.getElementById("openConsentCenterBtn");
  const closeConsentCenterBtn = document.getElementById("closeConsentCenterBtn");
  const consentCenterModal = document.getElementById("consentCenterModal");
  const refreshConsentCenterBtn = document.getElementById("refreshConsentCenterBtn");
  const consentList = document.getElementById("consentList");

  if (openConsentCenterBtn) {
    openConsentCenterBtn.addEventListener("click", () => {
      setConsentCenterOpen(true);
      loadConsentCenterState();
    });
  }
  if (closeConsentCenterBtn) closeConsentCenterBtn.addEventListener("click", () => setConsentCenterOpen(false));
  if (consentCenterModal) {
    consentCenterModal.addEventListener("click", (e) => {
      if (e.target === consentCenterModal) setConsentCenterOpen(false);
    });
  }
  if (refreshConsentCenterBtn) refreshConsentCenterBtn.addEventListener("click", loadConsentCenterState);
  if (consentList) {
    consentList.addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-consent-action]");
      if (!btn) return;
      const card = btn.closest(".consent-item");
      if (!card) return;
      const consentType = card.getAttribute("data-consent-type");
      const scope = card.getAttribute("data-scope") || null;
      const action = btn.getAttribute("data-consent-action");
      if (!consentType || !action) return;

      btn.disabled = true;
      try {
        if (action === "grant") {
          await recordConsent(consentType, scope, true);
          showToast("Consent granted", "success");
        } else {
          await revokeConsent(consentType, scope);
          showToast("Consent revoked", "success");
        }
      } catch (err) {
        showToast(err.message || "Consent update failed", "error");
      } finally {
        btn.disabled = false;
      }
    });
  }

  // Privacy Center
  const openPrivacyCenterBtn = document.getElementById("openPrivacyCenterBtn");
  const closePrivacyCenterBtn = document.getElementById("closePrivacyCenterBtn");
  const privacyCenterModal = document.getElementById("privacyCenterModal");
  const refreshPrivacyCenterBtn = document.getElementById("refreshPrivacyCenterBtn");
  const runPrivacyExportBtn = document.getElementById("runPrivacyExportBtn");
  const runPrivacyDeleteBtn = document.getElementById("runPrivacyDeleteBtn");

  if (openPrivacyCenterBtn) {
    openPrivacyCenterBtn.addEventListener("click", () => {
      setPrivacyCenterOpen(true);
      addPrivacyAuditEvent("Privacy center opened", "info", "From account panel");
      loadPrivacyCenterData();
    });
  }
  if (closePrivacyCenterBtn) closePrivacyCenterBtn.addEventListener("click", () => setPrivacyCenterOpen(false));
  if (privacyCenterModal) {
    privacyCenterModal.addEventListener("click", (e) => {
      if (e.target === privacyCenterModal) setPrivacyCenterOpen(false);
    });
  }
  if (refreshPrivacyCenterBtn) refreshPrivacyCenterBtn.addEventListener("click", loadPrivacyCenterData);
  if (runPrivacyExportBtn) runPrivacyExportBtn.addEventListener("click", handleExportMyData);
  if (runPrivacyDeleteBtn) runPrivacyDeleteBtn.addEventListener("click", handleDeleteMyData);

  // Clinician Queue Filters
  const reviewStatusFilter = document.getElementById("reviewStatusFilter");
  const reviewSortFilter = document.getElementById("reviewSortFilter");
  const reviewSearchInput = document.getElementById("reviewSearchInput");
  const refreshQueueBtn = document.getElementById("refreshQueueBtn");

  if (reviewStatusFilter) reviewStatusFilter.addEventListener("change", loadClinicianQueue);
  if (reviewSortFilter) reviewSortFilter.addEventListener("change", loadClinicianQueue);
  if (reviewSearchInput) reviewSearchInput.addEventListener("input", loadClinicianQueue);
  if (refreshQueueBtn) refreshQueueBtn.addEventListener("click", loadClinicianQueue);

  // Language & Country Selectors
  const uiLanguageSelect = document.getElementById("uiLanguageSelect");
  if (uiLanguageSelect) {
    uiLanguageSelect.addEventListener("change", (e) => {
      applyLocalization(e.target.value);
    });
  }
  const emergencyCountrySelect = document.getElementById("emergencyCountrySelect");
  if (emergencyCountrySelect) {
    emergencyCountrySelect.addEventListener("change", (e) => {
      updateEmergencyNumber(e.target.value);
    });
  }

  // Shortcuts & Accessibility
  const shortcutsBtn = document.getElementById("shortcutsBtn");
  const closeShortcutsBtn = document.getElementById("closeShortcutsBtn");
  if (shortcutsBtn) shortcutsBtn.addEventListener("click", () => setShortcutsModalOpen(true));
  if (closeShortcutsBtn) closeShortcutsBtn.addEventListener("click", () => setShortcutsModalOpen(false));

  const accessibilityBtn = document.getElementById("accessibilityBtn");
  const closeAccessibilityBtn = document.getElementById("closeAccessibilityBtn");
  if (accessibilityBtn) accessibilityBtn.addEventListener("click", () => setAccessibilityModalOpen(true));
  if (closeAccessibilityBtn) closeAccessibilityBtn.addEventListener("click", () => setAccessibilityModalOpen(false));

  // Onboarding Intent Grid
  const intentGrid = document.getElementById("onboardingIntentGrid");
  if (intentGrid) {
    intentGrid.addEventListener("click", (e) => {
      const btn = e.target.closest(".onboarding-intent-btn");
      if (!btn) return;
      const intentKey = btn.getAttribute("data-intent");
      if (intentKey) setOnboardingIntent(intentKey);
    });
  }

  // Initial data loading
  checkHealth();
  loadDocuments();
  loadSymptomSuggestions();
  loadSessions();
  await refreshSessionState();
  await hydrateLanguageFromProfile();
  await loadConsentCenterState();
  await loadGoals();
  updateOnboardingChecklist();
});
