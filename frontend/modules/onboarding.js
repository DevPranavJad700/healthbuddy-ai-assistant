/**
 * HealthBuddy AI — Onboarding & Accessibility Module
 * User health profile wizard, onboarding checklist, accessibility preferences, and shortcuts.
 */

import {
  API,
  API_BASE,
  ONBOARDING_DISMISSED_KEY,
  ONBOARDING_INTENT_KEY,
  ACCESSIBILITY_PREFS_KEY,
} from "./config.js";

import { state, getAuthToken, ONBOARDING_INTENTS } from "./state.js";
import { esc, showToast, autoResize, setModalOpenWithFocus } from "./utils.js";
import { authHeaders } from "./auth.js";
import { loadGoals } from "./goals.js";

const PROFILE_ONBOARDING_DONE_KEY_V2 = "healthbuddy.profileOnboardingDoneV2";
const WIZARD_DONE_KEY = "healthbuddy.profileWizardDone";

let _wizardStep = 1;
let _wizardConditions = [];
let _wizardAllergies = [];
let _wizardGoals = [];

export function getActiveOnboardingIntent() {
  return ONBOARDING_INTENTS[state.onboardingIntent] || ONBOARDING_INTENTS.symptom;
}

export function setOnboardingIntent(intentKey) {
  if (!ONBOARDING_INTENTS[intentKey]) return;
  if (intentKey === "clinician" && !state.isAdmin) {
    showToast("Clinician onboarding is available only for admin accounts", "error");
    return;
  }
  state.onboardingIntent = intentKey;
  localStorage.setItem(ONBOARDING_INTENT_KEY, intentKey);
  updateOnboardingChecklist();
}

export function syncOnboardingIntentSelector() {
  const grid = document.getElementById("onboardingIntentGrid");
  if (!grid) return;
  const selected = state.onboardingIntent;
  grid.querySelectorAll(".onboarding-intent-btn").forEach((btn) => {
    const key = btn.getAttribute("data-intent") || "";
    const isClinician = key === "clinician";
    const blocked = isClinician && !state.isAdmin;
    btn.classList.toggle("active", key === selected);
    btn.classList.toggle("disabled", blocked);
    btn.setAttribute("aria-disabled", blocked ? "true" : "false");
    btn.disabled = false;
  });

  if (state.onboardingIntent === "clinician" && !state.isAdmin) {
    state.onboardingIntent = "symptom";
    localStorage.setItem(ONBOARDING_INTENT_KEY, "symptom");
  }
}

export function updateOnboardingChecklist() {
  const card = document.getElementById("onboardingCard");
  if (!card) return;

  syncOnboardingIntentSelector();
  const intent = getActiveOnboardingIntent();

  const title = document.getElementById("onboardingTitle");
  const subtitle = document.getElementById("onboardingSubtitle");
  const hint = document.getElementById("onboardingIntentHint");
  const progressBar = document.getElementById("onboardingProgressBar");
  const progressText = document.getElementById("onboardingProgressText");

  if (title) title.textContent = intent.title;
  if (subtitle) subtitle.textContent = intent.subtitle;
  if (hint) hint.textContent = intent.hint;

  const steps = intent.steps.map((stepDef) => {
    const stepEl = document.getElementById(stepDef.id);
    return [stepEl, Boolean(stepDef.done()), stepDef.label];
  });

  let completed = 0;
  steps.forEach(([stepEl, done, label]) => {
    if (!stepEl) return;
    stepEl.textContent = label;
    stepEl.classList.toggle("done", done);
    if (done) completed += 1;
  });

  const total = steps.length;
  const percent = Math.round((completed / total) * 100);
  if (progressBar) progressBar.style.width = `${percent}%`;
  if (progressText) progressText.textContent = `${completed} of ${total} completed`;

  if (completed === total) {
    card.classList.add("complete");
    if (progressText) progressText.textContent = "All setup steps completed";
  } else {
    card.classList.remove("complete");
  }

  card.classList.toggle("hidden", state.onboardingDismissed && completed < total);
}

// ── Onboarding Modal V2 ───────────────────────────────────────────

export function maybeShowOnboardingModal() {
  const token = getAuthToken();
  if (!token) return;
  const done = localStorage.getItem(PROFILE_ONBOARDING_DONE_KEY_V2);
  if (done === "1") return;
  setTimeout(() => showOnboardingModal(), 1200);
}

export function showOnboardingModal() {
  const modal = document.getElementById("onboardingModal");
  if (!modal) return;
  modal.style.display = "flex";
  setTimeout(() => {
    const firstInput = document.getElementById("ob_age");
    if (firstInput) firstInput.focus();
  }, 350);
}

export function hideOnboardingModal() {
  const modal = document.getElementById("onboardingModal");
  if (!modal) return;
  modal.style.opacity = "0";
  modal.style.transition = "opacity 0.2s ease";
  setTimeout(() => {
    modal.style.display = "none";
    modal.style.opacity = "";
    modal.style.transition = "";
  }, 200);
}

export function markOnboardingDone() {
  localStorage.setItem(PROFILE_ONBOARDING_DONE_KEY_V2, "1");
}

export async function submitOnboardingProfile(e) {
  if (e?.preventDefault) e.preventDefault();
  const age = parseInt(document.getElementById("ob_age")?.value || "0", 10);
  const gender = document.getElementById("ob_gender")?.value || "";
  const conditionsRaw = document.getElementById("ob_conditions")?.value || "";
  const allergiesRaw = document.getElementById("ob_allergies")?.value || "";

  const conditions = conditionsRaw.split(",").map((s) => s.trim()).filter(Boolean);
  const allergies = allergiesRaw.split(",").map((s) => s.trim()).filter(Boolean);

  const submitBtn = document.getElementById("onboardingSubmitBtn");
  const btnText = document.getElementById("onboardingBtnText");
  const statusEl = document.getElementById("onboardingStatus");

  if (submitBtn) submitBtn.disabled = true;
  if (btnText) btnText.textContent = "Saving…";
  if (statusEl) statusEl.style.display = "none";

  try {
    const payload = {};
    if (age > 0 && age <= 120) payload.age = age;
    if (gender) payload.gender = gender;
    if (conditions.length > 0) payload.medical_conditions = conditions;
    if (allergies.length > 0) payload.allergies = allergies;

    const response = await fetch(`${API_BASE}/auth/profile`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData?.detail || "Failed to save profile.");
    }

    if (statusEl) {
      statusEl.className = "onboarding-status success";
      statusEl.textContent = "✓ Profile saved! Answers will be personalised.";
      statusEl.style.display = "block";
    }
    markOnboardingDone();
    showToast("Health profile saved. Answers are now personalised to you.", "success");
    setTimeout(() => hideOnboardingModal(), 1600);
  } catch (err) {
    if (statusEl) {
      statusEl.className = "onboarding-status error";
      statusEl.textContent = err.message || "Profile not saved, please try again.";
      statusEl.style.display = "block";
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (btnText) btnText.textContent = "Save & Start Chatting";
  }
}

export function initOnboardingModal() {
  const form = document.getElementById("onboardingForm");
  const skipBtn = document.getElementById("onboardingSkipBtn");
  const overlay = document.getElementById("onboardingModal");

  if (form) form.addEventListener("submit", submitOnboardingProfile);

  if (skipBtn) {
    skipBtn.addEventListener("click", () => {
      markOnboardingDone();
      hideOnboardingModal();
    });
  }

  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        markOnboardingDone();
        hideOnboardingModal();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && overlay?.style.display === "flex") {
      markOnboardingDone();
      hideOnboardingModal();
    }
  });

  const wizardSkipBtn = document.getElementById("wizardSkipBtn");
  const wizardNextBtn = document.getElementById("wizardNextBtn");
  const wizardBackBtn = document.getElementById("wizardBackBtn");
  const wizardOverlay = document.getElementById("profileWizardModal");

  if (wizardSkipBtn) wizardSkipBtn.addEventListener("click", hideProfileWizard);
  if (wizardBackBtn) wizardBackBtn.addEventListener("click", () => renderWizardStep(_wizardStep - 1));
  if (wizardNextBtn) {
    wizardNextBtn.addEventListener("click", () => {
      if (_wizardStep < 3) renderWizardStep(_wizardStep + 1);
      else wizardFinish();
    });
  }
  if (wizardOverlay) {
    wizardOverlay.addEventListener("click", (e) => {
      if (e.target === wizardOverlay) hideProfileWizard();
    });
  }
}

// ── Multi-Step Profile Wizard ─────────────────────────────────────

export function showProfileWizard() {
  const modal = document.getElementById("profileWizardModal");
  if (!modal) return;
  _wizardStep = 1;
  _wizardConditions = [];
  _wizardAllergies = [];
  _wizardGoals = [];
  renderWizardStep(1);
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

export function hideProfileWizard() {
  const modal = document.getElementById("profileWizardModal");
  if (modal) {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }
  localStorage.setItem(WIZARD_DONE_KEY, "1");
}

export function renderWizardStep(step) {
  _wizardStep = step;
  const labels = ["Personal Info", "Health Background", "Health Goals"];
  const stepLabel = document.getElementById("wizardStepLabel");
  if (stepLabel) stepLabel.textContent = labels[step - 1] || "";

  document.querySelectorAll(".wizard-step-dot").forEach((dot) => {
    const n = parseInt(dot.dataset.step);
    dot.classList.remove("active", "done");
    if (n < step) dot.classList.add("done");
    else if (n === step) dot.classList.add("active");
  });

  document.querySelectorAll(".wizard-step-line").forEach((line, i) => {
    line.classList.toggle("done", i + 1 < step);
  });

  [1, 2, 3].forEach((n) => {
    const el = document.getElementById(`wizardStep${n}`);
    if (el) el.classList.toggle("hidden", n !== step);
  });

  const backBtn = document.getElementById("wizardBackBtn");
  const nextBtn = document.getElementById("wizardNextBtn");
  if (backBtn) backBtn.style.display = step > 1 ? "inline-flex" : "none";
  if (nextBtn) nextBtn.textContent = step === 3 ? "Finish 🎉" : "Next →";
}

export async function wizardFinish() {
  const token = getAuthToken();
  if (!token) {
    hideProfileWizard();
    return;
  }

  const fullName = document.getElementById("wizardFullName")?.value.trim() || "";
  const age = parseInt(document.getElementById("wizardAge")?.value || "0") || null;
  const gender = document.getElementById("wizardGender")?.value || "";

  const profilePayload = {};
  if (fullName) profilePayload.full_name = fullName;
  if (age) profilePayload.age = age;
  if (gender) profilePayload.gender = gender;
  if (_wizardConditions.length) profilePayload.medical_conditions = _wizardConditions;
  if (_wizardAllergies.length) profilePayload.allergies = _wizardAllergies;

  const nextBtn = document.getElementById("wizardNextBtn");
  if (nextBtn) {
    nextBtn.textContent = "Saving…";
    nextBtn.disabled = true;
  }

  try {
    if (Object.keys(profilePayload).length) {
      await fetch(API.authProfile, {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(profilePayload),
      });
    }
    for (const goal of _wizardGoals) {
      await fetch(API.goals, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ goal, priority: "medium" }),
      });
    }
    showToast("✅ Profile saved! HealthBuddy is now personalized for you.", "success", 4000);
  } catch (err) {
    showToast("⚠️ Couldn't save profile. You can update it later in settings.", "warning", 4000);
  } finally {
    hideProfileWizard();
    await loadGoals();
  }
}

export async function maybeShowProfileWizard() {
  if (localStorage.getItem(WIZARD_DONE_KEY)) return;
  if (!getAuthToken()) return;
  try {
    const r = await fetch(API.authProfile, { headers: authHeaders() });
    if (!r.ok) return;
    const data = await r.json();
    const profile = data.profile || data;
    const hasProfile = profile.full_name && profile.full_name.trim().length > 0;
    if (!hasProfile) showProfileWizard();
    else localStorage.setItem(WIZARD_DONE_KEY, "1");
  } catch (_) {}
}

export function makeTagInput(inputId, listId, tagsArray) {
  const input = document.getElementById(inputId);
  const list = document.getElementById(listId);
  if (!input || !list) return;

  function renderTags() {
    list.innerHTML = tagsArray
      .map(
        (t, i) =>
          `<span class="tag-pill">${esc(t)}<button class="tag-pill-remove" data-i="${i}" type="button">×</button></span>`
      )
      .join("");
    list.querySelectorAll(".tag-pill-remove").forEach((btn) => {
      btn.addEventListener("click", () => {
        tagsArray.splice(parseInt(btn.dataset.i), 1);
        renderTags();
      });
    });
  }

  function addTag(value) {
    const v = value.trim();
    if (!v || tagsArray.includes(v)) return;
    tagsArray.push(v);
    renderTags();
    input.value = "";
  }

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(input.value);
    }
  });
}

// ── Modals: Shortcuts & Accessibility ─────────────────────────────

export function setShortcutsModalOpen(isOpen) {
  const modal = document.getElementById("shortcutsModal");
  setModalOpenWithFocus(modal, isOpen);
}

export function setAccessibilityModalOpen(isOpen) {
  const modal = document.getElementById("accessibilityModal");
  setModalOpenWithFocus(modal, isOpen);
}

export function initRotatingPlaceholders() {
  const chatInput = document.getElementById("messageInput") || document.getElementById("chatInput");
  if (!chatInput) return;
  const placeholders = [
    "Ask about symptoms...",
    "How do I improve my sleep?",
    "What foods boost immunity?",
    "What's a healthy blood pressure?",
    "How to manage anxiety naturally?",
    "What vitamins should I take?",
  ];
  let pIdx = 0;
  chatInput.setAttribute("placeholder", placeholders[0]);
  setInterval(() => {
    pIdx = (pIdx + 1) % placeholders.length;
    chatInput.setAttribute("placeholder", placeholders[pIdx]);
  }, 4000);
}
