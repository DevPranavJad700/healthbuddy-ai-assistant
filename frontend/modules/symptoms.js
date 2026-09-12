/**
 * HealthBuddy AI — Symptom Checker Module
 * Symptom chips selection, API prediction call, triage display.
 */

import { API, EMERGENCY_NUMBERS } from "./config.js";
import { state } from "./state.js";
import { esc, formatMsg, showToast } from "./utils.js";
import { appendMessage, showTyping } from "./chat.js";

export function addSymptom() {
  const input = document.getElementById("symptomInput");
  if (!input) return;
  const val = (input.value || "").trim().toLowerCase();
  if (!val || state.symptoms.includes(val)) return;
  state.symptoms.push(val);
  renderSymptoms();
  if (input.options && input.options.length > 0) {
    input.selectedIndex = 0;
  }
}

export async function loadSymptomSuggestions() {
  const input = document.getElementById("symptomInput");
  if (!input) return;
  try {
    const r = await fetch(API.symptomList);
    if (!r.ok) return;
    const data = await r.json();
    if (!Array.isArray(data.symptoms)) return;

    state.availableSymptoms = [...data.symptoms]
      .map((s) => String(s).trim())
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b));

    const options = [
      '<option value="">Select a symptom...</option>',
      ...state.availableSymptoms.map(
        (symptom) =>
          `<option value="${esc(symptom.toLowerCase())}">${esc(symptom)}</option>`
      ),
    ];
    input.innerHTML = options.join("");
  } catch (_) {
    // Keep UI usable if suggestions fail
  }
}

export function removeSymptom(s) {
  state.symptoms = state.symptoms.filter((x) => x !== s);
  renderSymptoms();
}

export function renderSymptoms() {
  const selectedSymptoms = document.getElementById("selectedSymptoms");
  const checkSymptomsBtn = document.getElementById("checkSymptomsBtn");
  if (!selectedSymptoms) return;

  selectedSymptoms.innerHTML = state.symptoms
    .map(
      (s) =>
        `<span class="symptom-tag">${esc(s)} <button type="button" onclick="window.removeSymptom('${s}')">&times;</button></span>`
    )
    .join("");

  if (checkSymptomsBtn) {
    checkSymptomsBtn.disabled = state.symptoms.length === 0;
  }
}

export async function checkSymptoms() {
  if (state.symptoms.length === 0) return;
  const welcomeScreen = document.getElementById("welcomeScreen");
  if (welcomeScreen) welcomeScreen.classList.add("hidden");

  appendMessage("user", `Symptom Check: ${state.symptoms.join(", ")}`);
  const typing = showTyping();

  try {
    const r = await fetch(API.symptomCheck, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symptoms: state.symptoms }),
    });
    const data = await r.json();
    typing.remove();

    let html = "";
    if (data.emergency) {
      html += `<div class="emergency-alert">${formatMsg(data.emergency_message)}</div>`;
    }
    html += `<strong>Severity: <span class="severity-${data.severity}">${data.severity ? data.severity.toUpperCase() : "INFO"}</span></strong>\n\n`;

    if (data.predictions && data.predictions.length > 0) {
      html += `**Possible Conditions:**\n\n`;
      data.predictions.forEach((p, i) => {
        const pct = Math.round((p.confidence || 0) * 100);
        html += `${i + 1}. **${p.condition}** (${pct}% match)\n`;
        if (p.description) html += `   ${p.description}\n`;
        if (p.matching_symptoms?.length) {
          html += `   Matching: ${p.matching_symptoms.join(", ")}\n\n`;
        }
      });
      const top = data.predictions[0];
      if (top?.recommendations?.length) {
        html += `**Recommendations:**\n`;
        top.recommendations.forEach((rec) => {
          html += `- ${rec}\n`;
        });
      }
    } else {
      html += `No matching conditions found. Please consult a healthcare professional.`;
    }

    if (data.disclaimer) {
      html += `\n\n---\n*${data.disclaimer}*`;
    }

    const finalHtml = html
      .replace(/\n/g, "<br>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>");

    await appendMessage("bot", finalHtml, [], null, null, null, false, false);
    state.symptomChecksCompleted += 1;
    if (typeof window.updateOnboardingChecklist === "function") {
      window.updateOnboardingChecklist();
    }
  } catch (err) {
    typing.remove();
    await appendMessage(
      "bot",
      `Error checking symptoms: ${err.message}`,
      [],
      null,
      null,
      null,
      false,
      true
    );
  }

  state.symptoms = [];
  renderSymptoms();
}

export function updateEmergencyNumber(countryKey = "us") {
  const el = document.getElementById("emergencyNumberText");
  if (!el) return;
  el.textContent = EMERGENCY_NUMBERS[countryKey] || EMERGENCY_NUMBERS.us;
}
