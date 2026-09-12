/**
 * HealthBuddy AI — Goals Management Module
 * User personal health goals, priorities, and preset goal chips.
 */

import { API } from "./config.js";
import { state, getAuthToken } from "./state.js";
import { esc, showToast, parseApiError } from "./utils.js";
import {
  authHeaders,
  attemptTokenRefresh,
  loadConsentCenterState,
  hasGrantedConsent,
  openConsentCenterWithContext,
} from "./auth.js";

export async function loadGoals() {
  const goalList = document.getElementById("goalList");
  const gate = document.getElementById("goalsSignInGate");
  const authed = document.getElementById("goalsAuthed");
  const emptyEl = document.getElementById("goalsEmpty");
  if (!goalList) return;

  const token = getAuthToken();
  if (!token) {
    if (gate) gate.classList.remove("hidden");
    if (authed) authed.classList.add("hidden");
    return;
  }

  if (gate) gate.classList.add("hidden");
  if (authed) authed.classList.remove("hidden");

  goalList.innerHTML = `<div style="font-size:0.72rem;color:var(--text-muted);padding:6px 0">Loading goals…</div>`;

  try {
    const r = await fetch(API.goals, { headers: authHeaders() });
    if (r.status === 401 && (await attemptTokenRefresh())) return loadGoals();
    if (r.status === 403) {
      await loadConsentCenterState();
      state.goalCount = 0;
      if (typeof window.updateOnboardingChecklist === "function") {
        window.updateOnboardingChecklist();
      }
      goalList.innerHTML = `<div class="empty-state-card">
        <p>Personalization consent required to manage goals.</p>
        <button class="empty-action-btn" type="button" onclick="window.openConsentCenterWithContext(['Personalization'])">Open consent center</button>
      </div>`;
      return;
    }
    if (!r.ok) throw new Error("Could not load goals");
    const data = await r.json();
    const goals = Array.isArray(data.goals) ? data.goals : [];
    state.goalCount = goals.length;
    if (typeof window.updateOnboardingChecklist === "function") {
      window.updateOnboardingChecklist();
    }

    // Mark preset chips as used
    document.querySelectorAll(".goal-preset-chip").forEach((chip) => {
      chip.classList.toggle("used", goals.some((g) => g.goal === chip.dataset.goal));
    });

    if (!goals.length) {
      goalList.innerHTML = "";
      if (emptyEl) emptyEl.classList.remove("hidden");
      return;
    }
    if (emptyEl) emptyEl.classList.add("hidden");

    const priorityEmoji = { high: "🔴", medium: "🟡", low: "🟢" };
    goalList.innerHTML = goals
      .map(
        (g) => `
        <div class="goal-card">
          <div class="goal-priority-dot ${esc(g.priority || "medium")}"></div>
          <div class="goal-card-text">${esc(g.goal)}</div>
          <span style="font-size:0.68rem;color:var(--text-muted);margin-right:4px">${priorityEmoji[g.priority] || "🟡"}</span>
          <button class="goal-card-delete" title="Delete goal" onclick="window.deleteGoal(${g.id})">✕</button>
        </div>`
      )
      .join("");
  } catch (err) {
    state.goalCount = 0;
    if (typeof window.updateOnboardingChecklist === "function") {
      window.updateOnboardingChecklist();
    }
    goalList.innerHTML = `<p style="font-size:0.72rem;color:var(--danger)">${esc(err.message || "Error loading goals")}</p>`;
  }
}

export async function addGoal() {
  const input = document.getElementById("goalInput");
  const prioritySelect = document.getElementById("goalPriority");
  const goal = (input?.value || "").trim();
  const priority = (prioritySelect?.value || "medium").trim();
  if (!goal) return;

  if (!state.consent.loaded && getAuthToken()) {
    await loadConsentCenterState();
  }
  if (getAuthToken() && !hasGrantedConsent("personalization")) {
    await loadConsentCenterState();
  }
  if (getAuthToken() && !hasGrantedConsent("personalization")) {
    showToast("Grant Personalization consent before adding goals", "error");
    openConsentCenterWithContext(["Personalization"]);
    return;
  }

  try {
    const r = await fetch(API.goals, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ goal, priority }),
    });
    if (r.status === 401 && (await attemptTokenRefresh())) {
      return addGoal();
    }
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      if (r.status === 403) {
        openConsentCenterWithContext(["Personalization"]);
      }
      throw new Error(parseApiError(e, "Failed to add goal"));
    }
    if (input) input.value = "";
    showToast("Goal added", "success");
    await loadGoals();
  } catch (err) {
    showToast(err.message || "Could not add goal", "error");
  }
}

export async function deleteGoal(goalId) {
  try {
    const r = await fetch(`${API.goals}/${goalId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (r.status === 401 && (await attemptTokenRefresh())) {
      return deleteGoal(goalId);
    }
    if (!r.ok) throw new Error("Failed to delete goal");
    showToast("Goal deleted", "success");
    await loadGoals();
  } catch (err) {
    showToast(err.message || "Delete failed", "error");
  }
}
