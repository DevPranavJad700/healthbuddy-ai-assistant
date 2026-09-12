/**
 * HealthBuddy AI — State Management Module
 */

import {
  AUTH_TOKEN_KEY,
  AUTH_REFRESH_TOKEN_KEY,
  ONBOARDING_DISMISSED_KEY,
  ONBOARDING_INTENT_KEY,
  UI_LANGUAGE_KEY,
} from "./config.js";

export const state = {
  isLoading: false,
  sidebarOpen: false,
  symptoms: [],
  isRecording: false,
  currentSessionId: null,
  availableSymptoms: [],
  isAdmin: false,
  goalCount: 0,
  docCount: 0,
  hasChatHistory: false,
  queueCounts: { pending: 0, reviewed: 0, resolved: 0 },
  onboardingDismissed: localStorage.getItem(ONBOARDING_DISMISSED_KEY) === "1",
  onboardingIntent: localStorage.getItem(ONBOARDING_INTENT_KEY) || "symptom",
  uiLanguage: localStorage.getItem(UI_LANGUAGE_KEY) || "en",
  isOnline: navigator.onLine,
  lastFailedMessage: "",
  accessibilityPrefs: {
    reduceMotion: false,
    largeText: false,
    highContrast: false,
  },
  consent: {
    policyVersion: "2026.04",
    items: {},
    loaded: false,
  },
  handoffBySession: {},
  symptomChecksCompleted: 0,
  modalFocusReturnEl: null,
  privacyExportMeta: null,
  privacyAuditTrail: [],
  authMode: "login",
};

export function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  }
}

export function getRefreshToken() {
  return localStorage.getItem(AUTH_REFRESH_TOKEN_KEY) || "";
}

export function setRefreshToken(token) {
  if (token) {
    localStorage.setItem(AUTH_REFRESH_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(AUTH_REFRESH_TOKEN_KEY);
  }
}

export function clearAuthTokens() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_REFRESH_TOKEN_KEY);
}

export const ONBOARDING_INTENTS = {
  symptom: {
    title: "Symptom Check Path",
    subtitle: "Fast triage-first setup for users who need immediate symptom guidance.",
    hint: "Best when your first goal is a safe symptom check and follow-up guidance.",
    steps: [
      {
        id: "onboardingStepAuth",
        label: "Create or log into your account",
        done: () => Boolean(getAuthToken()),
      },
      {
        id: "onboardingStepGoal",
        label: "Run your first symptom check",
        done: () => state.symptomChecksCompleted > 0,
      },
      {
        id: "onboardingStepDoc",
        label: "Ask one follow-up question in chat",
        done: () => state.hasChatHistory,
      },
      {
        id: "onboardingStepChat",
        label: "Save one health goal for follow-up",
        done: () => state.goalCount > 0,
      },
    ],
  },
  chronic: {
    title: "Chronic Condition Path",
    subtitle: "Set up longitudinal context for recurring conditions and safer follow-up recommendations.",
    hint: "Use this for blood pressure, diabetes, asthma, and other ongoing care goals.",
    steps: [
      {
        id: "onboardingStepAuth",
        label: "Create or log into your account",
        done: () => Boolean(getAuthToken()),
      },
      {
        id: "onboardingStepGoal",
        label: "Set one long-term health goal",
        done: () => state.goalCount > 0,
      },
      {
        id: "onboardingStepDoc",
        label: "Upload one report or treatment note",
        done: () => state.docCount > 0,
      },
      {
        id: "onboardingStepChat",
        label: "Ask about long-term management",
        done: () => state.hasChatHistory,
      },
    ],
  },
  medication: {
    title: "Medication & Adherence Path",
    subtitle:
      "Prepare safer medication conversations with document context and personalized reminders.",
    hint: "Ideal for adherence coaching, side-effect questions, and schedule planning.",
    steps: [
      {
        id: "onboardingStepAuth",
        label: "Create or log into your account",
        done: () => Boolean(getAuthToken()),
      },
      {
        id: "onboardingStepGoal",
        label: "Add an adherence goal",
        done: () => state.goalCount > 0,
      },
      {
        id: "onboardingStepDoc",
        label: "Upload one prescription or medication summary",
        done: () => state.docCount > 0,
      },
      {
        id: "onboardingStepChat",
        label: "Ask one medication safety question",
        done: () => state.hasChatHistory,
      },
    ],
  },
  clinician: {
    title: "Clinician Queue Path",
    subtitle:
      "Admin workflow for high-risk handoffs, triage coverage, and SLA-based follow-up.",
    hint: "Admin only. Track pending, reviewed, and resolved cases in the clinician queue.",
    steps: [
      {
        id: "onboardingStepAuth",
        label: "Sign in with an admin account",
        done: () => Boolean(getAuthToken()) && state.isAdmin,
      },
      {
        id: "onboardingStepGoal",
        label: "Open clinician queue and load pending items",
        done: () => (state.queueCounts.pending || 0) > 0,
      },
      {
        id: "onboardingStepDoc",
        label: "Mark at least one case as reviewed",
        done: () => (state.queueCounts.reviewed || 0) > 0,
      },
      {
        id: "onboardingStepChat",
        label: "Resolve at least one escalated case",
        done: () => (state.queueCounts.resolved || 0) > 0,
      },
    ],
  },
};
