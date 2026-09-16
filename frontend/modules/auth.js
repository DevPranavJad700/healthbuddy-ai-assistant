/**
 * HealthBuddy AI — Auth, Consent & Privacy Module
 * User login, registration, OAuth, profile wizard, GDPR export/delete, consent tracking.
 */

import {
  API,
  API_BASE,
  AUTH_TOKEN_KEY,
  AUTH_REFRESH_TOKEN_KEY,
  AUTH_FORM_PREFS_KEY,
  PROFILE_ONBOARDING_DONE_KEY,
  PRIVACY_EXPORT_META_KEY,
  PRIVACY_AUDIT_TRAIL_KEY,
  LOCAL_HISTORY_KEY,
} from "./config.js";

import {
  state,
  getAuthToken,
  setAuthToken as saveAuthToken,
  getRefreshToken,
  setRefreshToken as saveRefreshToken,
  clearAuthTokens,
} from "./state.js";

export { getAuthToken };

import {
  esc,
  showToast,
  parseApiError,
  parseCommaSeparatedItems,
  setModalOpenWithFocus,
} from "./utils.js";

// Callbacks for hooks when auth state changes
let _onAuthChangeCallbacks = [];
export function onAuthChange(cb) {
  if (typeof cb === "function") _onAuthChangeCallbacks.push(cb);
}

function triggerAuthChange() {
  _onAuthChangeCallbacks.forEach((cb) => {
    try {
      cb();
    } catch (_) {}
  });
}

/** Return Authorization header object if token present */
export function authHeaders(extra = {}) {
  const token = getAuthToken();
  const base = { ...extra };
  if (token) base.Authorization = `Bearer ${token}`;
  return base;
}

/** Attempt to refresh expired access token */
export async function attemptTokenRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const r = await fetch(API.authRefresh, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${refreshToken}`,
      },
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || !data.token) return false;
    setAuthToken(data.token, data.refresh_token || refreshToken);
    await refreshSessionState();
    return true;
  } catch (_) {
    return false;
  }
}

/** Set token and update UI */
export function setAuthToken(token, refreshToken = null) {
  saveAuthToken(token);
  if (refreshToken) {
    saveRefreshToken(refreshToken);
  }
  updateAuthStatus("Signed in", "success");
  syncAuthUI();
  loadConsentCenterState();
  triggerAuthChange();

  if (typeof window.maybeShowOnboardingModal === "function") {
    window.maybeShowOnboardingModal();
  }
  if (typeof window.maybeShowProfileWizard === "function") {
    setTimeout(() => window.maybeShowProfileWizard(), 800);
  }
}

/** Clear token and reset UI */
export function clearAuthToken() {
  clearAuthTokens();
  state.consent.items = {};
  state.consent.loaded = false;
  renderConsentPills();
  updateConsentCenterStatus("Sign in to manage consent.");
  updateAuthStatus("Signed out", "");
  renderAuthBadges(false, false, null);
  syncAuthUI();
  setProfileOnboardingOpen(false);
  triggerAuthChange();
}

export function updateAuthStatus(message, type = "") {
  const el = document.getElementById("authStatus");
  if (!el) return;
  el.textContent = message || "";
  el.className = `auth-status${type ? ` ${type}` : ""}`;
}

export function syncAuthUI() {
  const hasToken = Boolean(getAuthToken());
  if (hasToken) {
    updateAuthStatus("Signed in", "success");
  } else {
    updateAuthStatus("", "");
    setDangerZoneOpen(false);
  }

  const openAuthModalBtn = document.getElementById("openAuthModalBtn");
  if (openAuthModalBtn) {
    openAuthModalBtn.textContent = hasToken ? "Account" : "Sign In";
  }

  const authLogoutBtn = document.getElementById("authLogoutBtn");
  if (authLogoutBtn) {
    authLogoutBtn.classList.toggle("hidden", !hasToken);
  }

  const dangerZoneToggleBtn = document.getElementById("dangerZoneToggleBtn");
  if (dangerZoneToggleBtn) {
    dangerZoneToggleBtn.disabled = !hasToken;
  }

  const deleteMyDataBtn = document.getElementById("deleteMyDataBtn");
  if (deleteMyDataBtn) {
    deleteMyDataBtn.disabled = !hasToken;
  }

  const exportMyDataBtn = document.getElementById("exportMyDataBtn");
  if (exportMyDataBtn) {
    exportMyDataBtn.disabled = !hasToken;
  }

  const adminDeleteUserBtn = document.getElementById("adminDeleteUserBtn");
  if (adminDeleteUserBtn) {
    adminDeleteUserBtn.disabled = !hasToken || !state.isAdmin;
  }

  const acctCard = document.getElementById("accountAccessCard");
  const signInNudge = document.getElementById("sidebarSignInNudge");
  if (acctCard) acctCard.classList.toggle("hidden", !hasToken);
  if (signInNudge) signInNudge.classList.toggle("hidden", hasToken);
}

export function setDangerZoneOpen(isOpen) {
  const panel = document.getElementById("dangerZonePanel");
  const btn = document.getElementById("dangerZoneToggleBtn");
  if (!panel || !btn) return;
  panel.classList.toggle("hidden", !isOpen);
  panel.classList.toggle("open", isOpen);
  btn.textContent = isOpen ? "Hide Danger Zone" : "Show Danger Zone";
  btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
}

export function setAuthPasswordVisible(isVisible) {
  const input = document.getElementById("authPasswordInput");
  const btn = document.getElementById("authPasswordToggleBtn");
  if (!input || !btn) return;
  input.type = isVisible ? "text" : "password";
  btn.textContent = isVisible ? "Hide" : "Show";
  btn.setAttribute("aria-label", isVisible ? "Hide password" : "Show password");
}

export function setAuthModalOpen(isOpen) {
  const modal = document.getElementById("authModal");
  setModalOpenWithFocus(modal, isOpen);
}

export function setProfileOnboardingOpen(isOpen) {
  const modal = document.getElementById("profileOnboardingModal") || document.getElementById("onboardingModal");
  setModalOpenWithFocus(modal, isOpen);
}

export function setAuthMode(mode = "login") {
  state.authMode = mode === "register" ? "register" : "login";
  const isRegister = mode === "register";

  const title = document.getElementById("authModalTitle");
  if (title) title.textContent = isRegister ? "Create Account" : "Sign In";

  const subtext = document.getElementById("authModalSubtext");
  if (subtext) {
    subtext.textContent = isRegister
      ? "Already have an account? Switch to log in."
      : "New here? Create an account to personalize your care experience.";
  }

  const signInBtn = document.getElementById("authModeSignInBtn");
  if (signInBtn) signInBtn.classList.toggle("active", !isRegister);

  const createBtn = document.getElementById("authModeCreateBtn");
  if (createBtn) createBtn.classList.toggle("active", isRegister);

  const regFields = document.getElementById("authRegisterFields");
  if (regFields) regFields.classList.toggle("hidden", !isRegister);

  const termsRow = document.getElementById("authTermsRow");
  if (termsRow) termsRow.classList.toggle("hidden", !isRegister);

  const loginBtn = document.getElementById("authLoginBtn");
  if (loginBtn) loginBtn.classList.toggle("hidden", isRegister);

  const regBtn = document.getElementById("authRegisterBtn");
  if (regBtn) regBtn.classList.toggle("hidden", !isRegister);

  const emailInput = document.getElementById("authEmailInput");
  if (emailInput) {
    emailInput.classList.toggle("hidden", !isRegister);
    emailInput.placeholder = isRegister
      ? "Email (required for account creation)"
      : "Email";
  }
}

export function loadAuthFormPreferences() {
  const uInput = document.getElementById("authUsernameInput");
  const eInput = document.getElementById("authEmailInput");
  const rem = document.getElementById("authRememberMe");
  if (!uInput || !eInput || !rem) return;
  try {
    const raw = localStorage.getItem(AUTH_FORM_PREFS_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    const expiresAt = Number(parsed?.expiresAt || 0);
    if (parsed && parsed.remember && expiresAt > Date.now()) {
      rem.checked = true;
      uInput.value = String(parsed.username || "");
      eInput.value = String(parsed.email || "");
    } else {
      rem.checked = false;
      localStorage.removeItem(AUTH_FORM_PREFS_KEY);
    }
  } catch (_) {
    rem.checked = false;
  }
}

export function saveAuthFormPreferences() {
  const uInput = document.getElementById("authUsernameInput");
  const eInput = document.getElementById("authEmailInput");
  const rem = document.getElementById("authRememberMe");
  if (!uInput || !eInput || !rem) return;
  if (!rem.checked) {
    localStorage.removeItem(AUTH_FORM_PREFS_KEY);
    return;
  }
  localStorage.setItem(
    AUTH_FORM_PREFS_KEY,
    JSON.stringify({
      remember: true,
      username: (uInput.value || "").trim(),
      email: (eInput.value || "").trim(),
      expiresAt: Date.now() + 30 * 24 * 60 * 60 * 1000,
    })
  );
}

export function setDeleteFlowProbe(status, details = {}) {
  window.__hbDeleteMyDataProbe = {
    status,
    timestamp: Date.now(),
    ...details,
  };
}
setDeleteFlowProbe("idle");

export function renderAuthBadges(isSignedIn, isAdmin, username) {
  state.isAdmin = Boolean(isAdmin);
  const signedInBadge = document.getElementById("signedInBadge");
  const adminBadge = document.getElementById("adminBadge");
  const acctLabel = document.getElementById("acctLabel");

  if (signedInBadge) {
    if (isSignedIn) {
      signedInBadge.textContent = "Signed in";
      signedInBadge.className = "acct-status-dot signed-in";
      if (acctLabel) acctLabel.textContent = username || "Signed In";
    } else {
      signedInBadge.textContent = "Signed out";
      signedInBadge.className = "acct-status-dot";
      if (acctLabel) acctLabel.textContent = "Guest User";
    }
  }

  if (adminBadge) {
    adminBadge.className = isAdmin ? "acct-status-dot admin" : "acct-status-dot hidden";
  }

  triggerAuthChange();
}

export async function refreshSessionState() {
  const token = getAuthToken();
  if (!token) {
    renderAuthBadges(false, false, null);
    return;
  }
  try {
    const r = await fetch(API.authSession, { headers: authHeaders() });
    if (r.status === 401) {
      clearAuthToken();
      updateAuthStatus("Session expired. Sign in again.", "error");
      return;
    }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(parseApiError(data, "Failed to read session"));
    renderAuthBadges(
      Boolean(data.authenticated),
      Boolean(data.is_admin),
      data.username || null
    );
    if (Boolean(data.authenticated)) {
      await maybeShowProfileOnboarding();
    }
  } catch (err) {
    updateAuthStatus(err.message || "Failed to check session", "error");
  }
}

export async function handleAuth(mode) {
  const uInput = document.getElementById("authUsernameInput");
  const pInput = document.getElementById("authPasswordInput");
  const eInput = document.getElementById("authEmailInput");
  const fInput = document.getElementById("authFirstNameInput");
  const lInput = document.getElementById("authLastNameInput");
  const terms = document.getElementById("authTermsCheckbox");

  const identifier = (uInput?.value || "").trim();
  const password = (pInput?.value || "").trim();
  const emailInput = (eInput?.value || "").trim();
  const firstName = (fInput?.value || "").trim();
  const lastName = (lInput?.value || "").trim();

  try {
    const isRegister = mode === "register";
    if (!password) {
      updateAuthStatus("Enter your password", "error");
      return;
    }
    if (!isRegister && !identifier) {
      updateAuthStatus("Enter email or username", "error");
      return;
    }
    if (isRegister) {
      if (!emailInput) {
        updateAuthStatus("Email is required for account creation", "error");
        return;
      }
      if (terms && !terms.checked) {
        updateAuthStatus("Accept Terms & Conditions to continue", "error");
        return;
      }
    }

    const normalizeIdentifier = (raw) => {
      const value = String(raw || "").trim();
      if (!value) return "";
      if (!value.includes("@")) return value;
      return value.split("@")[0] || value;
    };

    const registerUsername =
      normalizeIdentifier(identifier) ||
      normalizeIdentifier(`${firstName}${lastName ? `.${lastName}` : ""}`) ||
      normalizeIdentifier(emailInput) ||
      `user_${Date.now()}`;

    const body = isRegister
      ? {
          username: registerUsername,
          password,
          email: emailInput,
          full_name: [firstName, lastName].filter(Boolean).join(" ") || undefined,
          tos_accepted: true,
        }
      : { username: normalizeIdentifier(identifier), password };

    const r = await fetch(isRegister ? API.authRegister : API.authLogin, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      throw new Error(parseApiError(data, `Auth failed (${r.status})`));
    }
    if (!data.token) {
      throw new Error("Token not returned by server");
    }

    saveAuthFormPreferences();
    setAuthToken(data.token, data.refresh_token || null);
    showToast(isRegister ? "Registered and signed in" : "Signed in", "success");
    setAuthModalOpen(false);
    await refreshSessionState();
    await loadConsentCenterState();
    await maybeShowProfileOnboarding(true);
  } catch (err) {
    updateAuthStatus(err.message || "Authentication failed", "error");
    showToast(err.message || "Authentication failed", "error");
  }
}

export async function handleLogout() {
  try {
    const refreshToken = getRefreshToken();
    await fetch(API.authLogout, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ refresh_token: refreshToken || null }),
    });
  } catch (_) {
    // Local sign-out still proceeds
  }
  clearAuthToken();
  setAuthModalOpen(false);
  showToast("Signed out successfully", "success");
}

// ── Consent Management ─────────────────────────────────────────

export function getConsentState(consentType) {
  return state.consent.items[consentType] || { granted: false, policyVersion: null };
}

export function hasGrantedConsent(consentType) {
  return Boolean(getConsentState(consentType).granted);
}

export function updateConsentCenterStatus(message, type = "") {
  const el = document.getElementById("consentCenterActionStatus");
  if (!el) return;
  el.textContent = message || "";
  el.className = `consent-status-text${type ? ` ${type}` : ""}`;
}

export function renderConsentPills() {
  const mapping = ["ai_guidance", "terms_of_use", "personalization"];
  mapping.forEach((key) => {
    const target = document.getElementById(`consentStatus-${key}`);
    if (!target) return;
    const item = getConsentState(key);
    const granted = Boolean(item.granted);
    target.textContent = granted
      ? `Granted (${item.policyVersion || state.consent.policyVersion})`
      : "Not granted";
    target.className = `consent-pill ${granted ? "granted" : "revoked"}`;
  });
}

export function setConsentCenterOpen(isOpen) {
  const modal = document.getElementById("consentCenterModal");
  setModalOpenWithFocus(modal, isOpen);
}

function resolveLatestConsent(consents, consentType, scope) {
  const filtered = (consents || []).filter(
    (row) =>
      row &&
      row.consent_type === consentType &&
      ((row.scope || null) === (scope || null) || row.scope == null)
  );
  if (!filtered.length) {
    return { granted: false, policyVersion: null };
  }
  const latest = filtered[0];
  return {
    granted: Boolean(latest.granted),
    policyVersion: latest.policy_version || null,
  };
}

export async function loadConsentCenterState() {
  if (!getAuthToken()) {
    state.consent.items = {};
    state.consent.loaded = false;
    renderConsentPills();
    updateConsentCenterStatus("Sign in to manage consent.");
    return;
  }

  try {
    const r = await fetch(API.complianceConsentMe, { headers: authHeaders() });
    if (r.status === 401 && (await attemptTokenRefresh())) {
      return loadConsentCenterState();
    }
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      throw new Error(parseApiError(data, "Could not load consent history"));
    }
    const data = await r.json();
    const consents = Array.isArray(data.consents) ? data.consents : [];
    state.consent.items = {
      ai_guidance: resolveLatestConsent(consents, "ai_guidance", "chat"),
      terms_of_use: resolveLatestConsent(consents, "terms_of_use", "chat"),
      personalization: resolveLatestConsent(consents, "personalization", "personalization"),
    };
    state.consent.loaded = true;

    const versions = consents
      .map((c) => c?.policy_version)
      .filter(Boolean)
      .slice(0, 1);
    if (versions.length) state.consent.policyVersion = versions[0];

    const label = document.getElementById("consentPolicyVersionLabel");
    if (label) label.textContent = state.consent.policyVersion;

    renderConsentPills();
    updateConsentCenterStatus("Consent state updated.", "success");
  } catch (err) {
    updateConsentCenterStatus(err.message || "Could not load consent state", "error");
  }
}

export async function recordConsent(consentType, scope, granted) {
  if (!getAuthToken()) {
    showToast("Sign in required", "error");
    updateConsentCenterStatus("Sign in required to update consent.", "error");
    return false;
  }

  const payload = {
    consent_type: consentType,
    policy_version: state.consent.policyVersion || "2026.04",
    granted,
    scope,
  };

  const sendReq = async () =>
    fetch(API.complianceConsent, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    });

  let r = await sendReq();
  if (r.status === 401 && (await attemptTokenRefresh())) {
    return recordConsent(consentType, scope, granted);
  }
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(parseApiError(data, "Could not update consent"));
  }
  await loadConsentCenterState();
  return true;
}

export async function revokeConsent(consentType, scope) {
  if (!getAuthToken()) {
    showToast("Sign in required", "error");
    updateConsentCenterStatus("Sign in required to revoke consent.", "error");
    return false;
  }

  const r = await fetch(API.complianceConsentRevoke, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ consent_type: consentType, scope }),
  });
  if (r.status === 401 && (await attemptTokenRefresh())) {
    return revokeConsent(consentType, scope);
  }
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(parseApiError(data, "Could not revoke consent"));
  }
  await loadConsentCenterState();
  return true;
}

export function openConsentCenterWithContext(required = []) {
  setConsentCenterOpen(true);
  loadConsentCenterState();
  const summary = document.getElementById("consentCenterSummaryText");
  if (summary) {
    summary.textContent = required.length
      ? `Required now: ${required.join(", ")}. Grant consent to continue.`
      : "Review and manage your consent choices.";
  }
}

// ── Profile Onboarding & Wizard ────────────────────────────────

function hasProfileContext(profile) {
  if (!profile || typeof profile !== "object") return false;
  const age = Number(profile.age || 0);
  const gender = String(profile.gender || "").trim();
  const conditions = Array.isArray(profile.medical_conditions)
    ? profile.medical_conditions.filter(Boolean)
    : [];
  const allergies = Array.isArray(profile.allergies)
    ? profile.allergies.filter(Boolean)
    : [];
  return Boolean(age > 0 || gender || conditions.length || allergies.length);
}

export async function maybeShowProfileOnboarding(force = false) {
  if (!getAuthToken()) return;
  if (navigator.webdriver) return;
  if (!force && localStorage.getItem(PROFILE_ONBOARDING_DONE_KEY) === "1") return;

  try {
    const r = await fetch(API.authProfile, { headers: authHeaders() });
    if (!r.ok) return;
    const profile = await r.json().catch(() => ({}));
    if (hasProfileContext(profile)) {
      localStorage.setItem(PROFILE_ONBOARDING_DONE_KEY, "1");
      return;
    }
    const ageInput = document.getElementById("onboardingAgeInput");
    const genSelect = document.getElementById("onboardingGenderSelect");
    const medInput = document.getElementById("onboardingMedicalHistoryInput");
    const allInput = document.getElementById("onboardingAllergiesInput");

    if (ageInput && profile?.age) ageInput.value = String(profile.age);
    if (genSelect && profile?.gender) genSelect.value = String(profile.gender);
    if (medInput && Array.isArray(profile?.medical_conditions)) {
      medInput.value = profile.medical_conditions.join(", ");
    }
    if (allInput && Array.isArray(profile?.allergies)) {
      allInput.value = profile.allergies.join(", ");
    }

    setProfileOnboardingOpen(true);
  } catch (_) {}
}

export async function submitProfileOnboarding() {
  if (!getAuthToken()) {
    showToast("Sign in required", "error");
    return;
  }

  const ageInput = document.getElementById("onboardingAgeInput");
  const genSelect = document.getElementById("onboardingGenderSelect");
  const medInput = document.getElementById("onboardingMedicalHistoryInput");
  const allInput = document.getElementById("onboardingAllergiesInput");
  const saveBtn = document.getElementById("onboardingSaveBtn");

  const age = Number(ageInput?.value || 0);
  const gender = String(genSelect?.value || "").trim();
  const conditions = parseCommaSeparatedItems(medInput?.value);
  const allergies = parseCommaSeparatedItems(allInput?.value);

  if (!Number.isFinite(age) || age <= 0 || age > 120) {
    showToast("Enter a valid age between 1 and 120.", "error");
    return;
  }
  if (!gender) {
    showToast("Select a gender option.", "error");
    return;
  }

  try {
    if (saveBtn) saveBtn.disabled = true;
    const r = await fetch(API.authProfile, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        age: Math.round(age),
        gender,
        medical_conditions: conditions,
        allergies,
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(parseApiError(data, "Could not save profile"));
    localStorage.setItem(PROFILE_ONBOARDING_DONE_KEY, "1");
    setProfileOnboardingOpen(false);
    showToast("Profile onboarding completed", "success");
  } catch (err) {
    showToast(err.message || "Could not save profile", "error");
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
}

// ── GDPR & Danger Zone ──────────────────────────────────────────

export async function handleDeleteMyData(options = {}) {
  const forceConfirm = Boolean(options && options.forceConfirm);
  setDeleteFlowProbe("started", { forceConfirm });

  if (!getAuthToken()) {
    setDeleteFlowProbe("blocked", { reason: "no_token" });
    updateAuthStatus("Sign in required to delete account", "error");
    showToast("Sign in required", "error");
    return false;
  }

  const proceed = forceConfirm
    ? true
    : window.confirm(
        "This action is permanent and cannot be undone. Delete your account and all linked data?"
      );
  if (!proceed) {
    setDeleteFlowProbe("canceled", { reason: "confirm_declined" });
    return false;
  }

  const confirmPhrase = forceConfirm
    ? "DELETE_MY_DATA"
    : window.prompt("Type DELETE_MY_DATA to confirm permanent deletion:", "");
  if ((confirmPhrase || "").trim().toUpperCase() !== "DELETE_MY_DATA") {
    setDeleteFlowProbe("canceled", { reason: "confirmation_phrase_mismatch" });
    showToast("Deletion canceled: confirmation phrase did not match", "error");
    return false;
  }

  try {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 12000);
    const r = await fetch(API.authDeleteMyData, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ confirm: "DELETE_MY_DATA" }),
      signal: controller.signal,
    });
    window.clearTimeout(timeoutId);

    if (r.status === 401 && (await attemptTokenRefresh())) {
      setDeleteFlowProbe("retrying_auth");
      return handleDeleteMyData();
    }

    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      throw new Error(parseApiError(data, "Failed to delete account"));
    }

    setDeleteFlowProbe("success", { deleted: data?.deleted || null });
    clearAuthToken();
    localStorage.removeItem(LOCAL_HISTORY_KEY);
    localStorage.removeItem(PRIVACY_EXPORT_META_KEY);
    localStorage.removeItem(PRIVACY_AUDIT_TRAIL_KEY);
    state.currentSessionId = null;
    state.privacyExportMeta = null;
    state.privacyAuditTrail = [];

    showToast("Your account data has been permanently deleted", "success");
    return true;
  } catch (err) {
    setDeleteFlowProbe("error", {
      message: String(err?.message || "Delete account failed"),
    });
    showToast(err.message || "Delete account failed", "error");
    return false;
  }
}

export async function handleExportMyData() {
  if (!getAuthToken()) {
    showToast("Sign in required", "error");
    return false;
  }

  try {
    const r = await fetch(API.authExportMyData, {
      method: "GET",
      headers: authHeaders(),
    });

    if (r.status === 401 && (await attemptTokenRefresh())) {
      return handleExportMyData();
    }

    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      throw new Error(parseApiError(data, "Failed to export account data"));
    }

    const payload = data.export || {};
    const userId = payload?.user?.user_id || "me";
    const date = new Date().toISOString().slice(0, 10);
    const filename = `healthbuddy_export_${userId}_${date}.json`;
    const exportedAt = new Date().toISOString();

    localStorage.setItem(
      PRIVACY_EXPORT_META_KEY,
      JSON.stringify({ filename, exportedAt, userId })
    );

    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);

    showToast("Data export downloaded", "success");
    return true;
  } catch (err) {
    showToast(err.message || "Export failed", "error");
    return false;
  }
}

export async function adminDeleteUserData() {
  const input = document.getElementById("adminDeleteUserIdInput");
  const raw = (input?.value || "").trim();
  const userId = Number.parseInt(raw, 10);
  if (!Number.isInteger(userId) || userId <= 0) {
    showToast("Enter a valid user ID", "error");
    return;
  }
  if (!getAuthToken()) {
    showToast("Sign in required", "error");
    return;
  }
  if (!state.isAdmin) {
    showToast("Admin privileges required", "error");
    return;
  }

  const ok = window.confirm(
    `Delete all linked data for user #${userId}? This cannot be undone.`
  );
  if (!ok) return;

  try {
    const r = await fetch(`${API_BASE}/auth/admin/users/${userId}/data`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (r.status === 401 && (await attemptTokenRefresh())) {
      return adminDeleteUserData();
    }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(parseApiError(data, `Delete failed (${r.status})`));
    showToast("Admin deletion completed", "success");
    if (input) input.value = "";
  } catch (err) {
    showToast(err.message || "Admin deletion failed", "error");
  }
}

export function setPrivacyCenterOpen(isOpen) {
  const modal = document.getElementById("privacyCenterModal");
  setModalOpenWithFocus(modal, isOpen);
}

export function addPrivacyAuditEvent(action, level = "info", details = "") {
  try {
    const raw = localStorage.getItem(PRIVACY_AUDIT_TRAIL_KEY);
    const trail = raw ? JSON.parse(raw) : [];
    const event = {
      action,
      level,
      details,
      timestamp: new Date().toISOString(),
    };
    trail.unshift(event);
    if (trail.length > 50) trail.length = 50;
    localStorage.setItem(PRIVACY_AUDIT_TRAIL_KEY, JSON.stringify(trail));
    state.privacyAuditTrail = trail;
  } catch (_) {}
}

export async function loadPrivacyCenterData() {
  const exportStatusEl = document.getElementById("privacyExportStatus");
  const lastExportTimeEl = document.getElementById("privacyLastExportTime");
  const sessionListEl = document.getElementById("privacySessionList");
  const timelineEl = document.getElementById("privacyConsentTimeline");
  const auditTrailEl = document.getElementById("privacyAuditTrail");
  const statusEl = document.getElementById("privacyCenterStatus");

  const hasToken = Boolean(getAuthToken());

  if (exportStatusEl) {
    if (!hasToken) {
      exportStatusEl.textContent = "Sign in to export your account data.";
    } else {
      const metaRaw = localStorage.getItem(PRIVACY_EXPORT_META_KEY);
      if (metaRaw) {
        try {
          const meta = JSON.parse(metaRaw);
          exportStatusEl.textContent = `Last export: ${meta.filename || "Downloaded"}`;
          if (lastExportTimeEl && meta.exportedAt) {
            lastExportTimeEl.textContent = `Exported on ${new Date(meta.exportedAt).toLocaleString()}`;
          }
        } catch (_) {
          exportStatusEl.textContent = "Ready to export.";
        }
      } else {
        exportStatusEl.textContent = "Ready to export your account data.";
      }
    }
  }

  if (sessionListEl) {
    if (state.currentSessionId) {
      sessionListEl.innerHTML = `<p class="privacy-meta-text">Active session: <code>${esc(state.currentSessionId)}</code></p>`;
    } else {
      sessionListEl.innerHTML = `<p class="privacy-meta-text">No active session.</p>`;
    }
  }

  if (timelineEl) {
    if (state.consent && Array.isArray(state.consent.records) && state.consent.records.length > 0) {
      timelineEl.innerHTML = state.consent.records
        .map(
          (r) =>
            `<div class="privacy-meta-item"><strong>${esc(r.consent_type || "Consent")}</strong>: ${r.granted ? "Granted" : "Revoked"} (${new Date(r.created_at || Date.now()).toLocaleDateString()})</div>`
        )
        .join("");
    } else {
      timelineEl.innerHTML = `<p class="privacy-meta-text">No consent records yet.</p>`;
    }
  }

  if (auditTrailEl) {
    try {
      const raw = localStorage.getItem(PRIVACY_AUDIT_TRAIL_KEY);
      const trail = raw ? JSON.parse(raw) : [];
      if (trail.length > 0) {
        auditTrailEl.innerHTML = trail
          .slice(0, 10)
          .map(
            (ev) =>
              `<div class="privacy-meta-item"><strong>${esc(ev.action)}</strong> <span class="dim">(${new Date(ev.timestamp).toLocaleTimeString()})</span> - ${esc(ev.details || "")}</div>`
          )
          .join("");
      } else {
        auditTrailEl.innerHTML = `<p class="privacy-meta-text">No privacy actions recorded yet.</p>`;
      }
    } catch (_) {
      auditTrailEl.innerHTML = `<p class="privacy-meta-text">No privacy actions recorded yet.</p>`;
    }
  }

  if (statusEl) statusEl.textContent = "Ready.";
}

